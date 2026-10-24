# WALTER paper trading tracker V2.0

Statisk frontend (HTML/CSS/JS, ingen build). Öppna `index.html` direkt i webbläsaren.
Frontend läser `data/market.js` (`window.WALTER_MARKET`, publik marknad) och, med ägarens kod, `data/owner.enc` (krypterad). `data/state.js` (`window.WALTER_STATE`) finns bara lokalt hos ägaren och publiceras aldrig. Båda .js-filerna GENERERAS – redigera dem aldrig för hand.

## Data-flöde
- `data/state.json` – handredigerad (ägaren): journal, portfölj, mode, level, regler, KPI-lampan. Hämtaren skriver aldrig hit. Går ALDRIG till GitHub okrypterad (gitignorerad).
- `data/state.enc` – state.json låst med `WALTER_OWNER_KEY` (`fetcher/walter_vault.py`: `ny-kod` | `las` | `las-upp` | `sla-ihop`). Det är den som ligger i repot; Actionen låser upp den med Secret.
- `data/cache.json` – senast hämtade marknadsvärden (publik, skrivs av hämtaren).
- `data/owner-cache.json` – ägarens privata dagsvärden och notis (gitignorerad; publiceras bara krypterad).
- `fetcher/walter_fetch.py` – hämtar, räknar lampor, bygger `state.js` (bara lokalt, ägarens hela bild) = state.json + cache, och `data/market.js` via `fetcher/walter_public.py` (publik, bara marknaden: lamps, mode, px, usdsek, eursek, rules, levels, version, `log` = dagsrader). `--offline` bygger bara om. `hamta.bat` = dubbelklick.
- Lampornas poäng blir `source: "data"` när alla 10 har värde. Mode (väderrapporten) ändras bara via journalpost – men Walter handlar själv i GitHub Actionen (`walter_paper.py --auto`) högst en gång per dag och skriver då journalposten med `auto: true`. Bara Actionen handlar själv, aldrig `hamta.bat`.
- `fetcher/walter_paper.py` = trade-motorn. Hämtaren räknar förslaget (`state.proposal`), dagens värde och Sharpe i state.js men handlar aldrig.
  Actionen (`--auto`) skriver läge, `portfolio.positions`, kontanter, historik, journalpost och K4-rad in i state.json, låser state.enc och committar den till main (`[skip ci]`). `paper.bat` finns kvar för att se förslaget och handla manuellt (JA).
  Datorn hämtar Walters affärer själv: `walter_vault.sync_from_repo()` (git pull + las-upp, aldrig i Actionen) körs först i hämtaren, `paper.bat` och deploy.
  `owner-cache.json` → `daily` = portföljvärdet per dag (för Sharpe).
- En lampa vars data är äldre än `rules.lampMaxAgeDays` blir "väntar" (null), så gammal data aldrig räknas som färsk.
- bykaranteli kräver gratis nyckel i `fetcher/.env` (`BYKARANTELI_API_KEY`). FRED svarar ofta inte → reserv Yahoo `^TNX`. BGeometrics gratis = ~7 dagar fördröjt och bara 4 års historik, därför räknas MVRV-Z själv från Coin Metrics Community (gratis, hela historiken, 1 dag efter) med BGeometrics som reserv. SOPR kommer fortfarande från BGeometrics.
- KPI-lampan räknas från `market.cpi` (actual/expected/asOf) som skrivs för hand.

## Lamporna (ändrade 22 okt 2026, se docs/ROADMAP.md)
S&P 500 under 50d-snitt · BTC under 200d-snitt · BTC −10 % på 7 dagar · VIX över 20 · 10Y upp mer än 0,25 %-enheter på en månad ·
Dollarindex över 50d-snitt · ETF-flöde negativt senaste 5 handelsdagarna · KPI högre än väntat · MVRV-Z över 3,0 (testad på 13 års historik, se ROADMAP) · SOPR 7d-snitt under 1.
Trend och nivå, inte enstaka dagar. Gränserna står i `rules.lampThresholds`.

## Regler (strategi) – autopiloten sedan 23 okt 2026 (steg 10, docs/BACKTEST.md)
- `rules.strategy`: `"autopilot"` (standard, även när fältet saknas) eller `"lamps"` (den gamla lamp-strategin, kvar för jämförelser).
- Autopiloten: fasta andelar = `rules.caps` (BTC 35 %, ETH 20 %, guld/PAXG 20 %, resten kontant, minst `rules.minCash` 25 %).
  Beslut bara på `rules.decision.weekday` (söndag, svenskt datum). Glidit en tillgång MER än `rules.decision.bandPp` (5) procentenheter
  (minst minTradePct) från sin andel går den hela vägen tillbaka; sälj först, sedan köp. Annars rörs inget.
  Första affären någonsin (`portfolio.firstTrade` saknas) får ske vilken dag som helst. Saknas tillgången på börsen: andel 0, kontant.
  Saknas pris: den tillgången väntar. Missad beslutsdag (ingen körning/loggrad): kollen görs första dagen efter, en gång.
  En klar koll skrivs som journalpost med `check: true` (senaste sådan = senaste kollen); väntar en tillgång på pris görs kollen
  om nästa dag, tyst (ingen journalpost på ikapp-dagar utan affär). Autopiloten handlar på priserna även när lamporna inte är klara.
  Samma kod i `walter_paper.propose`, `js/engine.js` och `backtest/sim.autopilot()` (paritetstest).
- Lamporna och läget räknas och visas fortfarande ("Walters väderrapport", journalens `mode`), men i autopiloten ÄNDRAR DE INGA AFFÄRER
  och Levels låser ingenting. Allt nedan om lägen, ETH-villkor, guldsignal och Levels gäller bara `"strategy": "lamps"`.
- Läge från röda lampor (`rules.modes`): 0–2 = Köper (OFFENSIV, fulla tak), 3–4 = Köper lite (NORMAL, halva taken), 5–6 = Avvaktar (rör inget), 7+ = Vilar (PARKERA, säljer till kontant).
- Buffert: från Vilar vaknar Walter först vid `rules.wakeAtRed` (5) eller färre röda. 6 röda = vilar kvar.
- Avgift per affär = taker + slippage (`rules.withdrawalFees`). Affärer under `rules.paper.minTradePct` (2 %) av portföljen görs inte.
- K4-omkostnad med genomsnittsmetoden (Skatteverkets regel), inte FIFO.
- Level 1 (lamps): BTC max 35 %, kontant minst 25 % alltid.
- Level 2 (ETH 20 %) låses upp av EN av vägarna i `rules.unlock`: tidig (15 dagar, +20 %, DD < 8 %, 7/10 gröna) eller normal (30 dagar, +10 %, DD < 12 %).
  Efter upplåsning köps ETH när BTC LONG + ETH/BTC över 30d MA + högst `rules.ethMaxRed` (4) röda lampor.
- Level 3 (guld 20 %, PAXG/XAUT) låses upp vid +50 % marknadsvinst och DD < 12 % (`levels.3`). Guld är skyddet: köps när oron är hög
  (VIX över 20 eller S&P under 50d-snitt) och får köpas även när Walter vilar (`rules.gold`).
- Max 75 % investerat = summan av alla tak. På Level 1 är taket i praktiken 35 %.
- Procenten är MARKNADSVINST över alla insättningar (startkapital + `capitalChange.manualTopUp`). Insättningar låser aldrig upp. Belopp räknas från procenten, sparas aldrig fast.
- Sharpe (årstakt, riskfri ränta 0) visas först efter 30 dagar riktig handel, räknat från `portfolio.firstTrade`. Insättningar (`flow`) räknas bort.
- `portfolio.history`: insättningar får `"flow": belopp`, paper-testet före start får `"test": true`. Avkastning räknas utan flows.

## Publicering och ägare
- Publikt: `index.html`, `cipher.html`, `css/`, `js/`, `assets/`, `data/market.js`, `data/cache.json`, `data/owner.enc` (krypterad `{state, daily, notis}`). ALLOW-listan och `leak_check` i `fetcher/walter_deploy.py` stoppar allt annat. Se `README_DEPLOY.md`.
- Utan Secret `WALTER_OWNER_KEY` hoppar Actionen över hämtning och publicering (sidan ligger kvar som den var).
- Lokal deploy slår först ihop publicerade `owner.enc` (dagsvärden) och vägrar korta historiken. `WALTER_GLOM_GAMLA_DAGAR=1` är nödutgången vid kodbyte: lägg den ALDRIG i `.env`.
- Boot (`js/boot.js`): `data/state.js` finns → ägare lokalt. Annars `walter.ownerKey` i localStorage (skrivs in under Inställningar) → dekryptera `owner.enc` → ägarens Walter. Annars landning (`js/landing.js`) → användarens Walter eller intro (`js/intro.js`).

## Walter som app (användare, steg 9)
- Allt sparas i webbläsaren: `walter.user` (state), `walter.user.goal`, `walter.user.plan`, `walter.ownerKey`. Inget skickas någonstans. Säkerhetskopia/inläsning finns i Inställningar (`js/user-state.js`).
- `js/engine.js` = trade-motorn i JS (samma regler som `walter_paper.py`), `catchUp` spelar upp missade loggdagar från `market.js` → `log` och visar en ikapp-notis. Ny användare: Walter gör sitt första drag samma dag.
- `js/exchanges.js`: 5 MiCA-börser (Bitstamp, Bybit EU, Kraken, OKX Europe, Safello) med avgift, tillstånd och källa/datum. Alla avgifter är paper, inga riktiga pengar.
- `js/vault.js` = dekryptering i webbläsaren (samma format som `walter_vault.py`).
- Appens vy för användare: förklaringar i vanliga ord, "Siffrorna", Pro-läge, "Live: inte än".
- Tester: `python -m unittest discover -s tests -v` och `tests/js/run.html` (via lokal server).

## W-Cipher (`cipher.html`)
- Egen sida: `js/wcipher.js` (ren matte, inga DOM-anrop) + `js/cipher-app.js` (börser, graf, text) + `css/cipher.css` (nya designen).
- Hämtar ljus direkt i webbläsaren från Binance/Coinbase/Kraken/Bybit/OKX, ritar med Lightweight Charts 5.0.0 (unpkg, med integrity-hash).
- Samma parametrar finns i `tradingview/*.pine`. Ändras en parameter ska båda ändras.
- W-Cipher ändrar ALDRIG Walters läge. Egen kod från öppna formler – kopiera inte VuManChu-kod.

## Data (bara gratis)
yfinance (^IXIC ^GSPC ^VIX DX-Y.NYB), FRED DGS10, Coin Metrics Community (MVRV-Z), BGeometrics (SOPR, reserv för MVRV-Z), bykaranteli (ETF-flöden), CoinGecko. Inga dyra API:er.

## Design (ny riktning okt 2026 – se docs/ROADMAP.md)
- Walter från Alien: Covenant: clean, städad, metodisk, alltid exakt info. Ljust tema som standard + knapp för mörkt.
- Dimmig blågrå/teal ton, frostade glaspaneler, Jost med luftig spärrning (W A L T E R), siffror i JetBrains Mono, teal som Walters accent.
- Färg sparsamt: röd/grön bara i lampor och läge, blurple för Avvaktar.
- Lugn rörelse: ljussvep, andande ljusring, lampor med sken. Respektera prefers-reduced-motion.
- Lägen för användaren: Vilar / Avvaktar / Köper lite / Köper (aldrig "all in", max 75 % investerat).
- Fasta höjder där innehåll byts, så att inget hoppar.
- INTE Kraken Pro order book.
- Notiser skrivs till en vanlig människa, inte en siffervägg. Siffror får ligga bakom "Siffrorna".

## LOGOS
Det är OK att ta fram och byta logos (ändrat okt 2026). Vald logo ("Inskriven" hexagon-W) ligger i `assets/logo/vald/` och används av index.html och cipher.html.
Spåren just nu: hexagon-W och kretskorts-W, i samma rena designspråk. Ingen regnbågs-gradient.

## Journal = sanning
Journalposter i `state.js` är facit. Hitta inte på marknadsdata; okänt värde = `null` ("väntar på data").
