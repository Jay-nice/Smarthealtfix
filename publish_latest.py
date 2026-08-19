"""
publish_latest.py — draait als aparte stap ná het pushen naar GitHub (zodat
GitHub Pages de bestanden al kan serveren). Leest output/last_run.json (weg-
geschreven door run_pipeline.py) en publiceert die reel naar Instagram.
"""

import json
import os

from instagram_publish import publish_reel
from cover_state import confirm_bg_used  # Pillow-vrij, veilig in deze lichtgewicht job (zie cover_state.py)


def main():
    public_base_url = os.environ["PUBLIC_BASE_URL"].rstrip("/")

    with open("output/last_run.json") as f:
        last_run = json.load(f)

    video_url = f"{public_base_url}/{last_run['mp4']}"
    cover_url = f"{public_base_url}/{last_run['cover']}"

    print(f"Video URL:  {video_url}")
    print(f"Cover URL:  {cover_url}")

    media_id = publish_reel(video_url=video_url, cover_url=cover_url,
                             caption=last_run["caption"],
                             hashtags_comment=last_run.get("hashtags_comment"))
    print(f"Gepubliceerd, media_id={media_id}")

    # Pas NU, met een bevestigde (of al bestaande) publicatie in de hand, leggen
    # we de gebruikte cover-achtergrondkleur vast voor de groen/wit-afwisseling.
    # Dit draait bewust pas hier en niet al tijdens het genereren: als het
    # genereren zelf lukt maar publiceren daarna (op alle 3 pogingen) mislukt,
    # mag de afwisseling NIET al doorgeschoven zijn naar een kleur die in
    # werkelijkheid nooit op je profiel verschenen is.
    cover_bg = last_run.get("cover_bg")
    if cover_bg:
        confirm_bg_used(cover_bg)
        print(f"[i] Cover-kleur '{cover_bg}' bevestigd voor de groen/wit-afwisseling.")
    else:
        print("[i] Geen cover_bg gevonden in last_run.json (oudere run) - "
              "kleur-afwisseling niet bijgewerkt.")


if __name__ == "__main__":
    main()
