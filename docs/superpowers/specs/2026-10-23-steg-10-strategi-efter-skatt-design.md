# Steg 10 – Walters strategi mätt efter skatt och avgifter (design)

23 okt 2026. Ägaren: "maximera vinst, men även vad som finns kvar efter alla skatter och avgifter, slutligen på mitt svenska bankkonto."
Meta AI påstod att strategin testats mot historik 2022–2026. Det finns inget sådant test i repot. Det här steget gör testet på riktigt,
så långt bakåt som data finns, och byter bara regler som vinner på data de inte är inställda på.

## Mål
1. Ett historiktest (`backtest/`) som kör Walter dag för dag och räknar allt i kronor: börsavgift, prisglidning, växling, uttag till bank och svensk skatt.
2. Svar på: slår dagens regler enkla alternativ efter skatt och avgifter? Vilka ändringar hjälper?
3. Regler som bevisat sig byggs in i både `fetcher/walter_paper.py` och `js/engine.js` (paritet som i steg 9).
4. En rapport i vanlig svenska (`docs/BACKTEST.md`) med siffror, osäkerhet och vad som inte gick att testa.

## Inte med
- Live-handel, SOL och andra valutor (eget steg).
- Ändra ägarens grundregler: max 75 % investerat, aldrig "all in", lägena Vilar/Avvaktar/Köper lite/Köper.
- Optimera tills historiken passar perfekt (överanpassning).

## Anti-mål
- En siffra som ser bra ut men bygger på data som inte fanns den dagen (framtidsläcka).
- Påstå säkerhet som inte finns. Varje slutsats får ett ärligt "så säkert är det".

## Data (bara gratis, som resten av Walter)
| Serie | Källa | Från ca |
|---|---|---|
| BTC pris + MVRV-Z | Coin Metrics Community (redan i hämtaren) | 2010 |
| ETH pris | Coin Metrics Community | 2015 |
| Guld (för PAXG före 2019) | yfinance `GC=F` | 2000 |
| S&P 500, VIX, DXY, 10Y | yfinance `^GSPC ^VIX DX-Y.NYB ^TNX` | 1990-tal |
| USD/SEK, EUR/SEK | FRED `DEXSDUS`/`DEXUSEU` eller Riksbanken | 1990-tal |
| SOPR | BGeometrics (gratis ~4 år) | ca 2022 |
| ETF-flöden | bykaranteli | 2024 |
| KPI mot förväntan | finns inte gratis historiskt | – |

Lampor utan data en viss dag räknas som "saknas", aldrig gissade. Läget räknas då på andelen röda bland lampor som har data,
omräknat till tio (t.ex. 2 röda av 6 → 3,3 av 10, avrundat uppåt = försiktigt). Rapporten visar hur många lampor som fanns varje period.
Ingen framtidsläcka: varje lampa använder bara värden med datum ≤ dagen (MVRV-Z och SOPR med samma fördröjning som i dag).

## Kostnader och skatt (svenska regler, Skatteverket)
- Per affär: börsens taker + 0,2 % prisglidning (som `js/exchanges.js`). Standard i testet: Kraken 0,80 % och Bitstamp 0,40 %, plus Safello (SEK, 0,6 %).
- Växling SEK↔EUR bara vid insättning och uttag, inte per affär (rättar dagens modell).
- Skatt: 30 % på vinst vid varje försäljning, omkostnad med genomsnittsmetoden. Förluster dras av till 70 % mot vinster samma år (kvittning per kalenderår, förenklat). Skatten betalas från portföljen året efter.
- Slutvärde = allt sålt sista dagen, skatt betald, uttag till svensk bank (SEPA + växling) = kronor på kontot.

## Jämförelser
- A: Dagens Walter (exakt dagens regler, levels, guld).
- B: Köp och behåll BTC med samma 35 %-tak (resten kontant).
- C: Köp och behåll BTC 75 % (taket för "aldrig all in").
- Varianter av Walter, en ändring i taget: buffert mellan alla lägen; ombalansering bara när andelen glidit mer än X procentenheter; inga delförsäljningar vid NORMAL↔OFFENSIV (bara sälj vid Vilar); lugnare guldregel (krav flera dagar i rad) eller ingen guld; levels av (ETH direkt) vs på; växlingsmodellen rättad.

## Metod mot överanpassning
- Ställ in på 2013–2019, kontrollera på 2020–idag (data varianten aldrig sett). Bara varianter som vinner i båda perioderna efter skatt och avgifter får in.
- Startdatumskänslighet: starta testet varje kvartal och redovisa spridningen, inte bara bästa start.
- Mått: kronor på bankkontot per 100 000 kr, årlig avkastning efter skatt, största nedgång, antal affärer, betald skatt och avgifter.

## Leverans
- `backtest/` (Python, stdlib + redan installerade beroenden): `data.py` (hämtar och cachar till `backtest/cache/`, gitignorerad), `lamps.py` (lamporna historiskt), `sim.py` (dag-för-dag, använder `walter_paper`s regler så att testet och Walter aldrig skiljer sig), `costs.py` (avgifter + skatt), `run.py` (alla jämförelser → `docs/BACKTEST.md`).
- Tester för skatteräkningen (genomsnittsmetod, 70 %-avdrag, årsvis), framtidsläcka (en lampa får aldrig se morgondagens värde) och att sim med dagens regler ger samma affärer som `walter_paper.propose` på samma dag.
- Vinnande ändringar in i `rules` (state.json), `walter_paper.py`, `js/engine.js`, paritetsfixturer uppdaterade.
