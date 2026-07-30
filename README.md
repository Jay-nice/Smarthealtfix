# Setup — Smart Health Fix reel-pipeline (gratis GitHub-route)

Geen server nodig — GitHub Actions draait het script, GitHub Pages host de
bestanden. Alles hieronder is klikwerk op github.com, geen terminal nodig.

## 1. Instagram-account
Zet je account om naar **Professional (Creator of Business)** — gratis, in de
Instagram-app zelf.

## 2. Meta Developer app aanmaken
1. Ga naar https://developers.facebook.com -> Mijn Apps -> App aanmaken -> "Business".
2. Voeg het product **"Instagram API setup with Instagram login"** toe.
3. Stel een **redirect URI** in — dit wordt straks je eigen GitHub Pages-adres,
   bijv. `https://jouwgebruikersnaam.github.io/reponaam/callback` (hoeft geen
   werkende pagina te zijn, je hebt 'm alleen nodig om de "code" uit de
   adresbalk af te lezen).
4. Noteer je **App ID** en **App Secret** (Instellingen -> Basic).

## 3. Repository aanmaken op GitHub
1. github.com -> New repository -> geef een naam (bijv. `reel-pipeline`) -> **Public** -> Create.
2. Sleep de hele projectmap (deze zip, uitgepakt) in het "upload files"-scherm
   van je nieuwe repository en commit.
   (Public is hier geen probleem: je echte secrets komen NIET in de code te
   staan, die zet je apart bij Settings -> Secrets, zie stap 5.)

## 4. GitHub Pages aanzetten
Settings -> Pages -> Source: "Deploy from a branch" -> branch `main`, map `/ (root)` -> Save.
Je bestanden zijn dan straks bereikbaar op:
`https://jouwgebruikersnaam.github.io/reponaam/output/...`

## 5. Secrets instellen
Settings -> Secrets and variables -> Actions -> "New repository secret" voor elk van:
- `ANTHROPIC_API_KEY`
- `FDC_API_KEY`
- `IG_ACCESS_TOKEN` (krijg je in stap 6)
- `IG_USER_ID` (krijg je in stap 6)

En bij "Variables" (zelfde scherm, ander tabblad) — niet geheim, mag zichtbaar zijn:
- `PUBLIC_BASE_URL` = `https://jouwgebruikersnaam.github.io/reponaam`

## 6. Eenmalige Instagram-login
Dit stapje moet je 1x lokaal draaien (heeft een browser nodig).
```
pip install requests python-dotenv --break-system-packages
cp .env.example .env   # vul META_APP_ID, META_APP_SECRET, IG_REDIRECT_URI in
python3 oauth_setup.py
```
Volg de aanwijzingen, en zet de twee waarden die het script teruggeeft
(`IG_ACCESS_TOKEN`, `IG_USER_ID`) als secrets in GitHub (stap 5).

## 7. Testen
Ga naar de "Actions"-tab van je repository -> "Dagelijkse reel" -> "Run workflow"
(handmatig starten, hoeft niet op het cron-tijdstip te wachten). Bekijk de log
— als er iets misgaat zie je precies bij welke stap.

## 8. Automatisch
Staat al goed: de workflow draait vanzelf 3x per dag (zie de cron-tijden
bovenin `.github/workflows/daily-reel.yml` — let op, die staan in UTC).

## Token-onderhoud
Je Instagram-token verloopt na ~60 dagen. Draai dan lokaal:
```
python3 refresh_token.py
```
en werk de `IG_ACCESS_TOKEN`-secret in GitHub bij met de nieuwe waarde.
(Een reminder hiervoor zetten in je agenda is handiger dan een cronjob, want
dit vereist een handmatige stap — secrets kunnen niet vanuit de workflow
zelf worden aangepast.)

## Waar kijk je als er iets misgaat?
- **Actions-tab** -> laatste run -> logs per stap.
- `review_queue/` in de repo — content die de factcheck niet doorkwam, nooit gepost.
