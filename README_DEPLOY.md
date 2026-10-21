# WALTER på autopilot

GitHub hämtar data och publicerar sidan åt dig (`.github/workflows/walter-auto.yml`).
Du behöver bara skriva journalposter i `data/state.json` och köra `walter deploy`.

## Hur ofta den hämtar

| Läge | Hur ofta |
|---|---|
| **PARKERA** | Ungefär var 3:e timme (≈ 7 gånger per dygn) |
| **NORMAL / OFFENSIV**, eller ett innehav i BTC/ETH/guld över 1 000 kr | Var 15:e minut (≈ 69 gånger per dygn) |

Fönstret är 04:00–20:45 UTC, plus en körning kl 23:00 UTC. I svensk vintertid blir det
05:00–21:45 och 00:00. I sommartid blir det 06:00–22:45 och 01:00.
GitHub kan starta schemalagda körningar 5–30 minuter sent.

Innehav på högst 1 000 kr (t.ex. 89 kr i BTC) räknas som damm, inte som öppen position.

## En gång: sätt upp det

1. **Skapa ett tomt GitHub-repo** som heter `walter` på https://github.com/new.
   Gör det **Public**: GitHub Pages och obegränsade Action-minuter är gratis bara för publika repon.
   Sidan är ändå publik, så ingenting nytt blir synligt.
   Lägg inte till README eller .gitignore där, de finns redan här.

2. **Lägg till repot i `fetcher/.env`:**
   ```
   WALTER_PAGES_REPO=https://github.com/MITT-NAMN/walter.git
   ```

3. **Hämta två saker från Netlify:**
   - `NETLIFY_SITE_ID`: app.netlify.com/sites/waltervault/settings/general → **Site ID**
   - `NETLIFY_AUTH_TOKEN`: app.netlify.com/user/applications → **New access token**

4. **Lägg in dem som Secrets i GitHub:** repot → **Settings → Secrets and variables → Actions → New repository secret**.
   | Namn | Värde | Behövs? |
   |---|---|---|
   | `NETLIFY_AUTH_TOKEN` | token från steg 3 | för Netlify |
   | `NETLIFY_SITE_ID` | Site ID från steg 3 | för Netlify |
   | `BYKARANTELI_API_KEY` | samma som i `fetcher/.env` | annars uppdateras inte ETF-lampan |
   | `FRED_API_KEY` | samma som i `fetcher/.env` | valfri |

   Saknas Netlify-nycklarna hoppar Actionen bara över Netlify-steget. GitHub Pages fungerar ändå.

5. **Första push**, i mappen `walter`:
   ```
   git init -b main
   git add .
   git commit -m "WALTER 1.6.3"
   git remote add origin https://github.com/MITT-NAMN/walter.git
   git push -u origin main
   ```
   Kör `git status` före commit. `.env`, `etf_raw.json`, `.venv` och `deploy/` ska **inte** finnas
   med. `.gitignore` stoppar dem.

6. **Slå på GitHub Pages:** repot → **Settings → Pages → Source: Deploy from a branch → `gh-pages` / root**.
   Grenen `gh-pages` skapas av första körningen. Kör därför steg 7 först om den inte syns i listan.

7. **Provkör:** repot → **Actions → WALTER auto → Run workflow**. En grön bock betyder att sidan är uppdaterad på
   `https://MITT-NAMN.github.io/walter/` (och på Netlify om du har lagt in nycklarna).

## Notiser morgon och kväll

Varje dag kl **08:13** och **22:05** (svensk tid) hämtar WALTER färskt och skriver en notis på vanlig svenska, t.ex.
"Morgon 08:13: Cash 254 600 kr vilar, BTC $84 719 (+0,94 % på ett dygn), totalt 254 600 kr. 4/10 lampor röda. Walter håller PARKERA."

- Notisen visas alltid överst på sidan.
- **Telegram (valfritt):** skapa en bot hos @BotFather och lägg in token som secret `TELEGRAM_TOKEN`.
  Skriv sedan något till boten och öppna `https://api.telegram.org/bot<TOKEN>/getUpdates`.
  Där står `"chat":{"id":…}`, och det talet läggs in som secret `TELEGRAM_CHAT_ID`.
- **Testa:** Actions → WALTER auto → Run workflow → välj `morgon` eller `kvall` under "Skicka notis nu".

## Vardag

- **Ny journalpost:** ändra `data/state.json` och kör `walter deploy`. Då publiceras sidan direkt och
  `state.json` pushas till `main`. Actionen startar också när `state.json` ändras på `main`.
  Ändrar du `state.json` direkt på github.com räcker det, Actionen bygger om sidan.
- `walter hamta` och `walter visa dashboard` fungerar som förut, lokalt.
- Lägesbyten görs fortfarande bara via journalen. Actionen ändrar aldrig `mode`.

## Säkerhet

- Bara `index.html`, `css/`, `js/`, `assets/`, `data/state.js` och `data/cache.json` kopieras till `deploy/`.
  `.env` och `etf_raw.json` spärras extra, och hittas de stoppas publiceringen.
- Actionen använder bara `GITHUB_TOKEN` och dina Secrets. Den committar aldrig till `main`. Senaste
  `cache.json` läses tillbaka från `gh-pages` vid varje körning.
- GitHub stänger av schemalagda Actions efter 60 dagar utan commits i repot. Kör `walter deploy`
  då och då, eller tryck **Enable workflow** under Actions.
