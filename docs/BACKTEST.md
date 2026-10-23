# Historiktestet – vad som blir kvar på banken

23 okt 2026. Steg 10 del 3 och 3b. Allt kan köras om: `.venv\Scripts\python.exe -m backtest.run` (ca 4 minuter)
och `.venv\Scripts\python.exe -m backtest.plateau` (del 3b, ca 2 minuter).

> **Del 3b ändrade rekommendationen.** Den långsamma Walter höll inte när vi skakade på inställningarna.
> Nu rekommenderas fasta andelar 35 % BTC + 20 % ETH + 20 % guld, ombalanserat en gång i veckan med 5 %-band.
> Se "Hur säkert är det?" och "Rekommendationen" längst ner.

## Kort svar (del 3)
- **Dagens Walter handlar alldeles för ofta.** Han byter läge ungefär 45 gånger per år, för att en enda lampa blinkar.
  Avgifterna äter upp vinsten. 100 000 kr 2014 blev **228 000 kr** på banken, och 100 000 kr 2020 blev **93 000 kr**.
- **Att nästan aldrig byta vinner.** Samma Walter med lägena kvar, men långsam (beslut en gång i veckan, snittet av
  60 dagars lampor och 7 veckors bekräftelse innan han byter läge), gav **480 000 kr** från 2020 och **9,6 miljoner** från 2014.
- **Ärligt:** från 2020 och framåt slog den långsamma Walter **inte** det enklaste alternativet, att alltid ha
  35 % BTC + 20 % ETH + 20 % guld och ombalansera. Det gav 499 000 kr, alltså 4 % mer. Walters fördelar är att
  nedgångarna var mindre (högst 41 % mot 59 %) och att han vann på alla andra mått (2014–2019 och medianen över startdagar).
- Det här är ingen finansiell rådgivning. Historien säger inte vad som händer härnäst.

## Vad testades
- Walter dag för dag från 2014-01-01 till 2026-10-22. Startkapital 100 000 kr. Varje beslut genomförs **nästa dag**
  till nästa dags pris, så testet kan inte fuska med morgondagens data.
- Allt dras av: börsens avgift + prisglidning på varje affär, växling SEK↔EUR in och ut, SEPA-avgift, och
  **svensk skatt** (30 % på vinst, genomsnittsmetoden, 70 % av förlusterna dras av samma år). Skatten betalas från
  kontot året efter. Ett år med förlust ger skattereduktion (30 % av underskottet), som hamnar på ditt bankkonto.
- Siffrorna är **kronor på bankkontot** efter att allt sålts, all skatt betalats och pengarna tagits hem.
- Grundbörs: som Kraken (0,8 % avgift + 0,2 % glidning, EUR, 1 % växling, 10 kr SEPA). Bitstamp (0,4 %) och Safello
  (0,6 %, SEK, ingen växling) visas också längre ner.

### Två rättningar av själva testet (inte av Walter)
| Dagens Walter 2014–idag | Bank kr |
|---|---|
| Gamla testet (avrundning uppåt, ingen skattereduktion) | 155 000 |
| + skattereduktion för förlustår | 182 000 |
| + avrundning till närmaste (används nedan) | 228 000 |
| (avrundning nedåt, som jämförelse) | 307 000 |

## Vilka lampor fanns
Walter har tio lampor, men all historik finns inte gratis. Saknas en lampa räknas andelen röda bland de som finns, omräknat till tio och avrundat till närmaste heltal.

| Från | Lampor med data | Antal |
|---|---|---|
| 2014-01-01 | S&P 500, BTC-trend, BTC-vecka, VIX, 10Y-ränta, dollarindex, MVRV-Z | 7 |
| 2022-11-05 | + SOPR | 8 |
| 2026-09-18 | + ETF-flöden | 9 |
| aldrig | KPI mot förväntan (ingen gratis historik) | – |

ETH finns från augusti 2015. Guld före 2019 är guldterminen (GC=F) i stället för PAXG.

## Hur vi undvek att lura oss själva
1. **Inställning 2014–2019:** 11 787 varianter kördes. Bara på de här åren valdes vilka inställningar som var bäst.
2. **Kontroll 2020–idag:** de valda körs oförändrade på år de aldrig sett.
3. **Startdag:** varje variant startas varje kvartal 2014–2024 (44 starter), alltid med slut i dag. Vi visar medianen och det sämsta utfallet.
4. Största nedgång får vara högst 60 %, annars räknas varianten bort.

## Pengatabellen (kr på banken per 100 000 kr, Kraken-lik börs)

| Strategi | 2014–2019 | 2020–idag | Median 44 starter | Sämsta start | Största nedgång | Affärer 2020– | Lägesbyten 2020– |
|---|---|---|---|---|---|---|---|
| **Walter i dag** | 237 000 | 93 000 | 96 000 | 78 000 | 44 % | 669 | 306 |
| **Walter långsam (rekommenderad)** | 1 477 000 | 480 000 | 539 000 | 94 000 | 41 % | 48 | 8 |
| Walter långsam, bara BTC 75 % | 1 214 000 | 595 000 | 665 000 | 92 000 | 49 % | 30 | 8 |
| Bäst på 2014–2019 (ren inställning) | 1 552 000 | 346 000 | 433 000 | 84 000 | 57 % | 47 | 1 |
| Ombalanserad BTC 35 % (alltid Köper) | 277 000 | 233 000 | 226 000 | 101 000 | 39 % | 177 | – |
| Ombalanserad BTC 35 + ETH 20 + guld 20 | 949 000 | 499 000 | 452 000 | 107 000 | 59 % | 233 | – |
| Ombalanserad BTC 75 % | 652 000 | 534 000 | 517 000 | 106 000 | **69 %** | 127 | – |
| Köp en gång BTC 35 % | 390 000 | 370 000 | 362 000 | 99 000 | **81 %** | 2 | – |
| Köp en gång BTC 35 + ETH 20 + guld 20 | 1 718 000 | 647 000 | 504 000 | 103 000 | **92 %** | 6 | – |
| Köp en gång BTC 75 % | 706 000 | 674 000 | 659 000 | 104 000 | **82 %** | 2 | – |

"Största nedgång" = det värsta fallet från en topp, i någon av perioderna eller startdagarna. **Fetstil** = över 60 %, för mycket för en nervös nybörjare.
"Ombalanserad" = andelarna justeras tillbaka när de glidit mer än 2 % av portföljen. "Köp en gång" = köp dag 1, rör aldrig.

### Startar man 2020 eller senare (20 starter)
| Strategi | Median | Sämsta | Största nedgång |
|---|---|---|---|
| Walter i dag | 92 000 | 78 000 | 44 % |
| Walter långsam (rekommenderad) | 183 000 | 94 000 | 32 % |
| Ombalanserad BTC 35 + ETH 20 + guld 20 | 158 000 | 107 000 | 43 % |
| Ombalanserad BTC 75 % | 180 000 | 106 000 | 58 % |

## Avgifter och skatt, hela perioden 2014–idag (Kraken-lik)
| Strategi | Bank kr | Affärer | Avgifter kr | Skatt kr | Skattereduktion kr |
|---|---|---|---|---|---|
| Walter i dag | 228 000 | 1 180 | 405 000 | 162 000 | 22 000 |
| Walter långsam (rekommenderad) | 9 640 000 | 125 | 527 000 | 4 053 000 | 100 |
| Ombalanserad BTC 35 + ETH 20 + guld 20 | 4 824 000 | 654 | 372 000 | 2 068 000 | 1 000 |

Dagens Walter betalade mer i avgifter (405 000 kr) än han tjänade. Den långsamma Walter betalar mest i skatt, för att han tjänar mest.

## Börsen spelar mindre roll än antalet affärer (2020–idag)
| Strategi | Kraken-lik | Bitstamp | Safello |
|---|---|---|---|
| Walter i dag | 93 000 | 127 000 | 106 000 |
| Walter långsam (rekommenderad) | 480 000 | 483 000 | 447 000 |
| Ombalanserad BTC 35 + ETH 20 + guld 20 | 499 000 | 510 000 | 511 000 |

## Vad vinner, och varför
- **Färre affärer.** Med 7 lampor väger varje lampa 1,4 poäng av 10, så en enda blinkande lampa flyttade Walter
  mellan Köper och Köper lite flera gånger i månaden. Varje byte kostar 1 % i avgift, och ofta skatt på vinsten.
- **Ingen tajming av ETH och guld.** ETH/BTC-regeln (över 30-dagarssnittet) gick av och på 18–45 gånger per år,
  och guldregeln (VIX/S&P) 12–33 gånger. I den rekommenderade varianten följer ETH bara läget, och guldet ligger kvar hela tiden när Level 3 är upplåst.
- **Den långsamma Walter vilar aldrig.** På 12 år bytte han läge 19 gånger och kom aldrig till Vilar. Han gick till
  Köper lite i december 2017 (nära toppen) och till Avvaktar 2019 och 2022, men först efter flera veckor. Lägena finns
  kvar och skulle slå till i en lång kris, men i praktiken ligger han oftast på Köper.
  Hans största vinst mot de andra kommer från ett enda beslut: att sälja halva BTC i december 2017.
- **Alltid investerad slår nästan alltid tajming på kryptots stora uppgångar.** Därför vinner "köp och rör inte" på
  pengar, men med nedgångar på 70–90 %, som är för mycket för de flesta.

## Hur säkert är det här? (inte särskilt)
- **Inställningarna är känsliga.** Snitt 30 dagar i stället för 60 gav 550 000 kr i stället för 1,5 miljoner 2014–2019
  (och 406 000 i stället för 480 000 kr från 2020).
  Avrundar man lampräkningen uppåt i stället för till närmaste blev det 296 000 kr i stället för 480 000 kr från 2020.
  Siffran kommer från några få stora vändpunkter (2018, 2022) och kan vara tur.
- **Den rekommenderade varianten valdes med båda perioderna.** Bara inställningsperioden gav en variant som tjänade
  346 000 kr från 2020, sämre än att alltid vara investerad. Kontrollsiffran 480 000 kr är därför för optimistisk.
- **Testet har färre lampor än den riktiga Walter.** Live har han tio lampor. Här fanns 7–9, och KPI saknades helt.
- **Data:** gratiskällor. Guld före 2019 är en termin, inte PAXG. ETF-flöden finns bara från sep 2026. Riktiga ordrar kan bli sämre än +0,2 % glidning.
- **Skatt förenklad:** skattereduktionen antar att du har annan skatt att dra av mot. Valutavinster på EUR beskattas inte här.
- **Framtiden är inte historien.** BTC gick från ca 750 dollar (jan 2014) till ca 81 000 (okt 2026). Det händer inte igen på samma sätt.
- Det här är inte finansiell rådgivning. Walter är ett papperstest.

## Hur säkert är det? (del 3b)
Vi skakade på inställningarna i stället för att leta efter den högsta siffran. Varje inställning startades varje
kvartal 2014–2024 (44 starter). "10 % sämsta" = nivån där bara var tionde start gick sämre. Det är det viktigaste måttet,
för det skyddar den som har otur med startdagen.

**Den långsamma Walter (tak 50/15/10, snitt 60 dagar, 7 veckor, 5 %):** grannarna ligger nära (snitt 45 eller 90 dagar,
5 eller 9 veckor, 2 eller 5 %), alla inom 15 %. Men **avrundningen** fäller den:

| Långsam Walter | Median | 10 % sämsta | Största nedgång |
|---|---|---|---|
| Avrundning till närmaste | 539 000 | 145 000 | 41 % |
| Avrundning uppåt | 305 000 | 138 000 | 41 % |
| Avrundning nedåt | 598 000 | 122 000 | 53 % |
| Grannar (snitt 45/90, 5/9 veckor, 2 %) | 488 000–569 000 | 135 000–148 000 | 39–44 % |

Avrundningen spelar roll även live, eftersom snittet av 60 dagars lampor nästan aldrig blir ett heltal.

**Utan toppen i december 2017** (bara starter från 2018, 28 stycken) försvinner Walters försprång:

| Starter 2018 och senare | Median | 10 % sämsta |
|---|---|---|
| Långsam Walter (närmaste / uppåt) | 195 000 / 178 000 | 126 000 / 111 000 |
| Fast 35/20/20, varje vecka, 5 %-band | 202 000 | 128 000 |
| Fast 35/20/20, varje dag, 2 % | 202 000 | 127 000 |
| Walter i dag | 92 000 | 80 000 |

**Den fasta mixen står på en riktig platå.** Varje dag, vecka eller månad × band 2, 5 eller 10 %: medianen blev
452 000–578 000, 10 % sämsta 140 000–151 000, och 200 000–206 000 för starter från 2018. Den har inga lamp-inställningar
som kan vara tur.

| Alla 44 starter | Median | 10 % sämsta | Största nedgång | Affärer (median) |
|---|---|---|---|---|
| **Fast 35/20/20, varje vecka, 5 %-band** | **510 000** | **142 000** | 55 % | 54 |
| Fast 35/20/20, varje dag, 2 % | 452 000 | 140 000 | 59 % | 259 |
| Fast 35/20/20 med Levels kvar | 474 000 | 132 000 | 54 % | 54 |
| Ombalanserad BTC 35 % | 226 000 | 124 000 | 39 % | 193 |
| Långsam Walter (sämsta avrundning) | 305 000 | 138 000 | 53 % | 59 |
| Långsam Walter, tak 75/0/0 (närmaste) | 665 000 | 160 000 | 65 % med nedåt | 31 |
| Walter i dag | 96 000 | 83 000 | 44 % | 661 |

Taken är ingen platå: mer BTC gav nästan alltid mer pengar (35/20/20 → 75/0/0: medianen 446 000 → 665 000) och större
nedgång. Det beskriver bara att BTC steg, inte ett skäl till att det fortsätter.

**Hur säkert:** ganska säkert att den fasta veckomixen är minst lika bra som alla långsamma Walter-varianter vi
testade. Hur mycket bättre vet vi inte. Alla bra kandidater hamnar på ungefär 1,4 gånger pengarna för de 10 % sämsta,
och historiken är en enda lång kryptouppgång.

## Rekommendationen (del 3b)
Regeln: bäst för de 10 % sämsta starterna, sedan medianen, bland dem med största nedgång högst 60 % (i alla avrundningar).
Inom 5 % vinner den enklaste. Vinnaren är **fasta andelar**:
1. **BTC 35 %, ETH 20 %, guld 20 %** (75 % investerat, minst 25 % kontant), från första dagen.
2. Titta **en gång i veckan** (söndag). Genomför på måndagen.
3. Handla bara en tillgång som glidit **mer än 5 % av portföljen** från sitt mål. Gå då hela vägen tillbaka till målet.
4. Lamporna och läget visas fortfarande, men de **handlar inte**. Levels låser inte längre ETH och guld.

Priset för det: nedgångar upp till 55 % (den långsamma Walter: 41–53 %). Det är under gränsen på 60 %, men det känns.
Tvåa: den långsamma Walter med avrundning till närmaste, om lägena måste få handla.

Regelvärden till del 4 (`state.json` → `rules`, och fälten i sim.py som gör samma sak):

```json
{
  "rules": {
    "strategy": "fixedMix",
    "caps": {"BTC": 0.35, "ETH": 0.2, "GOLD": 0.2},
    "maxInvested": 0.75,
    "minCash": 0.25,
    "paper": {"minTradePct": 2},
    "decision": {"cadenceDays": 7, "weekday": "söndag", "bandPp": 5},
    "lampsTrade": false,
    "levelsGate": false
  },
  "simStrategy": {
    "weights": {"BTC": 0.35, "ETH": 0.2, "GOLD": 0.2},
    "rebalance": true, "cadence_days": 7, "band_pp": 5, "loss_credit": true
  }
}
```
