# Steg 9 – Walter som app (design)

22 okt 2026. Grund: samtal med ägaren + `docs/ROADMAP.md` steg 9 + `CLAUDE.md`.
Skiss av landningssidan: `.superpowers/brainstorm/landning-v3.html` (ligger i .gitignore, öppnas via `walter-2` i `.claude/launch.json`, port 8771).

## Varför
Walter ska kunna användas av andra än ägaren. Personen som öppnar Walter är nyfiken, nybörjare, eller vill handla på ett nytt sätt
med visuell elegans. Den letar inte efter ett verktyg med hundra reglage utan efter någon att luta sig mot: en strateg, en förvaltare,
en syntet som Walter i Alien: Covenant – varm men kallt kalkylerande, alltid tydlig, ljuger aldrig.

Det här steget är ett proof of concept med paper (låtsaspengar) innan något kopplas live mot en börs.

## Mål
1. En filmisk landningssida som får folk att vilja gå in.
2. En ny användare kan på några minuter välja summa och börs och få en egen Walter som handlar deras paper.
3. Allt användarens sparas i deras egen webbläsare. Ingen inloggning, ingen server som sparar personuppgifter.
4. Ägarens egen portfölj, journal, historik och K4 syns ALDRIG för andra – varken i appen, på den publicerade sidan eller i repot.
5. Ägaren kan fortsätta använda Walter i mobilen med sina egna uppgifter, bara för sig.

## Inte med i steg 9
- SOL, silver eller andra valutor. SOL (och test av logiken mot andra valutor) blir ett eget senare steg, efter historiktest.
- Live-handel. Ingen API-nyckel tas emot, ingen knapp låtsas att live finns.
- Avanza, Nordnet eller andra aktiemäklare (inget officiellt API hos Avanza, Nordnets är stängt för nya; Walter handlar riktig krypto, inte ETP:er).
- Konton, inloggning, server-databas.
- Omskrivning av git-historiken för att ta bort gamla `state.json`. Beslutas separat, senare, bara om ägaren vill (går inte att ångra).

## Anti-mål (misslyckat även om det fungerar)
- Walter säger något som inte är sant: lovar live, visar en börs som inte är tillåten i Sverige, visar en tillgång som inte finns på vald börs, eller hittar på data (okänt = "väntar på data", som i resten av Walter).
- Någon annan än ägaren kan se ägarens belopp, affärer, journal eller K4.
- Användaren får fritt välja mynt Walter aldrig testats på.
- Landningssidan känns som en video som stannar och börjar om. Alla loopar ska vara sömlösa.
- Text som överlappar eller bryts konstigt på någon skärmstorlek.

## Delarna

### 1. Landningssidan
Utgå från skissen `landning-v3.html` (ägaren har godkänt riktningen). Det som är bestämt:
- Dimmig rörlig bakgrund (stora suddiga ljusfläckar som driver), frostad glasruta i mitten, filmkorn, vinjett.
- "Labbet bakom rutan": de tio lamporna lyser rött/grönt genom glaset, en kurva glider, en skannerlinje andas upp och ner, en ring andas.
  På riktiga sidan ska lamporna bakom glaset visa Walters riktiga lampor just nu (röd/grön/väntar) från den publika marknadsfilen.
- Musen (eller fingret) torkar en liten klar fläck i glaset så man ser labbet.
- Logon ("Inskriven" hexagon-W) glitchar kort, slumpvis var 3,5–9,5 s. W A L T E R tonar in bokstav för bokstav.
- Text: kicker `LABB 01 · STRATEG · FÖRVALTARE · PAPER` (kort form `LABB 01 · PAPER` på mobil, bryts aldrig).
  Under ordmärket: "Walter läser marknaden varje dag och förvaltar åt dig. Lugnt, metodiskt, alltid exakt. Han börjar med låtsaspengar, tills du är redo."
  Ordet "live" används inte på landningssidan (live åt andra kräver FI/jurist först, se ROADMAP).
- Statusrad: `SYSTEM · ONLINE`, klocka, `LÄSER 10 SIGNALER`.
- Ljust (Dimma) är standard, mörkt (Labbet) via rund knapp uppe till höger. Valet sparas i `localStorage` under samma nyckel som appen (`walterDark` = "1"/"0"), så det följer med in och ut.
- Inga Weyland-referenser.
- Alla loopar sömlösa: periodiska kurvor som glider ett helt varv, ljussvep med periodisk gradient, `alternate` på det som ska gå fram och tillbaka.
  Filmkornets flimmer och logons glitch hackar med flit.
- `prefers-reduced-motion`: allt stilla, texten syns direkt.
- Fonter Jost + JetBrains Mono, färgerna från `css/walter.css`.
- **GÅ IN** leder till introt första gången, direkt till översikten när användaren redan har en Walter.

### 2. Vägen in (första gången)
1. **Walter presenterar sig**, tre korta rutor i Walters röst (varm, exakt, ärlig): vem han är, vad han gör (läser marknaden varje dag, handlar med låtsaspengar), vad han inte gör ("Jag rör inga riktiga pengar. Det kan jag inte än."). Knappen "Hoppa över" syns hela tiden.
2. **Summa**: valfri summa i kronor (ingen fast skala, allt mäts i procent).
3. **Börs**: bara börser som har MiCA-tillstånd och får erbjuda krypto i Sverige (krav sedan 1 juli 2026). Walter räknar med den börsens avgifter.
   Saknar börsen en tillgång (t.ex. PAXG) säger Walter det rakt ut och den delen ligger kvar i kontanter.
4. **Översikten.**

### 3. Appen för en ny användare
- Samma Walter-hjärna som ägarens: samma tio lampor, samma lägen (Vilar / Avvaktar / Köper lite / Köper), samma buffert, samma trappa
  (Level 1 BTC 35 %, Level 2 ETH 20 %, Level 3 guld/PAXG 20 %), samma upplåsningsregler, max 75 % investerat, minst 25 % kontant,
  minsta affär 2 %, genomsnittsmetoden för omkostnad. Reglerna kommer från `rules` i ägarens `state.json` men publiceras i marknadsfilen
  (de är inte personliga).
- Användarens portfölj, affärer, historik och K4-underlag ligger bara i deras webbläsare (`localStorage`).
- Knapp "Spara kopia" (laddar ner en fil) och "Läs in kopia" (läser filen), eftersom rensad webbläsare = borttagen portfölj. Walter säger det ärligt i Inställningar.
- **Förklaringar påslagna som standard.** Varje lampa, läget, Sharpe, drawdown, nivåerna förklaras i vanliga ord där de visas.
  Texterna finns redan i `js/app.js` (`EXPLAIN`, rad ~486) men bara i Pro-fliken; flytta/återanvänd dem.
  **Pro-läget** döljer förklaringstexten och visar siffrorna (värde, gräns, källa, tid) som Pro-fliken gör i dag.
- "Live: inte än" står ärligt där live skulle ha legat. Ingen knapp, inget fält för API-nyckel.
- **Walter handlar själv** åt nya användare (beslut av ägaren 22 okt). Inget JA behövs. Läge, affärer och journalpost skrivs
  automatiskt i användarens webbläsare, och Walter berättar i vanliga ord vad han gjort och varför. Ägarens egen Walter
  fortsätter som i dag: läget ändras bara via journalen när ägaren skriver JA i `paper.bat`.
- Flikar som bara gäller ägaren (journal med JA-godkännande via `paper.bat`) visas inte för nya användare.

### 4. En hjärna, många portföljer (data)
- Hämtaren i GitHub Actions (`walter-auto.yml`, var 15:e minut) fortsätter vara Walters enda hjärna.
- Den publicerar en ny **publik marknadsfil** med bara: lampornas status/värde/tid, antal röda, Walters läge enligt lamporna,
  ETH-villkoren, guldvillkoren, priser i SEK (BTC, ETH, PAXG), USD/SEK, `rules` och en **daglig logg** av allt detta
  (så att en användares Walter kan räkna ikapp dagar då sidan inte var öppen). Inga belopp, ingen journal, inga positioner, ingen K4.
- Den publika appen läser ENDAST den filen.
- PAXG-priset hämtas inte i dag (`walter_paper.py` rad 51: "hämtas inte än") – måste läggas till i hämtaren.
- KPI-lampan (`market.cpi`, handskriven) är marknadsdata och ska med i den publika filen.

### 5. Ägarens portfölj: krypterad
- Repot `sinthaetic/walter` förblir publikt (privat repo skulle spräcka GitHubs 2 000 gratisminuter/månad med ~70 körningar/dygn).
- Allt personligt i `data/state.json` (journal, portfölj, historik, K4, capitalChange) sparas i repot bara som en **krypterad fil**.
  Den okrypterade filen läggs i `.gitignore`.
- Nyckeln: en lång slumpad kod. Finns i `fetcher/.env` (laddas aldrig upp), som GitHub Secret (så Actionen kan låsa upp, räkna, låsa igen),
  och skrivs in en gång i ägarens mobil.
- `paper.bat`, `hamta.bat`, `walter deploy`, K4 och Actionen ska fungera som i dag för ägaren – de låser upp, gör sitt, låser igen.
- Den publicerade sidan innehåller ägarens data bara krypterad. Samma adress som i dag (`sinthaetic.github.io/walter/`).
  Ägaren öppnar den i mobilen, skriver koden en gång (sparas i mobilens webbläsare) och ser sin egen Walter som i dag.
  Alla andra får den rena appen.
- Publiceringen får en spärr (som dagens `BLOCK` i `walter_deploy.py`): hittas okrypterad personlig data i det som ska publiceras stoppas allt.
- Kryptering i webbläsaren med Web Crypto (AES-GCM, nyckel härledd ur koden med PBKDF2 eller liknande, många varv). Samma format i Python.

### 6. Beslut tagna av Claude (ägaren kan ändra)
- **Ikapp-räkning:** missade dagar spelas upp i ordning, med varje dags egna priser och lampor från den dagliga loggen.
  Upplåsningar (15/30 dagar, DD) och bufferten räknas över de uppspelade dagarna. Loggen sparas från första publiceringen och framåt
  och kortas aldrig. Walter berättar efteråt i vanliga ord: "Medan du var borta gjorde jag 2 affärer …".
- **Ägarens rapporter** (`reports/`: K4, avgiftsrapport) publiceras inte längre. De finns lokalt på ägarens dator.
- **Nya användare får ingen K4-rapport.** Det är låtsaspengar. Deras affärer finns i affärslistan och i kopian de sparar.
- **Valuta:** allt visas i SEK. Börsens avgift = taker + slippage + växlingsavgift när börsen handlar i EUR/USD.
  Marknadsfilen publicerar därför även EUR/SEK.
- **Mer personlig data som aldrig publiceras okrypterad:** `cache.json` → `daily` (ägarens portföljvärde per dag) och
  `data/paper-journal-V2.1-FIXAD.csv`. Telegram-notisen och Actionens push-trigger flyttas över till den krypterade filen.

## Begränsningar
- Statisk frontend, ingen build (CLAUDE.md). Öppnas direkt i webbläsaren och via GitHub Pages.
- Bara gratis data och gratis hosting.
- Design enligt CLAUDE.md: clean, frostat glas, teal-accent, röd/grön bara i lampor och läge, fasta höjder där innehåll byts, notiser till en vanlig människa.
- Walter ljuger aldrig. Okänt värde = null = "väntar på data".
- Ändras en regel ska den gälla både ägarens Walter och appen (en källa: `rules`).

## Lämnat till byggaren
- Exakt filnamn och format för den publika marknadsfilen och den krypterade filen.
- Hur appen skiljer på "ny användare" och "ägaren med kod" i samma `index.html` (eller en separat sida).
- Hur ikapp-räkningen går till i detalj (med den dagliga loggen).
- Börslistan och avgifterna: kontrollera varje börs i ESMA:s register / FI:s register vid byggtillfället, hämta avgifter
  (taker, och slippage-antagande) från börsens officiella avgiftssida, skriv källa och datum. Kandidater från research 22 okt:
  Kraken, Coinbase, Bitstamp, Bybit EU, OKX, Bitpanda, Crypto.com, Safello (enda svenska). Binance verkar sakna tillstånd – ta inte med.
  Kolla per börs om ETH och PAXG finns.
- Hur JS-versionen av trade-motorn hålls i takt med `fetcher/walter_paper.py` (samma regler, samma avrundning).
