"""
cover_state.py — de groen/wit-afwisselstand voor de covers, LOS van
generate_cover.py gehouden.

Waarom een apart bestandje: dit wordt zowel aangeroepen tijdens het genereren
(generate_cover.py, draait in de 'maak-reel'-job met Pillow/ffmpeg
geïnstalleerd) als tijdens het publiceren (publish_latest.py, draait in de
lichtgewicht 'publiceer-poging-N'-jobs die BEWUST alleen requests/python-dotenv
installeren, zonder Pillow). Stond deze logica in generate_cover.py (dat
`from PIL import ...` bovenaan heeft), dan crasht publish_latest.py daar met
"ModuleNotFoundError: No module named 'PIL'" zodra het alleen deze twee
functies nodig heeft. Dit bestand heeft geen enkele afhankelijkheid buiten de
Python-standaardbibliotheek, dus is veilig te importeren vanuit beide jobs.
"""

import json
import os

STATE_PATH = "output/cover_state.json"


def peek_next_bg():
    """
    Geeft terug welke kleur de VOLGENDE cover zou moeten krijgen om het
    groen/wit/groen/wit-patroon voort te zetten - puur lezen, schrijft NIETS
    weg. Bewust gesplitst van het daadwerkelijk "bevestigen" (zie
    confirm_bg_used hieronder): op het moment dat we de cover RENDEREN weten
    we nog niet of deze reel straks ook echt succesvol gepubliceerd wordt
    (het genereren kan later in de pipeline alsnog mislukken, of alle 3
    publiceer-pogingen kunnen falen). Zouden we de afwisseling hier al
    vastleggen, dan raakt 'm uit de pas met wat er ECHT op je profiel
    verschijnt zodra zo'n mislukte run een kleur "verbruikt" zonder dat er
    iets gepost is.
    """
    last = "white"  # als er nog niks bekend is, start de EERSTE cover met groen
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH) as f:
                last = json.load(f).get("last_bg", "white")
        except (json.JSONDecodeError, OSError):
            pass
    return "green" if last == "white" else "white"


def confirm_bg_used(bg_choice):
    """
    Legt bg_choice ("green"/"white") pas vast als LAATST GEBRUIKTE kleur.
    Wordt aangeroepen door publish_latest.py, en dan ook alleen nadat
    Instagram bevestigd heeft dat de post echt geplaatst is (of al bleek te
    staan) - dus nooit voor een reel die (nog) niet live staat.
    """
    os.makedirs(os.path.dirname(STATE_PATH) or ".", exist_ok=True)
    with open(STATE_PATH, "w") as f:
        json.dump({"last_bg": bg_choice}, f)
