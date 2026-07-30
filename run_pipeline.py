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
import time
from datetime import datetime

from content_generator import generate_and_check, TEMPLATE_SHAPES
import generate_reel as gr
import generate_cover as gc
from instagram_publish import publish_reel

# Onderwerpen om uit te loten — vul dit gerust verder aan.
TOPIC_POOL = [
    ("nutrient_comparison", "vitamines en mineralen in veelgegeten groenten en fruit"),
    ("myth_bust", "veelgemaakte fouten bij het klaarmaken van gezond eten"),
    ("boxed_hacks", "snelle, ongevaarlijke huis-tuin-en-keuken trucjes voor kleine kwaaltjes"),
    ("allcaps_benefit", "welk voedsel goed is voor welk orgaan/lichaamsfunctie"),
    ("symptom_list", "signalen van een tekort aan een vitamine of mineraal"),
    ("problem_food_mapping", "welk voedsel helpt bij een veelvoorkomend klein gezondheidsprobleem"),
    ("mineral_sources", "een mineraal, zijn functie in het lichaam, en waar je het in vindt"),
    ("numbered_explainer", "kleine dagelijkse gewoontes met een concreet gezondheidsvoordeel"),
]


def pick_todays_topic(audience="algemeen"):
    return random.choice(TOPIC_POOL), audience


def run_once(handle="@smarthealthfix", display_name="Smart Health Fix",
             footer_cta="Save & Share let's get healthier together!",
             skip_upload=False):
    (shape_key, topic_hint), audience = pick_todays_topic()
    print(f"[1/5] Genereren: vorm='{shape_key}', onderwerp='{topic_hint}'")

    result = generate_and_check(shape_key, topic_hint, audience=audience)

    if not result["approved"]:
        # Niet zomaar posten — wegschrijven voor handmatige controle.
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

    # cover-titel = zelfde titel als de reel, maar zonder het {{accent}}-merkteken
    cover_title = content["title"].replace("{{", "").replace("}}", "")
    cover_path = gc.make_cover_for_topic(cover_title, display_name, f"output/cover_{ts}.png")
    print(f"[5/5] Cover klaar: {cover_path}")

    caption = build_caption(content)
    result_paths = {"png": png_path, "mp4": mp4_path, "cover": cover_path,
                     "content": content, "shape": shape_key, "caption": caption}

    # Altijd wegschrijven welke bestanden dit waren — publish_latest.py (aparte
    # stap, ná het pushen naar GitHub) gebruikt dit om te weten wat te posten.
    with open("output/last_run.json", "w") as f:
        json.dump(result_paths, f, indent=2, ensure_ascii=False)

    # --- Upload naar Instagram ---
    # Lokaal/VPS: kan direct, want het bestand staat al publiek zodra het er staat.
    # GitHub Actions: skip_upload=True, want het bestand moet eerst gepusht en
    # door GitHub Pages uitgerold worden — dat gebeurt in een aparte workflow-stap.
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
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-upload", action="store_true",
                         help="Genereer alleen, upload pas in een latere/aparte stap "
                              "(gebruikt door de GitHub Actions workflow).")
    args = parser.parse_args()
    run_once(skip_upload=args.skip_upload)
