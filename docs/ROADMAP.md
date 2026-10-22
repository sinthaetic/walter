# WALTER – roadmap (okt 2026)

Designskiss (privat): https://claude.ai/artifact/P3oRJT7DMLcQqQa7k8ETu2
Ta en ny Claude-session per steg. Modellförslaget står vid varje steg.

## Beslut som är tagna
- Lägen för användaren: Vilar / Avvaktar / Köper lite / Köper. Max 75 % investerat, aldrig "all in".
- Design: clean Walter från Alien: Covenant. Ljust standard + mörkt läge. Se CLAUDE.md.
- Startkapital: valfri summa, ingen fast skala (småsparare och miljonärer). Allt mäts i procent.
- Logo: "Inskriven" hexagon-W (vald 22 okt). Filer i assets/logo/vald/.
- W-Cipher (Walter Cipher): egen oscillator byggd på VuManChu Cipher A/B (gratis, öppen källkod) men med Walters parametrar och design. Licensen kontrolleras innan kod kopieras.

## Ordning

| # | Steg | Modell |
|---|---|---|
| 1 | ✓ Adaptiv layout i skissen: mobil, surfplatta, dator (klar 22 okt) | Opus |
| 2 | ✓ Logoskisser: hexagon-W och kretskorts-W, vald: "Inskriven" (klar 22 okt) | Opus |
| 3 | ✓ Inställningar: valfri summa, sparmål, tidslinje. Tradelogg och rapporthistorik i skissen (klar 22 okt) | Sonnet |
| 4 | ✓ Pro-läge: varje lampas värde, gräns, källa, tid, dagens priser (klar 22 okt) | Sonnet |
| 5 | ✓ W-Cipher: parametrar föreslagna, skiss klar, och en fungerande sida `cipher.html` med livedata från 5 börser + Pine Script för TradingView (klar 22 okt, parametrar väntar på ditt ja) | Opus |
| 6 | ✓ K4-underlag i ny design (klar 22 okt) | Sonnet |
| 7 | ✓ Designen inbyggd i riktiga koden: index.html med flikarna Översikt, Pro, Logg, K4, Inställningar + W-CIPHER i menyn, nya logon, ljust/mörkt, mobil. cipher.html publiceras nu också (klar 22 okt) | Opus |
| 8 | Logikluckor: trade-motor för paper, buffert 7/6, Sharpe (räknas utan flows). ~~Level 3 i procent~~ klart 22 okt | Opus |

## W-Cipher (steg 5, förslag)
- Grafen: Heikin-Ashi-ljus + trendband (Cipher A) överst, vågen + pengaflöde (Cipher B) under.
- Vågen (WaveTrend): 9 / 12 / 3 på hlc3, samma som VuManChu.
- Starka zoner bara vid ±60 (VuManChu har även 53). Färre, lugnare signaler.
- Pengaflöde (MFI-yta): 60 perioder, ×150, samma som VuManChu.
- Trendband: EMA 5, 11, 15, 18, 21, 24, 28, 34 (VuManChu Cipher A). Inte bekräftat mot originalkoden: en webbsökning 22 okt hittade inte originalet, bara en annan öppen version med 5, 11, 15, 18, 21, 25, 29, 33. Kolla inställningarna i originalskriptet på TradingView.
- Bara vanliga divergenser, inga dolda. Stoch RSI av i V1.
- Standard-tidsram: DAG (15 min, 1 tim, 4 tim och vecka valbara).
- Två visningar: WALTER (lugn, bara starka signaler, text i vanliga ord) och CIPHER (som Market Cipher/VuManChu: köp/sälj/guld-prickar, grönt/rött pengaflöde, VWAP, Stoch RSI, divergenslinjer, KÖP/SÄLJ/BLOD i prisgrafen). Röd/grön i Cipher-läget är ett medvetet undantag från färgregeln.
- Raden "Walter säger / Cipher säger" visar båda, så man kan köra hybrid på egen hand.
- Livedata: Binance, Coinbase, Kraken, Bybit, OKX (öppna flöden, ingen nyckel), uppdateras var 15:e sekund. Aktier/index finns inte än (de saknar öppna flöden som funkar i webbläsaren).
- TradingView: `tradingview/w-cipher.pine` (B) och `w-cipher-a.pine` (A). Inte testade inne i TradingView än.
- W-Cipher ändrar aldrig läget. Den är Walters andra åsikt i text, inte en lampa.
- Licens: originalet är märkt "© vumanchu" och bygger på LazyBears WaveTrend. Vi kopierar ingen kod, vi skriver egen kod från de öppna formlerna.

## Regelgranskning (22 okt, alla 14 förslag godkända)
- Fel rättade: en upplåsningsregel för Level 2 (tidig ELLER normal väg), Sharpe borttaget tills det finns data, ETH-villkoret "SOPR < 1" bytt mot "högst 4 röda lampor", insättningar märkta med `flow`, paper-testet märkt `test`, gammal data blir "väntar".
- Lamporna mäter trend och nivå i stället för enstaka dagar (se CLAUDE.md). Nasdaq och Dow borta, BTC-trend och BTC-vecka in.
- Level 3: +50 % marknadsvinst i stället för 500 000 kr. Guld = skydd vid oro, får köpas även när Walter vilar.
- MVRV-Z-gränsen: 3,0, testad på 13 års historik (Coin Metrics, egen uträkning, stämmer med BGeometrics inom ±0,1).
  Topparna krymper: 10,7 (2013), 10,1 (2017), 7,2 (2021), 3,4 (2024). Gamla 7 hade missat senaste cykeln helt.
  3,0 blev röd i varje uppgångscykel och aldrig i en björnmarknad. Den blir röd tidigt (månader före pristoppen), och de två senaste pristopparna kom EFTER MVRV-Z-toppen.
  Därför är MVRV-Z en värmemätare, inte en topp-signal – rätt som en av tio lampor, fel som ensam säljsignal.
  Testade även anpassade gränser (percentil av senaste 2–4 åren): ingen var bättre, flera missade 2024–25.

## Öppna frågor
- Vilka lampnivåer ger Avvaktar, Köper lite och Köper? Beslutas i steg 8. Tills dess översätter app.js bara journalens läge: PARKERA = Vilar, NORMAL = Köper lite, OFFENSIV = Köper (preliminärt).
- Ska W-Cipher någonsin bli en lampa? Nu: nej.
- W-Cipher för aktier/index (Nasdaq, S&P): kräver att hämtaren skriver ljus till en fil. Senare.
