"""
instagram_publish.py — de daadwerkelijke upload-stap. Verwacht dat de
video/cover al ergens publiek bereikbaar staan (zie hosting-vraag in de chat)
en gebruikt je IG_ACCESS_TOKEN / IG_USER_ID uit .env.
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

IG_ACCESS_TOKEN = os.environ.get("IG_ACCESS_TOKEN")
IG_USER_ID = os.environ.get("IG_USER_ID")
GRAPH_BASE = "https://graph.instagram.com/v21.0"


def publish_reel(video_url, caption, cover_url=None, audio_name=None,
                  poll_interval=10, max_polls=30):
    """video_url en cover_url moeten publiek bereikbare HTTPS-links zijn
    (jouw hosting/server), niet lokale bestandspaden."""
    if not IG_ACCESS_TOKEN or not IG_USER_ID:
        raise RuntimeError("IG_ACCESS_TOKEN / IG_USER_ID ontbreken in .env — "
                            "draai eerst oauth_setup.py.")

    # 1) Container aanmaken
    params = {
        "media_type": "REELS",
        "video_url": video_url,
        "caption": caption,
        "access_token": IG_ACCESS_TOKEN,
    }
    if cover_url:
        params["cover_url"] = cover_url
    if audio_name:
        params["audio_name"] = audio_name

    resp = requests.post(f"{GRAPH_BASE}/{IG_USER_ID}/media", params=params)
    resp.raise_for_status()
    container_id = resp.json()["id"]
    print(f"[1/3] Container aangemaakt: {container_id}")

    # 2) Pollen tot Instagram de video verwerkt heeft
    for attempt in range(max_polls):
        status_resp = requests.get(
            f"{GRAPH_BASE}/{container_id}",
            params={"fields": "status_code", "access_token": IG_ACCESS_TOKEN},
        )
        status_resp.raise_for_status()
        status = status_resp.json().get("status_code")
        print(f"[2/3] Status ({attempt+1}/{max_polls}): {status}")
        if status == "FINISHED":
            break
        if status == "ERROR":
            raise RuntimeError(f"Instagram kon de video niet verwerken: {status_resp.json()}")
        time.sleep(poll_interval)
    else:
        raise TimeoutError("Video was na te veel pogingen nog niet 'FINISHED'.")

    # 3) Publiceren
    publish_resp = requests.post(
        f"{GRAPH_BASE}/{IG_USER_ID}/media_publish",
        params={"creation_id": container_id, "access_token": IG_ACCESS_TOKEN},
    )
    publish_resp.raise_for_status()
    media_id = publish_resp.json()["id"]
    print(f"[3/3] Gepubliceerd! media_id={media_id}")
    return media_id


if __name__ == "__main__":
    # Voorbeeldaanroep — vervang door je eigen publieke URL's om te testen.
    publish_reel(
        video_url="https://jouwdomein.nl/output/reel_voorbeeld.mp4",
        cover_url="https://jouwdomein.nl/output/cover_voorbeeld.png",
        caption="Did you know these food facts? 🥑 #healthyeating #wellness",
    )
