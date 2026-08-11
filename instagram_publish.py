"""
instagram_publish.py — de daadwerkelijke upload-stap. Verwacht dat de
video/cover al ergens publiek bereikbaar staan en gebruikt je
IG_ACCESS_TOKEN / IG_USER_ID uit .env.

Belangrijk (juli 2026): Meta zet Graph API-versies na ~24 maanden uit. v23.0
is op 9 juni 2026 gesloten, dus alles t/m v23 is dood. Een uitgezette versie
geeft grillige fouten zoals "API access blocked." — eerst af en toe, daarna
altijd. Daarom probeert dit script automatisch meerdere actuele versies tot
er één werkt, en meldt het welke versie het deed. Zo hoef je bij de volgende
sunset (over ~2 jaar) alleen API_VERSIONS bij te werken, of de omgevings-
variabele IG_API_VERSION te zetten.

Dubbele posts voorkomen (augustus 2026): de daily-reel workflow probeert het
publiceren tot 3x op een verse computer als een poging faalt. Instagram's
publiceer-endpoint is NIET idempotent — als een netwerkhikje optreedt vlak
NADAT de post al gelukt is (we krijgen geen bevestiging terug, maar 'm staat
al live), denkt dit script dat het mislukt is en zou de volgende poging een
tweede, identieke post plaatsen. Daarom checkt publish_reel() vóór het
posten eerst of er al een recente post met exact dezelfde caption bestaat,
en slaat het publiceren dan over in plaats van te dupliceren.
"""

import os
import time
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

IG_ACCESS_TOKEN = os.environ.get("IG_ACCESS_TOKEN")
IG_USER_ID = os.environ.get("IG_USER_ID")

# Nieuwste eerst. Bij een blokkade zakt het script automatisch door naar de
# volgende. Zet IG_API_VERSION (bijv. "v26.0") om er eentje af te dwingen.
API_VERSIONS = ["v26.0", "v25.0", "v24.0"]
_forced = os.environ.get("IG_API_VERSION")
if _forced:
    API_VERSIONS = [_forced if _forced.startswith("v") else f"v{_forced}"]

# Hoe recent een bestaande post met dezelfde caption moet zijn om als
# "dat ben ik zelf, net geplaatst" te tellen i.p.v. toeval (een keer eerder
# exact dezelfde tekst gebruikt). Ruim boven de tijd die 1 publiceer-poging
# (incl. polling) kost, ruim onder de tijd tot de volgende geplande post.
DUPLICATE_WINDOW_MINUTES = 180


def _graph_base(version):
    return f"https://graph.instagram.com/{version}"


# Meta-foutcodes die "probeer het straks nog eens" betekenen (geen echte fout).
TRANSIENT_ERROR_CODES = {1, 2, 4, 17, 32, 341, 613}
# Blokkades die op een uitgezette/afgeknepen API-versie wijzen: bij deze
# meldingen heeft het zin om een ANDERE versie te proberen.
VERSION_BLOCK_MESSAGES = ("api access blocked", "version", "deprecat", "no longer supported")

RETRY_ATTEMPTS = 3            # pogingen per versie bij een tijdelijke fout
RETRY_BACKOFF = (10, 30)      # wachttijd (sec) tussen die pogingen


def _describe(resp):
    try:
        err = resp.json().get("error", {})
    except ValueError:
        return {}, ""
    return err, (err.get("message") or "").lower()


def _is_transient(resp):
    if resp.status_code >= 500:
        return True
    err, msg = _describe(resp)
    if err.get("code") in TRANSIENT_ERROR_CODES:
        return True
    return "please reduce the amount" in msg or "temporarily blocked" in msg


def _looks_like_version_block(resp):
    err, msg = _describe(resp)
    if err.get("code") == 2635:          # "API Version Deprecated"
        return True
    return any(m in msg for m in VERSION_BLOCK_MESSAGES)


def _post_on_version(url, params, what):
    """POST met korte backoff bij tijdelijke fouten. Geeft (resp, ok) terug."""
    last = None
    for attempt in range(RETRY_ATTEMPTS):
        try:
            resp = requests.post(url, params=params, timeout=60)
        except requests.exceptions.RequestException as e:
            print(f"[RETRY] Netwerkfout bij {what} (poging {attempt+1}/{RETRY_ATTEMPTS}): {e}")
            if attempt < RETRY_ATTEMPTS - 1:
                time.sleep(RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)])
                continue
            raise
        if resp.ok:
            return resp, True
        last = resp
        if not _is_transient(resp) or attempt == RETRY_ATTEMPTS - 1:
            break
        wait = RETRY_BACKOFF[min(attempt, len(RETRY_BACKOFF) - 1)]
        print(f"[RETRY] Tijdelijke fout bij {what}; wacht {wait}s "
              f"(poging {attempt+2}/{RETRY_ATTEMPTS})...")
        time.sleep(wait)
    return last, False


def _find_recent_duplicate(caption):
    """
    Kijkt of er al een post met EXACT deze caption bestaat, geplaatst binnen
    DUPLICATE_WINDOW_MINUTES. Geeft het media_id terug als die gevonden is,
    anders None. Faalt deze check zelf (netwerk/API-probleem), dan geven we
    gewoon None terug — liever een keer een gemiste duplicate-check dan de
    hele publicatie blokkeren op een check die zelf niet werkt.
    """
    for version in API_VERSIONS:
        try:
            resp = requests.get(
                f"{_graph_base(version)}/{IG_USER_ID}/media",
                params={"fields": "id,caption,timestamp", "limit": 5,
                        "access_token": IG_ACCESS_TOKEN},
                timeout=30,
            )
        except requests.exceptions.RequestException:
            continue
        if not resp.ok:
            continue

        now = datetime.now(timezone.utc)
        for item in resp.json().get("data", []):
            if (item.get("caption") or "") != caption:
                continue
            try:
                posted_at = datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00"))
            except (KeyError, ValueError):
                continue
            age_minutes = (now - posted_at).total_seconds() / 60
            if age_minutes <= DUPLICATE_WINDOW_MINUTES:
                return item["id"], age_minutes
        return None, None  # gelukt gelezen, gewoon geen match - niet bij andere versies nogmaals proberen

    return None, None  # geen enkele versie kon de check uitvoeren


def post_comment(base, media_id, text):
    """
    Plaatst 'text' als comment onder media_id (gebruikt voor de hashtags-in-de-
    eerste-comment aanpak: schonere caption, hashtags staan toch nog gewoon mee
    voor de vindbaarheid). Faalt dit, dan laten we de hele run NIET falen - de
    reel zelf staat dan al live, een ontbrekende hashtag-comment is vervelend
    maar geen reden om de publicatie als mislukt te markeren.
    """
    resp, ok = _post_on_version(
        f"{base}/{media_id}/comments",
        {"message": text, "access_token": IG_ACCESS_TOKEN},
        "het plaatsen van de hashtag-comment",
    )
    if not ok:
        print(f"[WAARSCHUWING] Hashtags als eerste comment plaatsen mislukt "
              f"(de reel zelf staat wel gewoon live): "
              f"{resp.text if resp is not None else '(geen response)'}")
        return None
    comment_id = resp.json().get("id")
    print(f"[i] Hashtags geplaatst als eerste comment (comment_id={comment_id}).")
    return comment_id


def publish_reel(video_url, caption, cover_url=None, audio_name=None,
                  hashtags_comment=None, poll_interval=10, max_polls=30):
    if not IG_ACCESS_TOKEN or not IG_USER_ID:
        raise RuntimeError("IG_ACCESS_TOKEN / IG_USER_ID ontbreken in .env - draai eerst oauth_setup.py.")

    # --- Stap 0: is dit al gepost? (voorkomt duplicaten bij een retry-poging) ---
    existing_id, age_minutes = _find_recent_duplicate(caption)
    if existing_id:
        print(f"[0/3] Deze caption staat al {age_minutes:.0f} min geleden gepost "
              f"(media_id={existing_id}). Publiceren overgeslagen om duplicaat te voorkomen.")
        return existing_id

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

    # --- Stap 1: container aanmaken, versie voor versie tot er één werkt ---
    container_id = None
    working_version = None
    last_resp = None

    for version in API_VERSIONS:
        print(f"[1/3] Container aanmaken via API {version}...")
        resp, ok = _post_on_version(f"{_graph_base(version)}/{IG_USER_ID}/media",
                                    params, f"het aanmaken van de container ({version})")
        if ok:
            container_id = resp.json()["id"]
            working_version = version
            print(f"[1/3] Gelukt op {version}. Container: {container_id}")
            break

        last_resp = resp
        print(f"[FOUT] {version} weigerde het verzoek (status {resp.status_code}):")
        print(resp.text)
        if _looks_like_version_block(resp) and version != API_VERSIONS[-1]:
            print(f"[VERSIE] {version} lijkt geblokkeerd/uitgezet - probeer de volgende versie...")
            continue
        break

    if container_id is None:
        print("[FOUT] Geen enkele API-versie accepteerde het verzoek.")
        print("       Check: (1) is IG_ACCESS_TOKEN nog geldig, (2) staat er een "
              "waarschuwing in het Meta App Dashboard, (3) bestaat er een nieuwere "
              "API-versie? Werk dan API_VERSIONS bij.")
        last_resp.raise_for_status()

    base = _graph_base(working_version)

    # --- Stap 2: wachten tot Instagram de video verwerkt heeft ---
    for attempt in range(max_polls):
        status_resp = requests.get(
            f"{base}/{container_id}",
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

    # --- Stap 2b: vlak vóór publiceren nog één keer checken. Dekt het geval
    # waarbij een EERDERE poging het hier tot en met publiceren schopte, wij
    # geen bevestiging kregen (vandaar dat we opnieuw zijn gestart), maar de
    # post ondertussen al live staat. ---
    existing_id, age_minutes = _find_recent_duplicate(caption)
    if existing_id:
        print(f"[2b/3] Bleek ondertussen al gepost te zijn ({age_minutes:.0f} min geleden, "
              f"media_id={existing_id}). Publiceren overgeslagen.")
        return existing_id

    # --- Stap 3: publiceren (zelfde versie die de container accepteerde) ---
    publish_resp, ok = _post_on_version(
        f"{base}/{IG_USER_ID}/media_publish",
        {"creation_id": container_id, "access_token": IG_ACCESS_TOKEN},
        "het publiceren",
    )
    if not ok:
        print(f"[FOUT] Instagram wees het publiceren af (status {publish_resp.status_code}):")
        print(publish_resp.text)
        publish_resp.raise_for_status()

    media_id = publish_resp.json()["id"]
    print(f"[3/3] Gepubliceerd via {working_version}! media_id={media_id}")

    if hashtags_comment:
        post_comment(base, media_id, hashtags_comment)

    return media_id


if __name__ == "__main__":
    publish_reel(
        video_url="https://jouwdomein.nl/output/reel_voorbeeld.mp4",
        cover_url="https://jouwdomein.nl/output/cover_voorbeeld.png",
        caption="Did you know these food facts? Check it out. #healthyeating #wellness",
    )
