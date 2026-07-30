"""
refresh_token.py — ververst je long-lived Instagram token voordat hij
verloopt (elke ~60 dagen). Zet dit als cronjob elke 45 dagen, zodat je nooit
te laat bent.

    0 3 1 * * cd /pad/naar/pipeline && python3 refresh_token.py >> refresh.log 2>&1
"""

import os
import requests
from dotenv import load_dotenv, set_key

load_dotenv()
ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")


def refresh():
    current_token = os.environ["IG_ACCESS_TOKEN"]
    resp = requests.get(
        "https://graph.instagram.com/refresh_access_token",
        params={"grant_type": "ig_refresh_token", "access_token": current_token},
    )
    resp.raise_for_status()
    data = resp.json()
    new_token = data["access_token"]
    set_key(ENV_PATH, "IG_ACCESS_TOKEN", new_token)
    print(f"Token ververst, geldig voor nog ~{round(data.get('expires_in', 0) / 86400)} dagen.")


if __name__ == "__main__":
    refresh()
