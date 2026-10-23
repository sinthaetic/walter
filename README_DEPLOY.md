# WALTER på autopilot

GitHub hämtar data och publicerar sidan åt dig (`.github/workflows/walter-auto.yml`).
Du behöver bara skriva journalposter i `data/state.json` och köra `walter deploy`.

Sidan är publik, men **din** data (journal, portfölj, K4, dagsvärden, notis) publiceras bara krypterad.
Allt annat på sidan är marknaden: lampor, läge, priser och den dagliga loggen.

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

0. **Skapa din åtkomstkod** (låser din data):
   ```
   .venv\Scripts\python.exe fetcher\walter_vault.py ny-kod
   ```
   - Spara koden i din **lösenordshanterare**. Tappar du den går `state.enc` och `owner.enc` inte att öppna.
   - Lägg den i `fetcher/.env`:
     ```
     WALTER_OWNER_KEY=koden-här
     ```
   - Lägg den som GitHub Secret `WALTER_OWNER_KEY` (se steg 4).
   - Lås din data första gången: `.venv\Scripts\python.exe fetcher\walter_vault.py las`.

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
   | `WALTER_OWNER_KEY` | koden från steg 0 | **ja** – annars hämtar och publicerar Actionen ingenting |
   | `NETLIFY_AUTH_TOKEN` | token från steg 3 | för Netlify |
   | `NETLIFY_SITE_ID` | Site ID från steg 3 | för Netlify |
   | `BYKARANTELI_API_KEY` | samma som i `fetcher/.env` | annars uppdateras inte ETF-lampan |
   | `FRED_API_KEY` | samma som i `fetcher/.env` | valfri |

   Saknas Netlify-nycklarna hoppar Actionen bara över Netlify-steget. GitHub Pages fungerar ändå.

5. **Första push**, i mappen `walter`. Utan Secreten `WALTER_OWNER_KEY` (steg 4) hämtar och publicerar Actionen **ingenting** – sidan ligger kvar som den var (eller finns inte än). Vill du publicera innan Secreten finns: kör `walter deploy` lokalt (med koden i `fetcher/.env`). Gamla versioner av `state.json` kan ligga i git-historiken: se öppna frågan i `docs/ROADMAP.md`.
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
   Grenen `gh-pages` skapas av första körningen. Kör därför steg 8 först om den inte syns i listan.

7. **Skriv in koden i mobilen:** öppna sidan → **GÅ IN** → **Har du en kod? Lås upp din Walter** (första rutan) → skriv koden → **LÅS UPP**. Du behöver inte skapa någon egen Walter först. (Har du redan en Walter i den webbläsaren: **Inställningar → Lås upp min Walter**.) Koden sparas bara i den webbläsaren, och bara när den stämmer. Då visas din Walter (journal, K4) på alla enheter där du gjort det. Vill du ta bort den från en enhet: **Inställningar → Glöm koden på den här enheten**.

8. **Provkör:** repot → **Actions → WALTER auto → Run workflow**. En grön bock betyder att sidan är uppdaterad på
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

- **Ny journalpost:** ändra `data/state.json` och kör `walter deploy`. Då låses `state.json` till
  `state.enc`, sidan publiceras direkt och `state.enc` pushas till `main`. Actionen startar också när
  `state.enc` ändras på `main`. `state.json` finns bara hos dig – den går aldrig till GitHub.
- **Ny dator / efter `git pull`:** `.venv\Scripts\python.exe fetcher\walter_vault.py las-upp` ger dig `state.json`.
  Är `state.enc` nyare än din `state.json` vägrar `walter deploy` skriva över den – lås upp först.
- **Paper-affär:** efter JA i `paper.bat` låses `state.json` direkt till `state.enc`.
- `walter hamta` och `walter visa dashboard` fungerar som förut, lokalt.
- Lägesbyten görs fortfarande bara via journalen. Actionen ändrar aldrig `mode`.

## Säkerhet

- Bara `index.html`, `cipher.html`, `css/`, `js/`, `assets/`, `data/market.js`, `data/cache.json` och
  `data/owner.enc` (krypterad) kopieras till `deploy/`. Aldrig `state.js`, `state.json` eller `reports/`.
- **Läckspärren** går igenom `deploy/` före varje publicering. Står `journal`, `portfolio`, `k4`,
  `capitalChange`, `daily`, `notis`, `proposal` eller `WALTER_OWNER_KEY` okrypterat i `deploy/data/`
  (utom i `owner.enc`), eller finns `state.js`, `reports/`, `.env`, `etf_raw.json` med, stoppas allt.
- **Utan kod lokalt:** är `WALTER_PAGES_REPO` satt men `WALTER_OWNER_KEY` saknas i `fetcher/.env` **stoppas** `walter deploy` –
  annars skulle din Walter i mobilen (`owner.enc`) och dagshistoriken försvinna från sidan. Utan `WALTER_PAGES_REPO` (Netlify Drop)
  byggs `deploy/` utan `owner.enc` (bara marknaden) och du får en varning.
- **Marknadsloggen tappas inte:** före varje lokal `walter deploy` hämtas publicerade `cache.json` från `gh-pages` och
  dagarna som Actionen lagt till slås ihop med dina (en klar dag skrivs aldrig över av en halvfärdig).
- **Journalen pushas bara från `main`:** `walter deploy` committar och pushar `state.enc` till `main` (HEAD:main) bara när
  `main` är utcheckad. Står du på en annan gren får du en varning och inget pushas.
- **Utan Secret i Actionen:** saknas `WALTER_OWNER_KEY` som Secret hämtar och publicerar Actionen
  **ingenting**. Körningen blir grön med en varning, och sidan ligger kvar exakt som den var.
- **Dagsvärdena tappas aldrig i tysthet.** Före varje publicering hämtas den publicerade `owner.enc` från
  `gh-pages` och dess dagsvärden/notis slås ihop med dina (både lokalt och i Actionen). Går `gh-pages`
  inte att nå, eller går `owner.enc` där inte att låsa upp, **stoppas publiceringen** med ett besked –
  hellre ingen uppdatering än en kortare historik. Allra första gången (ingen `owner.enc` än) går bra.
- Actionen använder bara `GITHUB_TOKEN` och dina Secrets. Den committar aldrig till `main`. Senaste
  `cache.json` läses tillbaka från `gh-pages` vid varje körning.
- **Byter du kod:** lägg den nya i `fetcher/.env` och i Secreten och kör `walter_vault.py las`. Nästa
  `walter deploy` stoppas, eftersom den publicerade `owner.enc` är låst med den gamla koden. Kör då en gång
  `set WALTER_GLOM_GAMLA_DAGAR=1` och sedan `walter deploy` i samma fönster. Gamla dagsvärden försvinner,
  och efter det fungerar Actionen igen med den nya koden. Lägg **aldrig** `WALTER_GLOM_GAMLA_DAGAR` i `fetcher/.env` – då skulle varje deploy tyst kunna tappa dagshistoriken. Bara i fönstret, en gång.
- GitHub stänger av schemalagda Actions efter 60 dagar utan commits i repot. Kör `walter deploy`
  då och då, eller tryck **Enable workflow** under Actions.
