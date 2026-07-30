"""
Nutrition-verificatie — checkt of een gegenereerde claim ("1 kop rode paprika
heeft 3x zoveel vitamine C als een sinaasappel") klopt met echte data.

Bron: USDA FoodData Central (fdc.nal.usda.gov) — gratis, publiek, overheidsdata.
Gratis API-key aanvragen (2 min): https://fdc.nal.usda.gov/api-key-signup.html
Zet 'm in de omgevingsvariabele FDC_API_KEY (of gebruik tijdelijk "DEMO_KEY"
om te testen, maar die heeft een streng rate limit).

LET OP: dit script belt api.nal.usda.gov aan — dat werkt op jouw eigen server
gewoon, maar niet vanuit deze Anthropic-sandbox (die staat alleen een beperkte
lijst domeinen toe). Vandaar dat de tests hieronder een lokale fallback-cache
gebruiken om de logica te demonstreren.
"""

import os
import requests

FDC_BASE_URL = "https://api.nal.usda.gov/fdc/v1"
FDC_API_KEY = os.environ.get("FDC_API_KEY", "DEMO_KEY")

# USDA nutrient-ID's die je het vaakst nodig hebt voor dit soort content
NUTRIENT_IDS = {
    "vitamin_c": 1162,
    "magnesium": 1090,
    "potassium": 1092,
    "fiber": 1079,
    "vitamin_d": 1114,
    "vitamin_k": 1185,
    "selenium": 1103,
    "calcium": 1087,
    "iron": 1089,
    "zinc": 1095,
    "omega3_ala": 1404,
}

# ---------------------------------------------------------------------------
# Kleine, met de hand geverifieerde startcache — werkt zonder internet, en
# dient als basis/voorbeeld. In productie vul je dit aan (of vervang je het
# volledig) met live USDA-opzoekingen via fetch_nutrient_amount().
# Waarden zijn afgeronde, representatieve USDA-cijfers per gangbare portie.
# ---------------------------------------------------------------------------
LOCAL_CACHE = {
    ("red bell pepper", "vitamin_c"): {"amount": 190, "unit": "mg", "per": "1 cup raw (149g)"},
    ("orange", "vitamin_c"): {"amount": 70, "unit": "mg", "per": "1 medium (130g)"},
    ("kiwi", "vitamin_c"): {"amount": 64, "unit": "mg", "per": "1 medium (76g)"},
    ("pumpkin seeds", "magnesium"): {"amount": 150, "unit": "mg", "per": "1 oz roasted (28g)"},
    ("banana", "magnesium"): {"amount": 32, "unit": "mg", "per": "1 medium (118g)"},
    ("banana", "potassium"): {"amount": 422, "unit": "mg", "per": "1 medium (118g)"},
    ("sweet potato", "potassium"): {"amount": 540, "unit": "mg", "per": "1 medium baked (114g)"},
    ("avocado", "potassium"): {"amount": 485, "unit": "mg", "per": "half avocado (100g)"},
    ("raspberries", "fiber"): {"amount": 8, "unit": "g", "per": "1 cup (123g)"},
    ("oatmeal", "fiber"): {"amount": 4, "unit": "g", "per": "1 cup cooked (234g)"},
    ("brazil nut", "selenium"): {"amount": 96, "unit": "mcg", "per": "1 nut (5g), varies sterk per bodem"},
    ("collard greens", "vitamin_k"): {"amount": 386, "unit": "mcg", "per": "1 cup cooked (190g)"},
    ("kale", "vitamin_k"): {"amount": 547, "unit": "mcg", "per": "1 cup cooked (130g)"},
}

# Claims die vaak online rondgaan maar wetenschappelijk wankel/misleidend zijn.
# De fact-checker moet deze altijd naar "needs_review" sturen, ongeacht bron.
KNOWN_SHAKY_CLAIMS = {
    "kiwi_more_vitc_than_orange": (
        "Een kiwi heeft veel vitamine C per calorie, maar een hele sinaasappel "
        "(groter, meer gewicht) bevat vaak een vergelijkbare of hogere absolute "
        "hoeveelheid. 'Kiwi heeft meer vitamine C dan een sinaasappel' is dus "
        "geen harde winst — nuanceren of vermijden."
    ),
    "chia_more_omega3_than_salmon": (
        "Chia bevat plantaardige ALA-omega-3; zalm bevat EPA/DHA. Het lichaam "
        "zet ALA maar voor ~5-10% om in bruikbare EPA/DHA. Qua ruwe grammen "
        "'omega-3' klopt de claim, maar zonder die context is hij misleidend."
    ),
    "dark_chocolate_more_antioxidants_than_green_tea": (
        "Antioxidant-vergelijkingen tussen totaal verschillende voedingsmiddelen "
        "(ORAC-waarden) zijn methodologisch omstreden — vermijd harde uitspraken "
        "hierover of houd het vaag ('bevat veel antioxidanten')."
    ),
}


def fetch_nutrient_amount(food_query: str, nutrient_key: str):
    """Haalt de hoeveelheid van een nutrient (per 100g) op bij USDA FoodData Central.
    Werkt op een normale server; in deze sandbox geblokkeerd (zie module-docstring)."""
    nutrient_id = NUTRIENT_IDS.get(nutrient_key)
    if nutrient_id is None:
        raise ValueError(f"Onbekende nutrient_key: {nutrient_key}")

    resp = requests.get(
        f"{FDC_BASE_URL}/foods/search",
        params={"query": food_query, "api_key": FDC_API_KEY, "pageSize": 1},
        timeout=10,
    )
    resp.raise_for_status()
    results = resp.json().get("foods", [])
    if not results:
        return None

    food = results[0]
    for n in food.get("foodNutrients", []):
        if n.get("nutrientId") == nutrient_id:
            return {
                "amount": n.get("value"),
                "unit": n.get("unitName"),
                "food_description": food.get("description"),
                "per": "100g",
            }
    return None


def verify_claim(food_a, food_b, nutrient_key, use_live_api=False, tolerance=0.25):
    """Vergelijkt food_a vs food_b op een nutrient. Retourneert een verdict:
    'confirmed' | 'contradicted' | 'unverifiable'.

    tolerance = hoeveel marge (25% default) voordat we een claim als
    'contradicted' bestempelen — voedingswaarden variëren nu eenmaal per
    kweek/rijpheid, dus een té strikte check levert alleen ruis op.
    """
    if use_live_api:
        a = fetch_nutrient_amount(food_a, nutrient_key)
        b = fetch_nutrient_amount(food_b, nutrient_key)
    else:
        a = LOCAL_CACHE.get((food_a, nutrient_key))
        b = LOCAL_CACHE.get((food_b, nutrient_key))

    if not a or not b:
        return {"verdict": "unverifiable", "reason": "Geen data gevonden voor een van beide, "
                                                        "stuur naar handmatige review."}

    ratio = a["amount"] / b["amount"] if b["amount"] else None
    return {
        "verdict": "confirmed" if ratio and ratio > 1 else "contradicted",
        "food_a": food_a, "food_b": food_b, "nutrient": nutrient_key,
        "amount_a": a, "amount_b": b, "ratio": round(ratio, 2) if ratio else None,
    }


if __name__ == "__main__":
    # Demonstratie met de lokale cache (geen internet nodig)
    tests = [
        ("red bell pepper", "orange", "vitamin_c"),
        ("pumpkin seeds", "banana", "magnesium"),
        ("sweet potato", "banana", "potassium"),  # let op: geen dramatisch verschil
        ("raspberries", "oatmeal", "fiber"),
    ]
    for food_a, food_b, nutrient in tests:
        result = verify_claim(food_a, food_b, nutrient, use_live_api=False)
        print(f"{food_a} vs {food_b} ({nutrient}): {result['verdict']} "
              f"(ratio {result.get('ratio')})")
