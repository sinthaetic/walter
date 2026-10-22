# WALTER paper trading tracker V1.13

Statisk frontend (HTML/CSS/JS, ingen build). Öppna `index.html` direkt i webbläsaren.
Frontend läser `data/state.js` (`window.WALTER_STATE`), som GENERERAS – redigera den aldrig för hand.

## Data-flöde
- `data/state.json` – handredigerad: journal, portfölj, mode, level, regler, KPI-lampan. Hämtaren skriver aldrig hit.
- `data/cache.json` – senast hämtade marknadsvärden (skrivs av hämtaren).
- `fetcher/walter_fetch.py` – hämtar, räknar lampor, bygger `state.js` = state.json + cache. `--offline` bygger bara om. `hamta.bat` = dubbelklick.
- Lampornas poäng blir `source: "data"` när alla 10 har värde. Mode ändras ALDRIG automatiskt – bara via journalpost.
- bykaranteli kräver gratis nyckel i `fetcher/.env` (`BYKARANTELI_API_KEY`). FRED svarar ofta inte → reserv Yahoo `^TNX`. BGeometrics gratis = ~7 dagar fördröjt.
- MVRV-Z-gränsen (7) i `rules.lampThresholds` är ett antagande, inte en dokumenterad WALTER-regel.

## Regler (strategi)
- PARKERA när 7/10 lampor är risk-off.
- Level 1: BTC max 35 %, kontant minst 25 % alltid.
- Level 2: ETH 20 %, låst tills BTC LONG + ETH/BTC över 30d MA + SOPR < 1,0.
- Level 3: Guld 20 % (PAXG/XAUT) när DXY > 105 + 10Y > 4,5 % + VIX > +10 %.
- Max 75 % investerat.
- Upplåsning tidig: +20 %, 15 dagar, DD < 8 %, 7/10 gröna. Normal: 30 dagar, +10 %, DD < 12 %, Sharpe > 1.
- Procenten är MARKNADSVINST över alla insättningar (startkapital + `capitalChange.manualTopUp`). Insättningar låser aldrig upp.
- `levels` i state.json: Level 2 låses upp vid +20 % marknadsvinst, Level 3 vid 500 000 kr där resten är marknadsvinst. Beloppen räknas från insättningarna, sparas aldrig fast.
  ETH/guld-villkoren ovan gäller först efter upplåsning (släckta innan).

## W-Cipher (`cipher.html`)
- Egen sida: `js/wcipher.js` (ren matte, inga DOM-anrop) + `js/cipher-app.js` (börser, graf, text) + `css/cipher.css` (nya designen).
- Hämtar ljus direkt i webbläsaren från Binance/Coinbase/Kraken/Bybit/OKX, ritar med Lightweight Charts 5.0.0 (unpkg, med integrity-hash).
- Samma parametrar finns i `tradingview/*.pine`. Ändras en parameter ska båda ändras.
- W-Cipher ändrar ALDRIG Walters läge. Egen kod från öppna formler – kopiera inte VuManChu-kod.

## Data (bara gratis)
yfinance (^IXIC ^GSPC ^DJI ^VIX), FRED DGS10, BGeometrics (MVRV-Z, SOPR), bykaranteli (ETF-flöden), CoinGecko. Inga dyra API:er.

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
Det är OK att ta fram och byta logos (ändrat okt 2026). Filer i `assets/logo/` (symbol, wordmark, full).
Spåren just nu: hexagon-W och kretskorts-W, i samma rena designspråk. Ingen regnbågs-gradient.

## Journal = sanning
Journalposter i `state.js` är facit. Hitta inte på marknadsdata; okänt värde = `null` ("väntar på data").
