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
from dotenv import load_dotenv

from nutrition_reference import verify_claim, KNOWN_SHAKY_CLAIMS

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = "claude-sonnet-5"

TEMPLATE_SHAPES = {
    "numbered_explainer": {
        "description": "Genummerde tips: bold intro-fragment + uitleg wat het effect is.",
        "example": "Eat 1 apple with cinnamon every morning — your blood sugar will "
                   "stabilize and metabolism will increase.",
        "has_nutrient_claims": False,
        "numbered": True,
    },
    "myth_bust": {
        "description": "Genummerd, '**Term** – uitleg' die een gangbare misvatting rechtzet.",
        "example": "Garlic – Chopping right before cooking reduces its health benefits; "
                   "let it sit for 10 minutes after cutting.",
        "has_nutrient_claims": False,
        "numbered": True,
    },
    "boxed_hacks": {
        "description": "Bold klacht – korte fix, in een apart kader. Losse items, geen nummers.",
        "example": "Mosquito Bites – Rub a banana peel on the bite to reduce itching.",
        "has_nutrient_claims": False,
        "numbered": False,
    },
    "allcaps_benefit": {
        "description": "ALLCAPS voedsel + 'is good for' + ALLCAPS groen orgaan/functie.",
        "example": "APPLES are good for LUNGS",
        "has_nutrient_claims": False,
        "numbered": False,
    },
    "symptom_list": {
        "description": "Bold tekort/klacht – lijst symptomen. Geen nummers.",
        "example": "Vitamin B12 – Tingling in hands/feet, weakness, memory problems, and low mood.",
        "has_nutrient_claims": False,
        "numbered": False,
    },
    "problem_food_mapping": {
        "description": "Genummerd, Probleem ----- Voedsel (kort en bondig).",
        "example": "Low Energy ----- Chia Seeds",
        "has_nutrient_claims": False,
        "numbered": True,
    },
    "nutrient_comparison": {
        "description": "Genummerd, 'X heeft meer [nutrient] dan Y' — DIT is de vorm met harde, "
                       "checkbare cijferclaims (vitamine C, magnesium, kalium, vezels, etc).",
        "example": "A red bell pepper has nearly three times more vitamin C than an orange.",
        "has_nutrient_claims": True,
        "numbered": True,
    },
    "mineral_sources": {
        "description": "Genummerd, mineraal (groen voordeel) + bronnenlijst met voedingsmiddelen eronder.",
        "example": "Magnesium (Muscle Relaxer) — Pumpkin Seeds | Dark Chocolate | Avocado | Cashews",
        "has_nutrient_claims": False,
        "numbered": True,
    },
    "daily_dose_habit": {
        "description": "Genummerd, EXACT dit pijl-format: '[Voedingsmiddel] -> [precieze hoeveelheid/"
                       "frequentie] -> [kort concreet voordeel, 2-4 woorden]'. Dit specifieke format "
                       "(voedingsmiddel, exacte dosis, resultaat, alle drie kort) is BEWEZEN STERK "
                       "PRESTEREND voor dit account - gebruik 'm dus relatief vaak in de rotatie. De "
                       "hoeveelheid moet een concreet, gangbaar getal/eenheid zijn (aantal stuks, cups, "
                       "eetlepels, mg, keer per week) - nooit vaag ('regelmatig', 'af en toe').",
        "example": "Kiwi -> 2 before bed -> Better sleep",
        "has_nutrient_claims": False,
        "numbered": True,
    },
    "organ_food_list": {
        "description": "Genummerd, '[Orgaan/lichaamsdeel] - [Voedsel1], [Voedsel2], [Voedsel3]' - één "
                       "orgaan gekoppeld aan een kommalijst van 2-4 voedingsmiddelen die het ondersteunen.",
        "example": "Lungs - Garlic, Pineapple, Ginger",
        "has_nutrient_claims": False,
        "numbered": True,
    },
    "conditional_transformation": {
        "description": "Genummerd, 'If you ate/did [item] every day for [tijdsbestek], you would "
                       "[heel specifiek, verrassend resultaat].' - conditionele wat-als-vorm met een "
                       "concreet tijdsbestek (bijv. '2 weeks', '30 days').",
        "example": "If you ate turmeric every day for two weeks, your inflammation would "
                   "decrease and your skin would glow.",
        "has_nutrient_claims": False,
        "numbered": True,
    },
    "imperative_advice_list": {
        "description": "Genummerd of met bullets, directe opdracht/advies in gebiedende wijs + korte "
                       "reden: '[Doe dit] [reden/wanneer].' Directer en actiegerichter dan de andere "
                       "vormen, vaak gericht op een specifieke doelgroep of levensfase.",
        "example": "Walk every day to help maintain balance and mobility.",
        "has_nutrient_claims": False,
        "numbered": True,
    },
}


ACCOUNT_PILLARS = ("nutrition (voeding), common health issues/symptoms (klachten), "
                    "organs & body functions (organen), and small daily habits (gewoontes)")


def build_system_prompt(shape_key, audience="algemeen", handle="@smarthealthfix"):
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

TAAL: schrijf ALTIJD in het Engels (titel, feiten, caption, alles) — dit is de vaste
merkstijl van het account, ongeacht in welke taal dit verzoek zelf gesteld is.

TITEL: maak 'm NIEUWSGIERIG-MAKEND, geen platte samenvatting die de hele inhoud al
weggeeft. Kies uit dit soort hooks, wat het beste past bij het onderwerp. De eerste
twee hieronder ("autoriteit verzwijgt iets" en "dit klinkt slecht maar is eigenlijk
goed") zijn bij vergelijkbare accounts BIJ VERRE de sterkste performers qua views
(soms 3-10x meer views dan een neutrale/beschrijvende titel over hetzelfde onderwerp)
- gebruik die twee dus vaker dan de rest (ruim de helft van de keren), en wissel de
andere helft af met de overige patronen zodat het niet elke keer identiek aanvoelt:
- "WHAT {{AUTORITEIT}} DOESN'T WANT YOU TO KNOW" / "{{ONDERWERP}} DOCTORS WON'T TELL YOU" /
  "DOCTORS DON'T WANT YOU TO KNOW THIS" (wantrouwen richting een gevestigde autoriteit zoals
  "big pharma", "doctors", "the food industry" - suggereert verzwegen/onderbelichte info)
- "SIGNS YOU'RE ACTUALLY {{ONVERWACHT POSITIEF}}" / "WEIRD SIGNS YOU'RE ACTUALLY HEALTHIER
  THAN YOU THINK" (draait een op-het-eerste-gezicht negatieve/verontrustende insteek om in
  iets positiefs/geruststellends - erg sterke curiosity-hook). LET OP: gebruik "SIGNS"/
  "SIGNALS" in de titel ALLEEN als de items ook LETTERLIJK waarneembare lichaamssignalen
  of symptomen zijn (bijv. bij de symptom_list-vorm). Gebruik dit NOOIT bij een lijst van
  voedingsmiddelen/aanbevelingen (bijv. allcaps_benefit, organ_food_list, daily_dose_habit,
  mineral_sources, nutrient_comparison, problem_food_mapping) - "eet dit voor dat orgaan"
  is geen "signaal", en die mismatch tussen titel en inhoud is verwarrend en voelt als
  clickbait zonder inlossing. Past de insteek van deze vorm niet bij "signs", kies dan een
  van de andere hooks hieronder.
- "WHAT HAPPENS TO YOUR BODY WHEN YOU {{...}}" (nieuwsgierigheid naar een gevolg)
- "IF YOU {{DOE X}}... THIS IS WHAT HAPPENS" (conditionele cliffhanger)
- "WHY {{VERRASSENDE/TEGENDRAADSE CLAIM}}"
- "THE REAL REASON YOU {{HERKENBAAR PROBLEEM}}"
- Een pakkende belofte: "{{ACCENT}} THAT ACTUALLY WORK" / "NEVER {{NEGATIEF}} AGAIN"
- "{{ONDERWERP}} CHEAT SHEET" (bijv. "BETTER SLEEP CHEAT SHEET") - handig, compact
  naslagwerk-gevoel, past vooral goed bij vormen met precieze hoeveelheden/dosis-items
BELANGRIJK, geldt voor ELKE hook hierboven: de titel moet accuraat zijn over WAT voor
soort content erop volgt - beloof nooit iets dat de lijst niet waarmaakt (bijv. "signs"/
"symptoms" beloven terwijl de lijst gewoon voedingsmiddel-aanbevelingen zijn, of "if you
do X" beloven terwijl er meerdere losse, ongerelateerde acties in staan). Een titel die
net niet klopt met de inhoud voelt als clickbait-zonder-inlossing en kost vertrouwen -
kies liever een net iets minder spannende hook die WEL exact past bij wat je gaat tonen.
Vermijd platte, puur beschrijvende titels zonder enige spanning (bijv. "IMPORTANT HEALTH
TIPS", "BODY CLEANSING FOODS", "FOOD FACTS YOU DIDN'T KNOW") - dat soort titels presteert
aantoonbaar veel slechter. Gebruik het woord "YOU"/"YOUR" waar het past (2e persoon
presteert beter dan neutrale 3e-persoon benoeming). Als je een getal in de titel gebruikt
(bijv. "16 WARNING SIGNS"), laat het als een compleet, universeel relevant lijstje voelen -
niet als "PART 1" of onnodig ingeperkt tot een smalle subgroep, dat presteert juist slechter.
Een titel die je al helemaal kan raden puur op de eerste paar woorden is te plat -
laat 'm een vraag oproepen die iemand alleen kan beantwoorden door de lijst te lezen.

AANTAL ITEMS IN "facts": er is geen vast aantal - bepaal het aantal items op basis van
hoeveel uitleg elk item nodig heeft, met als doel dat de TOTALE hoeveelheid tekst op de
afbeelding behapbaar blijft (denk ongeveer een vast "tekstbudget" per reel, niet een
vast aantal items). Twee richtlijnen die je tegen elkaar afweegt:
- Items met een korte, kernachtige zin (bijv. "**Kernwoord** -> kort gevolg", weinig
  woorden per item): dan mag je MEER items gebruiken, tot 10-13.
- Items met een langere, uitleggende zin per stuk (bijv. "If you ate X every day for Y
  weeks, [uitgebreid gevolg + mechanisme]"): houd het dan bij MINDER items, 6-8, anders
  wordt de tekst te dicht en te klein om prettig te lezen.
Nooit minder dan 5 items, nooit meer dan 13. Niemand heeft zin om op Instagram een heel
boek te lezen — kort en pakkend per item werkt beter dan een uitgebreid essay per item,
ongeacht hoeveel items je kiest. Het ALLERLAATSTE item in "facts" is ALTIJD een
follow-oproep, in EXACT dezelfde stijl en
opmaak als de andere items (dus ook met **bold** op het kernwoord en, indien de vorm
een scheidingsteken/nummer gebruikt, dat ook hier), bijvoorbeeld in de trant van:
"**Follow along** – for more daily health tips like this." Verzin 'm zelf passend bij
de vorm, dit is maar een voorbeeld.

Belangrijke regels voor "facts":
- Alleen feitelijk verdedigbare claims. Als je twijfelt aan een cijfer, wees vager
  ("bevat veel") in plaats van een specifiek getal te verzinnen.
- PRECIEZE HOEVEELHEDEN ZIJN GOUD voor dit account (bewezen sterk presterend): "2 kiwis
  before bed", "1 cup/day", "2x/week", "1 tbsp/day", "400 mg magnesium" - dit soort
  concrete dosis/frequentie-aanduidingen mag en moet je vaak gebruiken, in vrijwel elke
  vorm, niet alleen bij "daily_dose_habit". Belangrijk onderscheid: dit mag ALLEEN als
  het gaat om algemeen erkend, veelgebruikt voedingsadvies (portiegroottes, gangbare
  suppletie-doseringen) - verzin GEEN exacte percentages of pseudo-wetenschappelijke
  mechanisme-claims om precies te LIJKEN (bijv. "verhoogt calorieverbranding met 15%",
  "activeert NAD+-paden", "blokkeert vetopslagenzymen") - dat soort overdreven specifieke
  taal klinkt knap maar is meestal onbewezen/verzonnen, en is precies waar de factcheck
  op let. Concrete hoeveelheid bij een alledaags voedingsmiddel: ja, graag veel. Concreet
  klinkend maar onbewezen mechanisme/percentage: nee.
- Geen ebook/"Comment FIX"-promotie in de items zelf (behalve de follow-oproep hierboven).
- Gebruik levendige, beeldende werkwoorden waar het kan (bijv. "blunts the spike",
  "pulls sugar out of your blood", "melts away") in plaats van vlakke taal als
  "helps support" of "is good for" - dat leest sneller pakkend in een paar seconden
  scrollen.
- Zet het meest verrassende/sterkste item ALS EERSTE (na eventuele intro), niet per se
  chronologisch of logisch geordend. Hoe pakkender de eerste regel, hoe groter de kans
  dat iemand blijft kijken/lezen - dat is belangrijker dan een nette volgorde.

CAPTION: naast de afbeelding-tekst schrijf je ook een aparte Instagram-caption
("caption") van 3 alinea's, in deze vaste volgorde:
1. VERPLICHT: noem hierin LETTERLIJK het kernwoord van 2 tot 3 items uit "facts"
   (herhaal het woord dat in "facts" ook **bold** stond, bijv. als een fact over
   "**garlic**" gaat, moet het woord "garlic" ook hier expliciet terugkomen) en
   geef bij ELK van die 2-3 items een extra zin uitleg/mechanisme die NIET al op de
   afbeelding stond — waarom werkt het, wat gebeurt er in het lichaam. Dit moet
   voelen als 2-3 mini-uitleg-momenten na elkaar, dus ECHT meerdere zinnen (nooit
   maar 1 kort algemeen zinnetje als "everyone's body is different"). Pas aan het
   eind van deze alinea, na die 2-3 concrete stukjes, mag een korte relativerende
   afsluitzin zoals "everyone's body is different, listen to yours".
2. Een merk-alinea die {handle} noemt en verwijst naar de vaste pijlers van het
   account: {ACCOUNT_PILLARS} — gevolgd door een aparte tweede zin die de missie van
   het account in eigen woorden samenvat (bijv. "Our mission is to help you build
   small, realistic habits instead of chasing quick fixes."). Varieer de formulering
   van beide zinnen, herhaal ze niet letterlijk elke keer.
3. Een save & share-oproep, bijv. "Save this post so you don't lose it, and share it
   with someone who needs to see this today."
Scheid de 3 alinea's met een lege regel (\\n\\n). Herhaal de titel NIET letterlijk in
de caption, die staat al in de afbeelding. In totaal moet de caption ruim langer zijn
dan je gewend bent - streef naar 110-180 woorden totaal (vooral alinea 1 mag stevig
zijn dankzij de 2-3 uitgewerkte items), niet 3 losse eenregelige zinnetjes.

HASHTAGS EN TREFWOORDEN: geef in "hashtags" een lijst van 8 tot 12 relevante
hashtags (elk met #) die passen bij het SPECIFIEKE onderwerp van deze reel — dus
niet steeds exact dezelfde set. Mix een paar brede gezondheidshashtags (bijv.
#healthtips #wellness) met meerdere die specifiek zijn voor het onderwerp van
vandaag. Geef DAARNAAST in "extra_keywords" een lijst van 3 tot 5 losse trefwoorden
ZONDER #-teken (bijv. "naturalhealing", "wellnessjourney", "guttips") die aan het
eind van de hashtag-regel worden geplakt, zoals veel grote health-accounts doen.

Geef ALTIJD puur geldige JSON terug, niets anders, in dit schema:

{{
  "title": "TITEL IN HOOFDLETTERS MET {{{{EEN WOORD}}}} ALS ACCENT",
  "facts": ["Feit 1 met **bold** op de kernwoorden", "... laatste item is de follow-oproep"],
  "claims": [
    {{"food_a": "...", "food_b": "...", "nutrient_key": "vitamin_c|magnesium|potassium|fiber|vitamin_d|vitamin_k|selenium|calcium|iron|zinc|omega3_ala"}}
  ],
  "caption": "Alinea 1 tekst (2-3 items met naam genoemd + uitleg).\\n\\nAlinea 2 tekst.\\n\\nAlinea 3 tekst.",
  "hashtags": ["#tag1", "#tag2", "#tag3"],
  "extra_keywords": ["keyword1", "keyword2", "keyword3"]
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
                "max_tokens": 6000,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
                # Op claude-sonnet-5 staat "thinking" standaard AAN zodra je 'm
                # weglaat, en die denk-tokens gaan af van max_tokens - dat kon
                # bij lange content (12+ vormen, 3-alinea caption, 8-12
                # hashtags) de daadwerkelijke JSON-tekst laten afkappen
                # halverwege (vandaar eerdere "Unterminated string"-fouten).
                # We hebben hier geen redeneerstappen nodig, alleen
                # betrouwbare JSON-output, dus schakelen we 'm expliciet uit.
                "thinking": {"type": "disabled"},
            },
            timeout=60,
        )
        if not resp.ok:
            # resp.raise_for_status() alleen geeft "400 Client Error" zonder te
            # laten zien WAAROM - printen we hier alsnog, anders is een fout
            # als een verkeerde/verlopen modelnaam niet te diagnosticeren uit
            # de GitHub Actions-log.
            print(f"[FOUT] Anthropic API gaf {resp.status_code} terug:")
            print(resp.text)
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


def generate_and_check(shape_key, topic_hint, audience="algemeen", recent_titles=None,
                        recent_items=None, handle="@smarthealthfix"):
    system_prompt = build_system_prompt(shape_key, audience, handle=handle)
    user_prompt = f"Onderwerp/invalshoek: {topic_hint}\n\nSchrijf nu de content volgens het schema."
    if recent_titles:
        titles_list = "\n".join(f"- {t}" for t in recent_titles)
        user_prompt += (
            f"\n\nBelangrijk: deze titels/invalshoeken zijn recent al gebruikt, "
            f"kies een merkbaar andere invalshoek (niet gewoon een synoniem van "
            f"hetzelfde idee):\n{titles_list}"
        )
    if recent_items:
        items_list = ", ".join(recent_items)
        user_prompt += (
            f"\n\nNOG BELANGRIJKER: deze specifieke voedingsmiddelen/voedingsstoffen/"
            f"klachten/organen zijn recent al gebruikt in dit account (over meerdere "
            f"reels heen, ongeacht de vorm). Vermijd ze zoveel mogelijk en kies "
            f"echt andere, ook minder voor de hand liggende opties - niet steeds "
            f"dezelfde 'bekendste' 5-6 terugpakken:\n{items_list}"
        )
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
