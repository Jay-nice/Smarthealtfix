name: Diagnose Instagram-koppeling

# Handmatig te starten via het Actions-tabblad. Post NIETS - leest alleen,
# om uit te vinden waar de "API access blocked"-blokkade precies zit.

on:
  workflow_dispatch: {}

jobs:
  diagnose:
    runs-on: ubuntu-latest
    steps:
      - name: Repository ophalen
        uses: actions/checkout@v4
        with:
          ref: main

      - name: Python installeren
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Dependencies installeren
        run: pip install requests python-dotenv

      - name: Diagnose draaien
        env:
          IG_ACCESS_TOKEN: ${{ secrets.IG_ACCESS_TOKEN }}
          IG_USER_ID: ${{ secrets.IG_USER_ID }}
        run: python3 diagnose_instagram.py
