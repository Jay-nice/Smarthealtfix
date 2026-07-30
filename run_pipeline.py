name: Dagelijkse reel

on:
  schedule:
    # Tijden in UTC! Ingesteld op 12:00, 17:00, 22:00 Nederlandse ZOMERtijd (UTC+2).
    # Let op: dit is een vaste UTC-tijd die NIET automatisch meeschuift met de
    # klok. Zodra het in Nederland weer wintertijd wordt (UTC+1, eind oktober),
    # schuiven deze momenten in werkelijkheid 1 uur op (dus dan 13:00/18:00/23:00
    # lokale tijd) — pas dan de cron-regels hieronder met -1 uur aan indien gewenst.
    - cron: "0 10 * * *"
    - cron: "0 15 * * *"
    - cron: "0 20 * * *"
  workflow_dispatch: {}   # handmatig te starten via de "Actions"-tab, handig om te testen

permissions:
  contents: write   # nodig om de gegenereerde bestanden terug te committen

jobs:
  maak-en-post-reel:
    runs-on: ubuntu-latest
    steps:
      - name: Repository ophalen
        uses: actions/checkout@v4

      - name: Python installeren
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: ffmpeg installeren
        run: sudo apt-get update && sudo apt-get install -y ffmpeg

      - name: Dependencies installeren
        run: pip install -r requirements.txt

      - name: Reel genereren (tekst -> factcheck -> afbeelding -> video -> cover)
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
          FDC_API_KEY: ${{ secrets.FDC_API_KEY }}
        run: python3 run_pipeline.py --skip-upload
        # --skip-upload: eerst alleen genereren, dan pushen we de bestanden,
        # en pas daarna (in een aparte stap) publiceren we naar Instagram.
        # Zo staat het bestand al op Pages voordat Instagram ernaar vraagt.

      - name: Gegenereerde bestanden committen en pushen
        run: |
          git config user.name "reel-bot"
          git config user.email "reel-bot@users.noreply.github.com"
          git add -f output/
          git diff --staged --quiet || git commit -m "Nieuwe reel: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
          git push

      - name: Wachten tot GitHub Pages de nieuwe bestanden live heeft
        run: sleep 120   # 2 minuten, ruim voldoende voor een Pages-redeploy

      - name: Publiceren naar Instagram
        env:
          IG_ACCESS_TOKEN: ${{ secrets.IG_ACCESS_TOKEN }}
          IG_USER_ID: ${{ secrets.IG_USER_ID }}
          PUBLIC_BASE_URL: ${{ vars.PUBLIC_BASE_URL }}
        run: python3 publish_latest.py
