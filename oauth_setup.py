"""
oauth_setup.py — EENMALIG uit te voeren op jouw eigen machine/server, om een
Instagram access token te krijgen. Draait lokaal, print het resultaat lokaal
— je hoeft niets hiervan met mij te delen.

Gebruikt de "Instagram API met Instagram Login" (geen Facebook-account nodig).

Voorwaarden voor je draait:
1. Je Instagram-account is een Business of Creator account.
2. Je hebt een Meta Developer-app aangemaakt met het product
   "Instagram API setup with Instagram login" toegevoegd.
3. Je hebt daar een "redirect URI" ingesteld (bijv. https://jouwdomein.nl/instagram/callback)
   — dit hoeft geen werkende pagina te zijn, je hebt 'm alleen nodig om zo
   dadelijk de "code" uit de browser-URL te kunnen aflezen.
4. .env is ingevuld met MET_APP_ID, META_APP_SECRET, IG_REDIRECT_URI.

Gebruik:
    python3 oauth_setup.py
"""

import os
import webbrowser
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

load_dotenv()

APP_ID = os.environ["META_APP_ID"]
APP_SECRET = os.environ["META_APP_SECRET"]
REDIRECT_URI = os.environ["IG_REDIRECT_URI"]

SCOPES = "instagram_business_basic,instagram_business_content_publish"


def step1_open_auth_url():
    params = {
        "client_id": APP_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": SCOPES,
    }
    url = f"https://www.instagram.com/oauth/authorize?{urlencode(params)}"
    print("\n[1] Open deze URL, log in met je Instagram-account, en keur de "
          "permissies goed:\n")
    print(url)
    try:
        webbrowser.open(url)
    except Exception:
        pass
    print("\nJe wordt daarna doorgestuurd naar je redirect_uri met een "
          "'?code=...' erachter in de adresbalk (de pagina zelf mag een "
          "foutmelding/404 tonen, dat maakt niet uit — je hebt alleen de "
          "'code' uit de URL nodig).")


def step2_exchange_code(code):
    resp = requests.post(
        "https://api.instagram.com/oauth/access_token",
        data={
            "client_id": APP_ID,
            "client_secret": APP_SECRET,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
            "code": code,
        },
    )
    resp.raise_for_status()
    data = resp.json()
    return data["access_token"], data["user_id"]


def step3_exchange_for_long_lived(short_token):
    resp = requests.get(
        "https://graph.instagram.com/access_token",
        params={
            "grant_type": "ig_exchange_token",
            "client_secret": APP_SECRET,
            "access_token": short_token,
        },
    )
    resp.raise_for_status()
    data = resp.json()
    return data["access_token"], data.get("expires_in")


if __name__ == "__main__":
    step1_open_auth_url()
    code = input("\n[2] Plak hier de 'code' waarde uit de adresbalk: ").strip()

    short_token, user_id = step2_exchange_code(code)
    print(f"\n[3] Short-lived token verkregen voor IG user_id={user_id}")

    long_token, expires_in = step3_exchange_for_long_lived(short_token)
    days = round((expires_in or 0) / 86400)
    print(f"\n[4] Long-lived token verkregen (geldig ~{days} dagen).")

    print("\n" + "=" * 60)
    print("Zet deze twee regels in je .env bestand:")
    print(f"IG_ACCESS_TOKEN={long_token}")
    print(f"IG_USER_ID={user_id}")
    print("=" * 60)
    print("\nLet op: deze token verloopt over ~60 dagen. Draai "
          "refresh_token.py periodiek (bijv. elke 45 dagen via cron) om 'm "
          "geldig te houden — zie dat bestand.")
