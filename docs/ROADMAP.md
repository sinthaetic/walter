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
| 5 | ✓ W-Cipher: VuManChu A/B inläst, parametrar föreslagna, grafvyn i skissen (klar 22 okt, parametrar väntar på ditt ja) | Opus |
| 6 | ✓ K4-underlag i ny design (klar 22 okt) | Sonnet |
| 7 | Bygg in designen i riktiga koden (index.html, css, js), inkl. nya logon från assets/logo/vald | Opus för plan, Sonnet för utförande |
| 8 | Logikluckor: trade-motor för paper, buffert 7/6, Sharpe, Level 3 i procent | Opus |

## W-Cipher (steg 5, förslag)
- Grafen: Heikin-Ashi-ljus + trendband (Cipher A) överst, vågen + pengaflöde (Cipher B) under.
- Vågen (WaveTrend): 9 / 12 / 3 på hlc3, samma som VuManChu.
- Starka zoner bara vid ±60 (VuManChu har även 53). Färre, lugnare signaler.
- Pengaflöde (MFI-yta): 60 perioder, ×150, samma som VuManChu.
- Trendband: EMA 5, 11, 15, 18, 21, 24, 28, 34 (VuManChu Cipher A, kontrolleras mot originalet i steg 7).
- Bara vanliga divergenser, inga dolda. Stoch RSI av i V1.
- Standard-tidsram: DAG (4 tim och vecka valbara).
- W-Cipher ändrar aldrig läget. Den är Walters andra åsikt i text, inte en lampa.
- Licens: originalet är märkt "© vumanchu" och bygger på LazyBears WaveTrend. Vi kopierar ingen kod, vi skriver egen kod från de öppna formlerna.

## Öppna frågor
- Level 3 är i dag 500 000 kr fast belopp. Med valfri summa bör den bli procent. Beslutas i steg 8.
- Vilka lampnivåer ger Avvaktar, Köper lite och Köper? Beslutas i steg 8.
- Ska W-Cipher någonsin bli en lampa? Nu: nej.
- Realtidsdata till W-Cipher: gratis källa (t.ex. Binance/Coinbase publika flöden) + TradingView Lightweight Charts.
