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

Regelvärden (infört i del 4, 23 okt: `state.json` → `rules`). Andelarna är `caps`, så det finns bara en källa:

```json
{
  "rules": {
    "strategy": "autopilot",
    "decision": {"weekday": "söndag", "bandPp": 5},
    "caps": {"BTC": 0.35, "ETH": 0.2, "GOLD": 0.2},
    "maxInvested": 0.75,
    "minCash": 0.25,
    "paper": {"minTradePct": 2}
  }
}
```
Lamporna och Levels handlar inte i autopiloten. Den gamla strategin finns kvar med `"strategy": "lamps"`.

## Autopiloten i Walter (del 4)
Historiktestet kör nu Walters egen kod: `sim.autopilot()` anropar `walter_paper.propose`, samma som Walter live.
`.venv\Scripts\python.exe -m backtest.run --quick` skriver jämförelsen överst (44 starter, Kraken-lik börs):

| Alla 44 starter | Median | 10 % sämsta | Största nedgång | Affärer (median) |
|---|---|---|---|---|
| Autopiloten (live-koden) | 524 000 | 143 000 | 55 % | 64 |
| Fast 35/20/20, varje vecka, 5 %-band (del 3b) | 510 000 | 142 000 | 55 % | 54 |

Skillnaden: del 3b köpte bara om köpet (efter kontantgolvet) var större än bandet. Walter köper när andelen glidit mer än
bandet och köpet är minst 2 % (minTradePct), också om kontanterna bara räcker en bit. Det ger 10 fler små köp, och
10 % sämsta är i stort sett densamma. Samma platå som i del 3b.

## Testade vi W-Cipher? Ja. (del 5, 24 okt 2026)
Frågan: kan W-Ciphers köp- och säljsignaler tjäna pengar i både uppgång och nedgång, efter avgifter och svensk skatt?
Och ska de styra en liten del (10–20 %) av Walter? Kör om: `.venv\Scripts\python.exe -m backtest.wcipher_run` (några sekunder).

**Kort svar: nej.** Signalerna slog inte autopiloten, och att blanka (tjäna på nedgång) slutade nästan alltid med att
kontot tömdes. Ingen satellit.

### Vad testades
- W-Cipher exakt som på sidan: `backtest/wcipher.py` är en kopia av `js/wcipher.js` (paritetstest i `tests/js/wcipher.test.js`).
  Standardinställningarna, ingen justering. BTC/USD från Bitstamp, dagsljus och 4-timmarsljus, hela vägen från 2011.
- Signalen på en stapel handlas på **nästa** stapels öppning. Ingen titt framåt.
- Fyra varianter bestämdes i förväg: *bas* (köp på kop/guld, sälj på salj/blod), *stora* (alla stora signaler),
  *kop+salj*, och *blod ut* (köp på kop/guld, sälj bara på blod).
- **Bara köp** (spot, allt i BTC eller allt i kontanter): samma börs som autopiloten (1 % per affär), svensk skatt.
- **Köp och blanka** (terminer, 1×): lång på köpsignal, kort på säljsignal. 0,1 % per affär, finansiering 0,01 % per
  8 timmar (ca 11 % per år). En kort position likvideras när priset nästan fördubblas – då är insatsen borta.
  Förenkling: vinst och förlust på terminer beskattas som krypto (30 %, förluster 70 %). Obs: terminer för privatpersoner
  finns troligen inte hos MiCA-börserna i Walter (Bitstamp, Bybit EU, Kraken, OKX Europe, Safello).
- Val på 2014–2019, kontroll oförändrat på 2020–idag, och start varje kvartal 2014–2024 (44 starter).

### Pengatabellen (kr på banken per 100 000 kr)
| Strategi | 2014–2019 | 2020–idag | Median 44 starter | 10 % sämsta | Största nedgång | Median från 2020 | Affärer | Avgifter | Skatt |
|---|---|---|---|---|---|---|---|---|---|
| **Autopiloten (live)** | **1 213 000** | **573 000** | **524 000** | 143 000 | 55 % | 163 000 | 64 | 24 000 | 185 000 |
| Bästa W-Cipher, bara köp (dag, blod ut) | 942 000 | 623 000 | 590 000 | 170 000 | **78 %** | 248 000 | 16 | 64 000 | 275 000 |
| Bästa W-Cipher, köp och blanka (dag, blod ut) | 465 000 | 302 000 | 296 000 | 169 000 | **92 %** | 238 000 | 28 | 160 000 | 147 000 |
| Satellit 10 % W-Cipher + 90 % autopilot | 1 185 000 | 578 000 | 540 000 | 155 000 | 59 % | 174 000 | 80 | 28 000 | 199 000 |
| Satellit 20 % W-Cipher + 80 % autopilot | 1 158 000 | 583 000 | 550 000 | 157 000 | **64 %** | 186 000 | 80 | 32 000 | 208 000 |
| Kontroll: 10 % bara BTC + 90 % autopilot | 1 182 000 | 602 000 | 560 000 | 144 000 | 60 % | 165 000 | 66 | 24 000 | 201 000 |
| Kontroll: 20 % bara BTC + 80 % autopilot | 1 151 000 | 631 000 | 596 000 | 145 000 | **65 %** | 170 000 | 66 | 24 000 | 217 000 |
| Köp och behåll BTC 100 % | 903 000 | 864 000 | 844 000 | 150 000 | **83 %** | 212 000 | 2 | 26 000 | 324 000 |
| BTC 35 % ombalanserad | 277 000 | 233 000 | 226 000 | 124 000 | 39 % | 132 000 | 193 | 14 000 | 55 000 |

Avgifter, skatt och affärer är medianen över de 44 starterna. **Fetstil** på nedgång = över 60 %.

### W-Ciphers signaler var för sig (2014–idag, dagsljus / 4 timmar)
| Variant | Bara köp 2014–2019 | Bara köp 2020– | Rundor/år (in+ut) | Träff | Snitt vinst / förlust | Tid i marknad | Köp och blanka: kontot tömt |
|---|---|---|---|---|---|---|---|
| bas, dag | 63 000 | 125 000 | 2 | 52 % | +16 % / −16 % | 38 % | 40 av 44 starter |
| stora, dag | 63 000 | 137 000 | 2 | 57 % | +15 % / −17 % | 36 % | 40 av 44 |
| kop+salj, dag | 63 000 | 127 000 | 2 | 50 % | +16 % / −14 % | 40 % | 40 av 44 |
| blod ut, dag | 942 000 | 623 000 | 1 | 69 % | +156 % / −36 % | 84 % | 2 av 44 |
| bas, 4 h | 29 000 | 28 000 | 18 | 46 % | +6 % / −7 % | 39 % | 28 av 44 |
| kop+salj, 4 h | 32 000 | 53 000 | 14 | 54 % | +6 % / −9 % | 46 % | 28 av 44 |
| blod ut, 4 h | 238 000 | 152 000 | 11 | 40 % | +24 % / −9 % | 70 % | 27 av 44 |

"stora, 4 h" är nästan samma som "bas, 4 h". Även **helt utan avgifter** blev bas-signalerna bara 110 000–147 000 kr
på 12 år, medan BTC steg ungefär 100 gånger. Signalerna har ingen fördel att äta upp – avgifterna gör det bara värre.

### Vad betyder det för drömmen (tjäna på upp OCH ned)?
- **Säljsignalen kommer för tidigt i en uppgång.** "Salj" säger att vågen vänt ned från toppen, men i en tjurmarknad
  fortsätter priset upp. En blankning hålls tills nästa köpsignal längst ner, och hinner ofta se priset fördubblas.
  Då är kontot borta (nov 2015, dec 2020, jan 2021). 1× hävstång skyddar inte en kort position.
- Den enda varianten som överlevde, *blod ut*, ligger lång 84–97 % av tiden. Den är i praktiken "köp och behåll BTC"
  med några få utgångar. Dess blankningar (12 stycken på 12 år) förlorade tillsammans ungefär 40 %.
- Även i björnår tjänade den inte på nedgången: 2018 −66 % och 2022 −56 % (autopiloten: −34 % och −26 %).
- *Blod ut* (bara köp) gav mer än autopiloten från 2020 (623 000 mot 573 000 kr), men med 66 % nedgång, och mindre
  än att bara köpa BTC (864 000). Den vinner bara när BTC-andelen (nästan 100 %) vinner.
- Det som såg bra ut i satelliten var mer BTC, inte signalerna: samma andel som bara köpt BTC gav lika mycket eller mer
  (median 560 000 mot 540 000), och lika stora nedgångar.

### Hur säkert?
- **Ganska säkert att svaret är nej** för W-Cipher med dagens inställningar: 16 varianter (4 signalregler × dag/4 h × bara köp/blanka) pekar åt samma håll,
  och de som handlar ofta förlorar mest. Det enda plus vi såg (10 % sämsta 155 000 mot 143 000 med satellit) kommer från
  en variant som nästan aldrig handlar (16 affärer på 12 år), och vilar på några få utgångar 2018 och 2022.
- Vi provade bara de förbestämda varianterna. Andra inställningar kan se bättre ut i efterhand, men det vore just den
  sortens jakt på siffror som lurar en. Market Cipher-handlare som visar vinster visar sällan avgifter, skatt och förlusterna.
- Förenklingar: terminsskatten (som krypto), en fast finansiering, inga avbrott på börsen, Bitstamps pris för W-Cipher men
  Coin Metrics för autopiloten. Satellitens skatt räknas per del (samma summa så länge ett förlustår är under 100 000 kr).

### Rekommendationen
**Ingen satellit (0 %).** W-Cipher får fortsätta vara ett verktyg att titta på (`cipher.html`), men den ska inte flytta
pengar, och Walter ska inte blanka. Autopiloten står kvar oförändrad. Vill ägaren ha mer chans (och mer risk) är en större
BTC-andel ärligare än signaler – men den höjer nedgångarna över 60 %.

## Krasch-broms och nödjustering (del 6, 24 okt 2026)
Frågan: förlorar en koll i veckan för mycket i en kryptokrasch, eller missar den en rusning? Två idéer som aldrig testats.
Kör om: `.venv\Scripts\python.exe -m backtest.krasch_run` (ca en minut, alla kärnor).

**Kort svar: nej.** Ingen av dem ersätter autopiloten. Krasch-bromsen gör nedgångarna mindre, men kostar ungefär en
femtedel av pengarna i medianen. Nödjusteringen gör nästan ingenting.

### Vad testades (bestämt innan något kördes)
- **A. Krasch-broms:** faller BTC eller ETH (var för sig) X % från sin högsta stängning sedan senaste affären, säljs den
  till kontanter. Den köps tillbaka när priset stänger över sitt N-dagarssnitt efter att ha varit under det (eller över
  den gamla toppen). X = 15, 20, 25, 30, 40 %, N = 50, 100, 200 dagar.
- **B. Nödjustering:** söndagens 5 %-band kvar, men glider en andel mer än Y procentenheter någon annan dag justeras den
  direkt. Y = 10, 15, 20.
- **C. Båda,** hela rutnätet (45 celler).
- Kollas varje kväll på dagens stängning, affären görs nästa dag till nästa dags pris. Samma avgifter (Kraken-lik), växling,
  svensk skatt och närmaste avrundning som förut. Testerna i `tests/test_backtest_crash.py` visar att framtida priser inte
  ändrar några tidigare affärer.
- **Val bara på 2014–2019** (20 kvartalsstarter 2014–2018, slut 31 dec 2019). Kontroll oförändrad på 2020–idag
  (20 kvartalsstarter 2020–2024, slut idag) och de vanliga 44 starterna. Platå = alla grannar inom 15 %.

### Pengatabellen (kr på banken per 100 000 kr)
| Strategi | Median 2014–19 | 10 % sämsta 2014–19 | Median 2020– | 10 % sämsta 2020– | Median 44 starter | 10 % sämsta 44 | Största nedgång | Affärer | Avgifter | Skatt |
|---|---|---|---|---|---|---|---|---|---|---|
| **Autopiloten (live)** | **607 000** | 99 000 | 163 000 | 117 000 | **524 000** | **143 000** | 55 % | 64 | 24 000 | 185 000 |
| A: broms 25 %, snitt 50 (bästa platån) | 509 000 | 100 000 | 170 000 | 116 000 | 411 000 | 137 000 | 44 % | 108 | 57 000 | 178 000 |
| B: nödjustering 20 pp (alla Y lika) | 607 000 | 99 000 | 163 000 | 117 000 | 524 000 | 143 000 | 55 % | 64 | 24 000 | 185 000 |
| C: broms 25 %, snitt 200 + nöd 10 pp | 421 000 | 105 000 | 153 000 | 112 000 | 313 000 | 131 000 | 37 % | 93 | 37 000 | 115 000 |

Affärer, avgifter och skatt = medianen över de 44 starterna. En enda körning: autopiloten 1 213 000 kr (2014–2019) och
573 000 kr (2020–idag), A 841 000 / 521 000, C 550 000 / 376 000.

### I kraschen (en körning från 2014, fall från topp till botten och dagar tills värdet var tillbaka)
| Krasch | Autopiloten | A: broms 25 %/50 | C: broms + nöd |
|---|---|---|---|
| 2018 (topp dec 2017) | −49 %, 529 dagar | −27 %, 371 dagar | −11 %, 22 dagar* |
| Mars 2020 | −25 %, **71 dagar** | −19 %, 169 dagar | −20 %, 185 dagar |
| 2022 (topp nov 2021) | −37 %, 823 dagar | −25 %, 590 dagar | −19 %, 519 dagar |

\*C sålde redan i dec 2017 och var i stort sett ute under 2018. B är samma som autopiloten i alla tre.

### Vad betyder det?
- **Bromsen skyddar i en lång björnmarknad** (2018, 2022): nedgången blev ungefär en tredjedel mindre.
- **Men den säljer också i varje vanlig dipp.** BTC faller 25 % flera gånger om året i en uppgång. Bromsen sålde ungefär
  30 gånger (median över starterna) och fick ofta köpa tillbaka högre. I mars 2020 sålde den nära botten och köpte tillbaka i april – därför tog
  det 169 dagar att komma tillbaka i stället för 71. Fler affärer gav dubbelt så höga avgifter.
- **Resultat:** sämre median i inställningsperioden (509 000 mot 607 000, −16 %) och för alla 44 starter
  (411 000 mot 524 000, −22 %). Bara 2020– var den lika bra (median +4 %, 10 % sämsta −1 %, mindre nedgång).
  Regeln kräver båda perioderna, så A faller.
- Den enda bromsen som vann tydligt efter 2020 (20 %, snitt 200: median 179 000) var bland de sämsta 2014–2019
  (374 000) och står inte på en platå. Den hade vi aldrig valt utan att titta på facit.
- **Nödjusteringen:** en andel glider sällan 10 procentenheter på mindre än en vecka (BTC måste stiga eller falla
  ungefär 40 % på några dagar). Det hände några gånger på 12 år, och då kom söndagen ändå strax efter. Ingen skillnad.

### Beslutet
**Nej.** Autopiloten står kvar oförändrad: koll en gång i veckan, 5 %-band, ingen broms. Bromsen betalar för skyddet med just de
rusningar ägaren var rädd att missa. Ingenting byggs live.
