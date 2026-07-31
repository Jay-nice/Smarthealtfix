"""
diagnose_instagram.py — LEEST ALLEEN, post niets.

Doel: uitvinden WAAR de "API access blocked"-blokkade precies zit.
Er zijn drie mogelijkheden en dit script onderscheidt ze:

  A. Zelfs een simpele leesvraag ("wie ben ik?") wordt geweigerd
     -> de app of het token is als geheel geblokkeerd door Meta.
  B. Lezen werkt, maar publiceren wordt geweigerd
     -> alleen de publicatie-rechten/-functie is geblokkeerd.
  C. Alles werkt hier
     -> dan lag het aan iets tijdelijks of aan de video/cover-URL.
"""

import json
import os
import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ.get("IG_ACCESS_TOKEN")
USER_ID = os.environ.get("IG_USER_ID")
VERSIONS = ["v26.0", "v25.0", "v24.0", "v23.0", "v21.0"]


def toon(resp):
    """Vat een response kort samen."""
    try:
        data = resp.json()
    except ValueError:
        return f"status {resp.status_code}, geen JSON: {resp.text[:200]}"
    if "error" in data:
        e = data["error"]
        return (f"GEWEIGERD (status {resp.status_code}) | code={e.get('code')} "
                f"subcode={e.get('error_subcode')} | {e.get('message')}")
    return f"OK (status {resp.status_code}) | {json.dumps(data)[:250]}"


def probeer(omschrijving, url, params):
    print(f"\n--- {omschrijving}")
    print(f"    {url}")
    try:
        resp = requests.get(url, params=params, timeout=30)
    except requests.exceptions.RequestException as e:
        print(f"    NETWERKFOUT: {e}")
        return False
    print(f"    {toon(resp)}")
    return resp.ok


def main():
    print("=" * 70)
    print("DIAGNOSE INSTAGRAM-KOPPELING (leest alleen, post niets)")
    print("=" * 70)

    if not TOKEN or not USER_ID:
        print("FOUT: IG_ACCESS_TOKEN of IG_USER_ID ontbreekt in de omgeving.")
        return

    print(f"\nToken aanwezig: ja, {len(TOKEN)} tekens, begint met '{TOKEN[:8]}...'")
    print(f"IG_USER_ID:     {USER_ID}")

    # Vanaf welk IP praten we? (alleen ter info)
    try:
        ip = requests.get("https://api.ipify.org", timeout=15).text
        print(f"Uitgaand IP:    {ip}")
    except requests.exceptions.RequestException:
        print("Uitgaand IP:    kon niet bepaald worden")

    resultaten = {}

    print("\n" + "=" * 70)
    print("TEST 1 — Basale leesvraag: 'wie ben ik?' (per API-versie)")
    print("=" * 70)
    for v in VERSIONS:
        ok = probeer(
            f"API {v}: GET /me",
            f"https://graph.instagram.com/{v}/me",
            {"fields": "id,username,account_type", "access_token": TOKEN},
        )
        resultaten[f"me_{v}"] = ok

    print("\n" + "=" * 70)
    print("TEST 2 — Account opvragen via IG_USER_ID (controleert of het ID klopt)")
    print("=" * 70)
    probeer(
        "GET /{IG_USER_ID}",
        f"https://graph.instagram.com/v24.0/{USER_ID}",
        {"fields": "id,username", "access_token": TOKEN},
    )

    print("\n" + "=" * 70)
    print("TEST 3 — Bestaande media uitlezen (leesrecht op content)")
    print("=" * 70)
    probeer(
        "GET /me/media",
        f"https://graph.instagram.com/v24.0/me/media",
        {"fields": "id,media_type,timestamp", "limit": "3", "access_token": TOKEN},
    )

    print("\n" + "=" * 70)
    print("TEST 4 — Staat de publicatielimiet nog open? (leest alleen de teller)")
    print("=" * 70)
    probeer(
        "GET /me/content_publishing_limit",
        f"https://graph.instagram.com/v24.0/{USER_ID}/content_publishing_limit",
        {"fields": "config,quota_usage", "access_token": TOKEN},
    )

    print("\n" + "=" * 70)
    print("CONCLUSIE")
    print("=" * 70)
    lees_ok = any(resultaten.get(f"me_{v}") for v in VERSIONS)
    if not lees_ok:
        print("Zelfs de simpelste leesvraag wordt geweigerd op ALLE versies.")
        print("=> De app of het token is als geheel geblokkeerd door Meta.")
        print("   Kijk in het Meta App Dashboard (developers.facebook.com/apps)")
        print("   of daar een waarschuwing/beperking staat, en of de app nog")
        print("   in Ontwikkelaarsmodus staat met een geldige Testers-rol.")
        print("   Genereer daarna een NIEUW access token.")
    else:
        werkend = [v for v in VERSIONS if resultaten.get(f"me_{v}")]
        print(f"Lezen werkt WEL, op deze versies: {', '.join(werkend)}")
        print("=> Token en app zijn in orde; de blokkade zit specifiek op het")
        print("   publiceren. Zie test 4 hierboven voor de publicatielimiet.")


if __name__ == "__main__":
    main()
