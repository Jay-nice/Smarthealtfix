"""
Content generator — schrijft de tekst voor een reel in een van jouw 8
sjabloon-vormen, en stuurt elke feitelijke claim door de factchecker voordat
het als "klaar om te posten" wordt gemarkeerd.

Vereist: een eigen Anthropic API-key in de omgevingsvariabele ANTHROPIC_API_KEY
(https://console.anthropic.com/settings/keys — niet hetzelfde als je claude.ai
account, dit is los, betaald per gebruik).
"""

import os
import json
import requests

from nutrition_reference import verify_claim, KNOWN_SHAKY_CLAIMS

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = "claude-sonnet-5"

TEMPLATE_SHAPES = {
    "numbered_explainer": {
        "description": "Genummerde tips: bold intro-fragment + uitleg wat het effect is.",
        "example": "Eat 1 apple with cinnamon every morning — your blood sugar will "
                   "stabilize and metabolism will increase.",
        "has_nutrient_claims": False,
    },
    "myth_bust": {
        "description": "Genummerd, '**Term** – uitleg' die een gangbare misvatting rechtzet.",
        "example": "Garlic – Chopping right before cooking reduces its health benefits; "
                   "let it sit for 10 minutes after cutting.",
        "has_nutrient_claims": False,
    },
    "boxed_hacks": {
        "description": "Bold klacht – korte fix, in een apart kader. Losse items, geen nummers.",
        "example": "Mosquito Bites – Rub a banana peel on the bite to reduce itching.",
        "has_nutrient_claims": False,
    },
    "allcaps_benefit": {
        "description": "ALLCAPS voedsel + 'is good for' + ALLCAPS groen orgaan/functie.",
        "example": "APPLES are good for LUNGS",
        "has_nutrient_claims": False,
    },
    "symptom_list": {
        "description": "Bold tekort/klacht – lijst symptomen. Geen nummers.",
        "example": "Vitamin B12 – Tingling in hands/feet, weakness, memory problems, and low mood.",
        "has_nutrient_claims": False,
    },
    "problem_food_mapping": {
        "description": "Genummerd, Probleem ----- Voedsel (kort en bondig).",
        "example": "Low Energy ----- Chia Seeds",
        "has_nutrient_claims": False,
    },
    "nutrient_comparison": {
        "description": "Genummerd, 'X heeft meer [nutrient] dan Y' — DIT is de vorm met harde, "
                       "checkbare cijferclaims (vitamine C, magnesium, kalium, vezels, etc).",
        "example": "A red bell pepper has nearly three times more vitamin C than an orange.",
        "has_nutrient_claims": True,
    },
    "mineral_sources": {
        "description": "Genummerd, mineraal (groen voordeel) + bronnenlijst met voedingsmiddelen eronder.",
        "example": "Magnesium (Muscle Relaxer) — Pumpkin Seeds | Dark Chocolate | Avocado | Cashews",
        "has_nutrient_claims": False,
    },
}


def build_system_prompt(shape_key, audience="algemeen"):
    shape = TEMPLATE_SHAPES[shape_key]
    audience_hint = {
        "algemeen": "Schrijf voor een algemeen, gezondheidsbewust publiek.",
        "50plus": "Schrijf met iets meer aandacht voor onderwerpen die relevant zijn voor "
                  "mensen van 45-65: energie, gewrichten, hart, geheugen, slaap, cholesterol. "
                  "Toon blijft gewoon toegankelijk, niet 'medisch' of belerend.",
    }[audience]

    return f"""Je schrijft content voor een Instagram health/wellness account in deze vaste vorm:

VORM: {shape['description']}
VOORBEELD: "{shape['example']}"

{audience_hint}

TAAL: schrijf ALTIJD in het Engels (titel, feiten, alles) — dit is de vaste
merkstijl van het account, ongeacht in welke taal dit verzoek zelf gesteld is.

Belangrijke regels:
- Alleen feitelijk verdedigbare claims. Als je twijfelt aan een cijfer, wees vager
  ("bevat veel") in plaats van een specifiek getal te verzinnen.
- Geen ebook/"Comment FIX"-promotie, dat voegen we later apart toe.
- Geef ALTIJD puur geldige JSON terug, niets anders, in dit schema:

{{
  "title": "TITEL IN HOOFDLETTERS MET {{{{EEN WOORD}}}} ALS ACCENT",
  "facts": ["Feit 1 met **bold** op de kernwoorden", "Feit 2 ..."],
  "claims": [
    {{"food_a": "...", "food_b": "...", "nutrient_key": "vitamin_c|magnesium|potassium|fiber|vitamin_d|vitamin_k|selenium|calcium|iron|zinc|omega3_ala"}}
  ]
}}

Vul "claims" alleen als de vorm harde voeding-vs-voeding vergelijkingen bevat
(zoals bij nutrient_comparison). Voor andere vormen: laat "claims" een lege lijst.
"""


def call_claude(system_prompt, user_prompt, max_retries=2):
    if not ANTHROPIC_API_KEY:
        raise RuntimeError(
            "Geen ANTHROPIC_API_KEY gevonden. Zet je eigen key: "
            "export ANTHROPIC_API_KEY=sk-ant-..."
        )

    last_error = None
    for attempt in range(1, max_retries + 2):
        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": ANTHROPIC_MODEL,
                "max_tokens": 4000,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        text = "".join(b["text"] for b in data["content"] if b["type"] == "text")
        text = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            last_error = e
            print(f"[!] Antwoord was geen geldige JSON (poging {attempt}/{max_retries + 1}): {e}. "
                  f"Probeer opnieuw...")
            continue

    raise RuntimeError(f"Kon na {max_retries + 1} pogingen geen geldige JSON van het "
                        f"model krijgen. Laatste fout: {last_error}")


def fact_check_content(content, shape_key):
    shape = TEMPLATE_SHAPES[shape_key]
    if not shape["has_nutrient_claims"] or not content.get("claims"):
        return True, {"checked": 0, "issues": []}

    issues = []
    for claim in content["claims"]:
        key = f"{claim['food_a']}_more_{claim['nutrient_key']}_than_{claim['food_b']}"
        shaky_match = next((v for k, v in KNOWN_SHAKY_CLAIMS.items()
                             if claim['food_a'].replace(" ", "_") in k
                             and claim['food_b'].replace(" ", "_") in k), None)
        if shaky_match:
            issues.append({"claim": claim, "verdict": "known_shaky", "note": shaky_match})
            continue

        result = verify_claim(claim["food_a"], claim["food_b"], claim["nutrient_key"],
                               use_live_api=False)
        if result["verdict"] != "confirmed":
            issues.append({"claim": claim, "verdict": result["verdict"], "detail": result})

    is_approved = len(issues) == 0
    return is_approved, {"checked": len(content["claims"]), "issues": issues}


def generate_and_check(shape_key, topic_hint, audience="algemeen"):
    system_prompt = build_system_prompt(shape_key, audience)
    user_prompt = f"Onderwerp/invalshoek: {topic_hint}\n\nSchrijf nu de content volgens het schema."
    content = call_claude(system_prompt, user_prompt)
    approved, report = fact_check_content(content, shape_key)
    return {
        "shape": shape_key,
        "content": content,
        "approved": approved,
        "fact_check_report": report,
    }


if __name__ == "__main__":
    fake_content_good = {
        "title": "SURPRISING {{FOOD}} FACTS",
        "facts": ["A **red bell pepper** has nearly three times more **vitamin C** than **an orange**."],
        "claims": [{"food_a": "red bell pepper", "food_b": "orange", "nutrient_key": "vitamin_c"}],
    }
    fake_content_bad = {
        "title": "SURPRISING {{FOOD}} FACTS",
        "facts": ["A **kiwi** has more **vitamin C** than **an orange**."],
        "claims": [{"food_a": "kiwi", "food_b": "orange", "nutrient_key": "vitamin_c"}],
    }
    for label, fake in [("Correcte claim", fake_content_good), ("Wankele claim", fake_content_bad)]:
        approved, report = fact_check_content(fake, "nutrient_comparison")
        print(f"\n{label}: approved={approved}")
        print(json.dumps(report, indent=2, ensure_ascii=False))
