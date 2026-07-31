"""
instagram_publish.py — de daadwerkelijke upload-stap. Verwacht dat de
video/cover al ergens publiek bereikbaar staan en gebruikt je
IG_ACCESS_TOKEN / IG_USER_ID uit .env.

Bevat retry-met-backoff rondom de container-creatie en het publiceren, zodat
tijdelijke Meta-blokkades ("API access blocked.", rate-limits, 5xx) de hele
run niet meer laten crashen. Echte fouten (verlopen token e.d.) stoppen wel
meteen.
"""

import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

IG_ACCESS_TOKEN = os.environ.get("IG_ACCESS_TOKEN")
IG_USER_ID = os.environ.get("IG_USER_ID")
GRAPH_BASE = "https://graph.instagram.com/v21.0"

# Meta-foutcodes die "probeer het straks nog eens" betekenen (geen echte fout).
# 1  = onbekende tijdelijke fout        2  = tijdelijke storing
# 4  = app-rate-limit                   17 = user-rate-limit
# 32 = page-rate-limit                  341 = tijdelijke limiet
# 613 = custom-rate-limit
TRANSIENT_ERROR_CODES = {1, 2, 4, 17, 32, 341, 613}
# Sommige tijdelijke blokkades komen als code 200 met deze boodschap binnen.
TRANSIENT_MESSAGES = ("api access blocked", "please reduce the amount", "temporarily blocked")

RETRY_ATTEMPTS = 4          # totaal aantal pogingen per API-call
RETRY_BACKOFF = (10, 30, 60)  # wachttijd (sec) na poging 1, 2, 3


def _is_transient(resp):
    """Bepaal of een mislukte response een tijdelijke Meta-hik is (dan retryen)."""
    if resp.status_code >= 500:
        return True
    try:
        err = resp.json().get("error", {})
    except ValueError:
        return False
    if err.get("code") in TRANSIENT_ERROR_CODES:
        return True
    msg = (err.get("message") or "").lower()
    return any(m in msg for m in TRANSIENT_MESSAGES)


def _post_with_retry(url, params, what):
    """POST met backoff bij tijdelijke fouten. Geeft de gelukte response terug."""
    last_resp = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            resp = requests.post(url, params=params, timeout=60)
        except requests.exceptions.RequestException as e:
            # Netwerkfout = altijd tijdelijk; retryen.
            print(f"[RETRY] Netwerkfout bij {what} (poging {attempt+1}/{RETRY_ATTEMPTS}): {e}")
            if attempt < RETRY_ATTEMPTS - 1:
                time.sleep(RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)])
                continue
            raise

        if resp.ok:
            return resp

        last_resp = resp
        transient = _is_transient(resp)
        print(f"[FOUT] Instagram wees {what} af (status {resp.status_code}, "
              f"{'tijdelijk - retry' if transient else 'definitief'}):")
        print(resp.text)

        if not transient or attempt == RETRY_ATTEMPTS - 1:
            break
        wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
        print(f"[RETRY] Wacht {wait}s en probeer {what} opnieuw "
              f"(poging {attempt+2}/{RETRY_ATTEMPTS})...")
        time.sleep(wait)

    # Alle pogingen op: laat de originele HTTPError opgooien.
    last_resp.raise_for_status()


def publish_reel(video_url, caption, cover_url=None, audio_name=None,
                  poll_interval=10, max_polls=30):
    if not IG_ACCESS_TOKEN or not IG_USER_ID:
        raise RuntimeError("IG_ACCESS_TOKEN / IG_USER_ID ontbreken in .env - draai eerst oauth_setup.py.")

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

    resp = _post_with_retry(f"{GRAPH_BASE}/{IG_USER_ID}/media", params, "het aanmaken van de container")
    container_id = resp.json()["id"]
    print(f"[1/3] Container aangemaakt: {container_id}")

    for attempt in range(max_polls):
        status_resp = requests.get(
            f"{GRAPH_BASE}/{container_id}",
            params={"fields": "status_code", "access_token": IG_ACCESS_TOKEN},
            timeout=60,
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
        raise TimeoutError("Video was na te veel pogingen nog niet FINISHED.")

    publish_resp = _post_with_retry(
        f"{GRAPH_BASE}/{IG_USER_ID}/media_publish",
        {"creation_id": container_id, "access_token": IG_ACCESS_TOKEN},
        "het publiceren",
    )
    media_id = publish_resp.json()["id"]
    print(f"[3/3] Gepubliceerd! media_id={media_id}")
    return media_id


if __name__ == "__main__":
    publish_reel(
        video_url="https://jouwdomein.nl/output/reel_voorbeeld.mp4",
        cover_url="https://jouwdomein.nl/output/cover_voorbeeld.png",
        caption="Did you know these food facts? Check it out. #healthyeating #wellness",
    )
