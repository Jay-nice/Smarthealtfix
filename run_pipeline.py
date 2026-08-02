"""
run_pipeline.py — de dagelijkse "maak 1 reel"-stap.

Doet: tekst genereren (Claude) -> factchecken (USDA + bekende wankele claims)
-> als goedgekeurd: renderen tot afbeelding + 5-sec video met muziek
-> als afgekeurd: wegschrijven naar review_queue/ zodat jij het handmatig
   kan nakijken in plaats van dat er iets fouts automatisch gepost wordt.

Gebruik:
    export ANTHROPIC_API_KEY=sk-ant-...
    python3 run_pipeline.py
"""

import argparse
import json
import os
import random
import re
import time
from datetime import datetime

from content_generator import generate_and_check, TEMPLATE_SHAPES
import generate_reel as gr
import generate_cover as gc
from instagram_publish import publish_reel

TOPIC_POOL = [
    ("nutrient_comparison", "vitamines en mineralen in veelgegeten groenten en fruit - "
     "varieer breed tussen vitamine C, magnesium, kalium, vezels, vitamine D, vitamine K, "
     "selenium, calcium, ijzer, zink, omega-3, niet steeds dezelfde 1-2 stoffen"),
    ("myth_bust", "veelgemaakte fouten bij het klaarmaken van gezond eten"),
    ("boxed_hacks", "snelle, ongevaarlijke huis-tuin-en-keuken trucjes voor kleine kwaaltjes"),
    ("allcaps_benefit", "welk voedsel goed is voor welk orgaan/lichaamsfunctie"),
    ("symptom_list", "signalen van een tekort aan een vitamine of mineraal - kies breed uit "
     "o.a. ijzer, vitamine D, magnesium, vitamine B12, zink, kalium, vitamine C, calcium, "
     "jodium, foliumzuur, vitamine A, vitamine E, omega-3 - niet steeds dezelfde 5-6 'bekendste'"),
    ("problem_food_mapping", "welk voedsel helpt bij een veelvoorkomend klein gezondheidsprobleem"),
    ("mineral_sources", "een mineraal, zijn functie in het lichaam, en waar je het in vindt - "
     "varieer tussen o.a. magnesium, ijzer, zink, calcium, kalium, jodium, selenium, koper, "
     "mangaan - niet steeds dezelfde 2-3"),
    ("numbered_explainer", "kleine dagelijkse gewoontes met een concreet gezondheidsvoordeel"),
]


HISTORY_PATH = "output/history.json"
HISTORY_LENGTH = 3
TITLE_HISTORY_LENGTH = 6
ITEMS_HISTORY_LENGTH = 36   # ruim genoeg voor ~6 reels aan specifieke items


def _load_history():
    if not os.path.exists(HISTORY_PATH):
        return {"shapes": [], "titles": [], "items": []}
    try:
        with open(HISTORY_PATH) as f:
            data = json.load(f)
            if isinstance(data, list):
                return {"shapes": data, "titles": [], "items": []}
            data.setdefault("shapes", [])
            data.setdefault("titles", [])
            data.setdefault("items", [])
            return data
    except (json.JSONDecodeError, OSError):
        return {"shapes": [], "titles": [], "items": []}


def _extract_items(content):
    """
    Haalt de specifieke onderwerpen (voedingsstof/voedingsmiddel/klacht/orgaan) uit
    de gegenereerde feiten, zodat we die apart van de titel kunnen onthouden en de
    volgende keer kunnen laten vermijden. Twee simpele signalen, samengevoegd:
    - alle **vetgedrukte** stukken tekst
    - het stuk vóór het eerste streepje/liggend streepje (meestal de kern-entiteit,
      bijv. "Iron – ..." of "1. Hiccups ----- Peanut Butter")
    Geen perfecte NLP, maar ruim genoeg om te voorkomen dat dezelfde 5-6 voor de
    hand liggende items steeds terugkomen.
    """
    bold_re = re.compile(r"\*\*(.+?)\*\*")
    lead_re = re.compile(r"^\s*(?:\d+\.\s*)?(.+?)\s*(?:–|—|-{2,})\s")

    items = set()
    for fact in content.get("facts", []):
        for m in bold_re.findall(fact):
            cleaned = m.strip().strip(".,")
            if cleaned:
                items.add(cleaned)
        lead_match = lead_re.match(fact)
        if lead_match:
            lead = lead_match.group(1).replace("*", "").strip()
            if lead and len(lead) < 40:  # lange zinnen overslaan, dat is geen "item"
                items.add(lead)
    return items


def _save_history(shape_key, title, new_items=None):
    history = _load_history()
    history["shapes"] = (history["shapes"] + [shape_key])[-HISTORY_LENGTH:]
    history["titles"] = (history["titles"] + [title])[-TITLE_HISTORY_LENGTH:]
    if new_items:
        # dedupliceren met behoud van volgorde (oudste eerst, nieuwste onderaan)
        combined = history["items"] + [i for i in new_items if i not in history["items"]]
        history["items"] = combined[-ITEMS_HISTORY_LENGTH:]
    os.makedirs(os.path.dirname(HISTORY_PATH), exist_ok=True)
    with open(HISTORY_PATH, "w") as f:
        json.dump(history, f)


def pick_todays_topic(audience="algemeen"):
    history = _load_history()
    recent_shapes = history["shapes"]
    available = [t for t in TOPIC_POOL if t[0] not in recent_shapes]
    if not available:
        available = TOPIC_POOL
    choice = random.choice(available)
    return choice, audience


def run_once(handle="@smarthealthfix", display_name="Smart Health Fix",
             footer_cta="Save & Share let's get healthier together!",
             skip_upload=False):
    os.makedirs("output", exist_ok=True)
    os.makedirs("review_queue", exist_ok=True)

    (shape_key, topic_hint), audience = pick_todays_topic()
    print(f"[1/5] Genereren: vorm='{shape_key}', onderwerp='{topic_hint}'")

    history = _load_history()
    recent_titles = history["titles"]
    recent_items = history["items"]
    if recent_items:
        print(f"[1/5] Vermijd recente items: {', '.join(recent_items)}")
    result = generate_and_check(shape_key, topic_hint, audience=audience,
                                 recent_titles=recent_titles, recent_items=recent_items)

    if not result["approved"]:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"review_queue/flagged_{ts}.json"
        with open(path, "w") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"[!] Content afgekeurd door factcheck. Weggeschreven naar {path}")
        print(json.dumps(result["fact_check_report"], indent=2, ensure_ascii=False))
        return None

    print("[2/5] Factcheck OK, renderen...")
    content = result["content"]
    config = {
        "handle": handle,
        "title": content["title"],
        "facts": content["facts"],
        "footer_cta": footer_cta,
    }

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    png_path = gr.render_slide(config, f"output/reel_{ts}.png")
    print(f"[3/5] Afbeelding klaar: {png_path}")

    mp4_path, track = gr.image_to_reel_video(png_path, f"output/reel_{ts}.mp4")
    print(f"[4/5] Video klaar: {mp4_path} (muziek: {track})")

    cover_title = content["title"].replace("{{", "").replace("}}", "")
    cover_path = gc.make_cover_for_topic(cover_title, display_name, f"output/cover_{ts}.png")
    print(f"[5/5] Cover klaar: {cover_path}")

    new_items = _extract_items(content)
    print(f"[i] Nieuwe items uit deze reel (onthouden voor volgende keer): {', '.join(new_items) or '(geen gevonden)'}")
    _save_history(shape_key, cover_title, new_items)

    caption = build_caption(content)
    result_paths = {"png": png_path, "mp4": mp4_path, "cover": cover_path,
                     "content": content, "shape": shape_key, "caption": caption}

    with open("output/last_run.json", "w") as f:
        json.dump(result_paths, f, indent=2, ensure_ascii=False)

    public_base_url = os.environ.get("PUBLIC_BASE_URL")
    if skip_upload:
        print("[i] Upload overgeslagen (--skip-upload) — gebeurt in een latere stap.")
    elif public_base_url:
        video_url = f"{public_base_url}/{mp4_path}"
        cover_url = f"{public_base_url}/{cover_path}"
        media_id = publish_reel(video_url=video_url, cover_url=cover_url, caption=caption)
        result_paths["instagram_media_id"] = media_id
    else:
        print("[i] PUBLIC_BASE_URL niet gezet — reel is klaar maar nog niet geupload.")

    return result_paths


def build_caption(content, hashtags="#healthyeating #wellness #healthtips"):
    return f"{content['title'].replace('{{', '').replace('}}', '')}\n\n{hashtags}"


if __name__ == "__main__":
    import sys

    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-upload", action="store_true",
                         help="Genereer alleen, upload pas in een latere/aparte stap "
                              "(gebruikt door de GitHub Actions workflow).")
    args = parser.parse_args()
    result = run_once(skip_upload=args.skip_upload)

    if result is None:
        # run_once() geeft None terug als de factcheck de content afkeurde (zie
        # review_queue/). Vroeger merkte niemand dit: het script sloot gewoon af
        # met exit code 0, GitHub Actions zag dat als "gelukt", en de publiceer-
        # stap postte dan stilletjes de VORIGE (oude) reel nog een keer omdat er
        # niks nieuws was om te posten. Nu laten we dit expliciet als mislukking
        # tellen, zodat de workflow rood kleurt en er NIETS herhaald/herpost wordt.
        print("[FOUT] Geen nieuwe reel gemaakt deze run (afgekeurd door factcheck of "
              "een andere reden - zie hierboven). Dit telt vanaf nu als mislukt, dus "
              "wordt er niks (opnieuw) gepost.")
        sys.exit(1)
