# Steg 9 – Walter som app: byggplan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Andra än ägaren kan öppna Walter, gå in via en filmisk landningssida, välja summa och börs och få en egen Walter som handlar deras paper i webbläsaren – medan ägarens portfölj bara finns krypterad.

**Architecture:** Hämtaren i GitHub Actions är fortsatt Walters enda hjärna. Den publicerar en publik marknadsfil (`data/market.js`: lampor, läge, priser, regler, daglig logg) och en krypterad ägarfil (`data/owner.enc`). I webbläsaren avgör `js/boot.js` vem som tittar: ägaren lokalt (`data/state.js` finns), ägaren med kod (dekrypterar `owner.enc`), en användare (portfölj i `localStorage`, räknas ikapp med `js/engine.js`) eller en ny besökare (landning → intro). Alla fall bygger samma `window.WALTER_STATE` som `js/app.js` redan renderar.

**Tech Stack:** Statisk HTML/CSS/JS utan build, Python 3.12 (`unittest`, `cryptography` för AES-GCM), Web Crypto i webbläsaren, GitHub Actions + GitHub Pages.

**Spec:** `docs/superpowers/specs/2026-10-22-steg-9-walter-som-app-design.md` (läs den först). Skiss: `.superpowers/brainstorm/landning-v3.html`.

## Global Constraints

- Ingen build, inga npm-beroenden. Node finns inte på datorn. JS-tester körs i webbläsaren via `walter-2` i `.claude/launch.json` (http://localhost:8771).
- Python-tester: `python -m unittest discover -s tests -v` från repo-roten med `.venv\Scripts\python.exe`. Enda nya Python-beroendet: `cryptography>=42` i `fetcher/requirements.txt`.
- Walter ljuger aldrig: okänt värde = `null` = "väntar på data". Inga påhittade priser, avgifter eller börser.
- Ägarens data får ALDRIG finnas okrypterad i det som publiceras eller committas: `journal`, `portfolio`, `k4`, `capitalChange`, `daily`, `notis`, `proposal`, `reports/`, `data/paper-journal-V2.1-FIXAD.csv`.
- Reglerna har en källa: `rules` i ägarens `state.json`. Appen får dem via marknadsfilen.
- Tema-nyckel `walterDark` (`"1"`/`"0"`) delas av landning, app och W-Cipher.
- Krypteringsformat (samma i Python och JS): JSON `{"v":1,"kdf":"PBKDF2-SHA256","iter":600000,"salt":b64,"iv":b64,"ct":b64}`, AES-256-GCM, 16 byte salt, 12 byte iv, `ct` = chiffertext + 16 byte tagg (Web Crypto- och `cryptography`-formatet är redan detsamma).
- Nyckelns namn: `WALTER_OWNER_KEY` (i `fetcher/.env` och som GitHub Secret). Mobilen sparar koden i `localStorage` under `walter.ownerKey`.
- Användarens Walter: `localStorage` `walter.user` (JSON, `v: 1`). Walter handlar själv åt användaren, inget JA.
- Design enligt `CLAUDE.md`: Jost + JetBrains Mono, frostat glas, teal-accent, röd/grön bara i lampor och läge, fasta höjder, `prefers-reduced-motion`, inga överlapp eller konstiga radbrytningar på 360–1440 px bredd.
- Texter till användaren på vanlig svenska, i Walters röst: varm, exakt, ärlig. Ordet "live" används inte på landningssidan.
- Commit-meddelanden slutar med `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Arbeta på grenen `steg-9-walter-som-app`.

## Review Focus

1. **Blockerad lagring** (privat läge, `localStorage` kastar fel): landning och intro ska fungera, Walter säger ärligt att inget sparas, inget kraschar. → test i Task 8.
2. **Lång frånvaro och hål i loggen** (90 dagar borta, dagar då Actionen inte körde): ikapp-räkningen spelar bara upp dagar som finns i loggen, i datumordning, och hittar aldrig på en dag. → test i Task 6.
3. **Dag med lampor som väntar** (`ready: false` i loggen): ingen affär och inget lägesbyte den dagen. → test i Task 6.
4. **Fel kod eller trasig `owner.enc`**: tydligt besked, koden sparas inte, sidan faller tillbaka till den publika appen. → test i Task 2 och Task 8.
5. **Börs som saknar en tillgång** (t.ex. ingen PAXG): målet för den tillgången är 0, pengarna ligger kvar som kontanter, Walter säger det i klartext. → test i Task 6.

---

## Filkarta

| Fil | Ansvar |
|---|---|
| `fetcher/walter_vault.py` (ny) | Kryptera/dekryptera, CLI `ny-kod` / `las` / `las-upp` |
| `fetcher/walter_public.py` (ny) | Bygga publik ögonblicksbild + daglig logg, skriva `data/market.js` |
| `fetcher/walter_fetch.py` | PAXG + EUR/SEK, ägarens `daily`/`notis` till `data/owner-cache.json` |
| `fetcher/walter_notis.py`, `walter_auto.py`, `walter_paper.py`, `walter_deploy.py` | Läsa/skriva ägardata via vault, ny publiceringslista + läckspärr |
| `.github/workflows/walter-auto.yml` | Installera först, låsa upp, hämta `owner.enc` från gh-pages, nya push-sökvägar |
| `js/vault.js` (ny) | Dekryptera i webbläsaren |
| `js/engine.js` (ny) | Trade-motorn i JS (ren matte, inga DOM-anrop), ikapp-räkning, nivåer |
| `js/exchanges.js` (ny) | Börslistan med avgifter, källa och datum |
| `js/user-state.js` (ny) | Användarens lagring, kopia till/från fil, bygga `WALTER_STATE` |
| `js/boot.js` (ny) | Avgöra vem som tittar, starta landning/intro/app |
| `js/landing.js` + `css/landing.css` (nya) | Landningssidan |
| `js/intro.js` (ny) | Walter presenterar sig, summa, börs |
| `js/app.js` | Startas via `WalterApp.start(S, ctx)`, användarvy, förklaringar + Pro-läge |
| `index.html` | Landning + intro-markup, ny skriptordning |
| `tests/` (ny) | `test_vault.py`, `test_public.py`, `test_split.py`, `test_deploy_guard.py`, `make_fixtures.py`, `fixtures/`, `js/run.html` |

---

### Task 1: Valv i Python (kryptering + CLI)

**Files:**
- Create: `fetcher/walter_vault.py`, `tests/test_vault.py`, `tests/__init__.py`
- Modify: `fetcher/requirements.txt` (lägg till `cryptography>=42`), `fetcher/.env.example` (lägg till `WALTER_OWNER_KEY=`)

**Interfaces:**
- Produces:
  - `encrypt(obj: dict, code: str, iter: int = 600000) -> dict` (kuvertet enligt Global Constraints)
  - `decrypt(env: dict, code: str) -> dict` (kastar `VaultError("Fel kod eller trasig fil")` vid fel)
  - `new_code() -> str` (6 grupper à 5 tecken ur `ABCDEFGHJKLMNPQRSTUVWXYZ23456789`, bindestreck emellan, `secrets`)
  - `owner_key() -> str | None` (läser `WALTER_OWNER_KEY` ur miljön, efter `walter_fetch.load_env()`)
  - `lock_state() -> None` (`data/state.json` → `data/state.enc`), `unlock_state() -> None` (omvänt; vägrar skriva över en `state.json` som är nyare än `state.enc` och säger det)
  - CLI: `python fetcher/walter_vault.py ny-kod | las | las-upp`

- [ ] **Step 1: Skriv testerna**
  - `test_roundtrip`: `decrypt(encrypt({"a": 1, "å": "ö"}, "k", iter=1000), "k") == {"a": 1, "å": "ö"}`
  - `test_wrong_code_raises`: `decrypt(encrypt({}, "k", iter=1000), "fel")` kastar `VaultError`
  - `test_envelope_shape`: nycklarna är exakt `{"v","kdf","iter","salt","iv","ct"}`, `v == 1`, `kdf == "PBKDF2-SHA256"`, salt 16 byte, iv 12 byte efter base64-avkodning
  - `test_fresh_salt_iv`: två `encrypt` av samma data ger olika `salt`, `iv` och `ct`
  - `test_new_code_format`: matchar `^([A-HJ-NP-Z2-9]{5}-){5}[A-HJ-NP-Z2-9]{5}$`
- [ ] **Step 2:** `python -m unittest tests.test_vault -v` → FAIL (modulen saknas)
- [ ] **Step 3:** Implementera med `cryptography.hazmat.primitives.ciphers.aead.AESGCM` och `hashlib.pbkdf2_hmac("sha256", ...)`, JSON utf-8 utan BOM (`ensure_ascii=False`).
- [ ] **Step 4:** Kör testerna → PASS. Installera: `.venv\Scripts\python.exe -m pip install -r fetcher/requirements.txt`.
- [ ] **Step 5: Commit** `Steg 9: valv för ägarens data (AES-GCM)`

### Task 2: Valv i webbläsaren + JS-testsidan

**Files:**
- Create: `js/vault.js`, `tests/js/run.html`, `tests/make_fixtures.py`, `tests/fixtures/vault-sample.enc` (genererad)

**Interfaces:**
- Consumes: Task 1:s `encrypt`.
- Produces:
  - `window.WalterVault.decrypt(env: object, code: string) -> Promise<object>` (avvisar med `Error("Fel kod eller trasig fil")`)
  - `tests/js/run.html`: laddar skripten under test och `tests/js/*.test.js`, minimal `test(name, fn)` / `eq(a, b)` (djupjämförelse), skriver `PASS n` eller `FAIL namn: detalj` i `<pre id="result">`.
  - `tests/make_fixtures.py`: skriver alla fixturer under `tests/fixtures/`; körs om när motorn ändras.

- [ ] **Step 1:** `make_fixtures.py` skriver `vault-sample.enc` = `encrypt({"hej": "världen", "n": 1.5}, "TEST-KOD", iter=1000)`.
- [ ] **Step 2:** `tests/js/vault.test.js`: `decrypt(sample, "TEST-KOD")` ger `{"hej":"världen","n":1.5}`; `decrypt(sample, "fel")` avvisar med meddelandet ovan; ett kuvert med ändrad `ct` avvisar.
- [ ] **Step 3:** Öppna http://localhost:8771/tests/js/run.html → FAIL (vault.js saknas).
- [ ] **Step 4:** Implementera med `crypto.subtle.importKey("raw", …, "PBKDF2")`, `deriveKey` till `AES-GCM` 256, `decrypt`.
- [ ] **Step 5:** run.html visar `PASS`. Commit `Steg 9: dekryptering i webbläsaren + testsida`.

### Task 3: Dela ägarens data från marknadsdatan

**Files:**
- Modify: `fetcher/walter_fetch.py` (main: `daily` → `data/owner-cache.json`), `fetcher/walter_notis.py` (`notis` → `owner-cache.json`), `fetcher/walter_auto.py`, `.gitignore`
- Create: `tests/test_split.py`
- Git: `git rm --cached data/state.json data/paper-journal-V2.1-FIXAD.csv`, committa `data/state.enc` (skapas med `walter_vault.py las`), rensa `daily` och `notis` ur den spårade `data/cache.json`.

**Interfaces:**
- Produces:
  - `walter_fetch.OWNER_CACHE = ROOT / "data" / "owner-cache.json"` med `{"daily": {datum: värde}, "notis": {...}}`
  - `walter_fetch.build(state, cache, fetched_any, owner_cache=None)` – `daily` och `notis` läses från `owner_cache`, aldrig från `cache`
  - `walter_fetch.strip_private_cache(cache: dict) -> dict` (tar bort `daily`, `notis`)
  - `walter_vault.merge_daily(a: dict, b: dict) -> dict` (union; vid samma datum vinner `b`)
- `.gitignore`: `data/state.json`, `data/owner-cache.json`, `data/paper-journal-*.csv`, `reports/`

- **Före Step 5:** `state.enc` kräver en kod. Saknas `WALTER_OWNER_KEY` i `fetcher/.env`: kör `walter_vault.py ny-kod`, lägg koden i `fetcher/.env` och skriv den i rapporten till ägaren (ägaren sparar den i sin lösenordshanterare). Pusha inte grenen förrän ägaren har lagt koden som GitHub Secret (Task 12).
- [ ] **Step 1: Tester:** `test_strip_private_cache` (`daily`, `notis` borta, `market`/`fetchedAt`/`sources` kvar); `test_build_reads_daily_from_owner_cache` (Sharpe-räkningen får värden från `owner_cache["daily"]`, ett `daily` i `cache` ignoreras); `test_merge_daily` (`{"d1":1,"d2":2}` + `{"d2":3,"d3":4}` → `{"d1":1,"d2":3,"d3":4}`).
- [ ] **Step 2:** Kör → FAIL.
- [ ] **Step 3:** Implementera. Hämtaren skriver aldrig `daily`/`notis` till `cache.json` igen. `walter_auto.py` läser läget ur `data/state.json` (upplåst) som förut.
- [ ] **Step 4:** Kör → PASS. Kör `.venv\Scripts\python.exe fetcher\walter_fetch.py --offline` → bygger `state.js` utan fel.
- [ ] **Step 5:** `git status` visar varken `state.json` eller CSV:n som spårade. Commit `Steg 9: ägarens data ut ur repot, bara krypterad state.enc`.

### Task 4: Publik marknadsfil med daglig logg

**Files:**
- Create: `fetcher/walter_public.py`, `tests/test_public.py`
- Modify: `fetcher/walter_fetch.py` (`fetch_coingecko` hämtar även `pax-gold` → `market.gold = {"value": usd, "asOf": datum}`; `fetch_fx` hämtar även EUR/SEK → `market.eursek` på samma sätt som `usdsek`), `fetcher/walter_paper.py` (ta bort kommentaren "hämtas inte än")

**Interfaces:**
- Consumes: byggd state från `walter_fetch.build`, `walter_paper.prices_sek`, `walter_paper.suggest_mode`.
- Produces:
  - `snapshot(state: dict) -> dict` med exakt nycklarna `date, fetchedAt, ready, red, mode, lamps, px, usdsek, eursek, ethBtcAbove30dMa, btcLong, vix, spxBelowMa, rules`. `lamps` = `[{id, name, rule, status, value, asOf}]`; `px` = `{"BTC","ETH","GOLD"}` i SEK eller `null`; `mode` = `suggest_mode(red, "AVVAKTAR", rules)` om `ready` annars `null`; `ready` = alla 10 lampor har status.
  - `LOG_KEYS = ("date","ready","red","px","ethBtcAbove30dMa","vix","spxBelowMa")`
  - `append_log(log: list, snap: dict) -> list` – en rad per datum (senaste vinner), sorterad, aldrig kortad
  - `write_market_js(snap: dict, log: list, path) -> None` → `window.WALTER_MARKET = {"now": snap, "log": log};`
  - Loggen sparas mellan körningar i den publika `data/cache.json` under `marketLog`.
- [ ] **Step 1: Tester:** `test_snapshot_has_no_private_keys` (byggd från en fixtur-state med journal/portfölj/k4: inga av nycklarna `journal, portfolio, k4, capitalChange, daily, notis, proposal` finns någonstans i JSON-texten, sökt rekursivt); `test_not_ready_gives_null_mode` (en lampa `status: None` → `ready False`, `mode None`); `test_append_log_one_row_per_day` (två snapshots samma dag → en rad med den senares värden); `test_append_log_sorted_never_trimmed` (400 dagar in → 400 rader, stigande datum); `test_log_row_keys` (exakt `LOG_KEYS`).
- [ ] **Step 2:** Kör → FAIL.
- [ ] **Step 3:** Implementera. Hämtaren anropar `snapshot` + `append_log` efter `build` och skriver `data/market.js` (lägg den i `.gitignore` under "Genereras").
- [ ] **Step 4:** Kör → PASS. Kör hämtaren på riktigt (`hamta.bat`) och kontrollera att `market.js` har `px.GOLD` och `eursek` med värden eller `null` och `asOf`.
- [ ] **Step 5:** Commit `Steg 9: publik marknadsfil med daglig logg, PAXG och EUR/SEK`.

### Task 5: Publicering, läckspärr och Actionen

**Files:**
- Modify: `fetcher/walter_deploy.py`, `fetcher/walter_paper.py` (efter JA: `walter_vault.lock_state()`), `.github/workflows/walter-auto.yml`, `README_DEPLOY.md`
- Create: `tests/test_deploy_guard.py`

**Interfaces:**
- Consumes: Task 1 (`encrypt`, `owner_key`, `lock_state`, `unlock_state`), Task 3 (`OWNER_CACHE`, `merge_daily`, `strip_private_cache`), Task 4 (`market.js`).
- Produces:
  - `ALLOW = ["index.html", "cipher.html", "css", "js", "assets", "data/market.js", "data/cache.json", "data/owner.enc"]` (inte `state.js`, inte `reports`, inte `tests`)
  - `build_owner_enc(state: dict, owner_cache: dict, code: str) -> dict` = `encrypt({"state": state, "daily": …, "notis": …}, code)`
  - `leak_check(out_dir: Path) -> list[str]` – går igenom varje fil under `out_dir/data/` utom `owner.enc` (inte `js/`, där `app.js` lagligt nämner `portfolio` och `k4`), plus att ingen `reports/` eller `state.js` finns någonstans, och listar filer som innehåller någon av strängarna `"journal"`, `"portfolio"`, `"k4"`, `"capitalChange"`, `"daily"`, `"WALTER_OWNER_KEY"` eller filnamnen i `BLOCK`. Tom lista = OK. Annars stoppas publiceringen som i dag.
  - `push_source()` committar `data/state.enc` (inte `state.json`).
  - Saknas `WALTER_OWNER_KEY` publiceras sidan utan `owner.enc` och en varning skrivs (appen funkar ändå för andra).
- Workflow:
  1. `pip install -r fetcher/requirements.txt` flyttas före "Ska vi hämta nu?".
  2. Nytt steg "Lås upp" (env `WALTER_OWNER_KEY: ${{ secrets.WALTER_OWNER_KEY }}`): `python fetcher/walter_vault.py las-upp`, och om gh-pages har `data/owner.enc`: dekryptera den och slå ihop dess `daily`/`notis` in i `data/owner-cache.json` med `merge_daily`.
  3. `WALTER_OWNER_KEY` skickas även till hämta-, notis- och deploy-stegen.
  4. `push.paths`: `data/state.json` → `data/state.enc`, lägg till `fetcher/**`.
- [ ] **Step 1: Tester:** `test_leak_check_finds_journal` (temp-mapp med `data/x.js` som innehåller `"journal"` → listas); `test_leak_check_ignores_owner_enc`; `test_leak_check_clean_market_js` (en `market.js` från Task 4:s fixtur → tom lista); `test_owner_enc_roundtrip` (`decrypt(build_owner_enc(s, oc, "k"), "k")["state"] == s`).
- [ ] **Step 2:** Kör → FAIL.
- [ ] **Step 3:** Implementera. Uppdatera `README_DEPLOY.md` med ägarens engångssteg: `walter_vault.py ny-kod`, spara koden i lösenordshanterare, lägg den i `fetcher/.env` och som GitHub Secret `WALTER_OWNER_KEY`.
- [ ] **Step 4:** Kör → PASS. Kör `walter deploy` utan push (sätt inte `WALTER_PAGES_REPO`) och kontrollera `deploy/`: ingen `state.js`, ingen `reports/`, `owner.enc` finns, `leak_check` tom.
- [ ] **Step 5:** Commit `Steg 9: publicera bara marknaden + krypterad ägarfil, läckspärr`.

### Task 6: Trade-motorn i JS + ikapp-räkning

**Files:**
- Create: `js/engine.js`, `tests/js/engine.test.js`
- Modify: `tests/make_fixtures.py` (skriver `tests/fixtures/engine-cases.json`)

**Interfaces:**
- Consumes: logg-raderna från Task 4 (`LOG_KEYS`), `rules`.
- Produces (`window.WalterEngine`, inga DOM-anrop, samma matte och avrundning som `walter_paper.py`):
  - `suggestMode(red: number, current: string, rules) -> "PARKERA"|"AVVAKTAR"|"NORMAL"|"OFFENSIV"`
  - `propose(user, row, rules, exchange) -> {ready, red, mode, currentMode, trades:[{asset, side:"köp"|"sälj", units, priceSek, sek, feeSek}], valueSek, plain, missing:[asset]}` – `fee = (exchange.takerPct + exchange.slippagePct + (exchange.quote !== "SEK" ? exchange.fxPct : 0)) / 100`; en tillgång som börsen saknar (`exchange.assets[a] !== true`) får mål 0 och hamnar i `missing`.
  - `apply(user, proposal, date) -> journalEntry` (muterar `user`: positioner med genomsnittsmetoden, kontanter, `history`, `mode`, `journal` överst, `trades`-listan)
  - `levelFor(user, row, rules, levels) -> 1|2|3` – Level 2 via `rules.unlock.early` eller `.normal` (dagar sedan `user.startDate`, marknadsvinst %, drawdown %, gröna lampor = `10 - row.red`), Level 3 via `levels["3"].gainPct` och `.maxDd`. Nivån är klistrig: `max(user.level, levelFor(...))`. Upplåsning ger en journalpost.
  - `catchUp(user, log, rules, levels, exchange) -> {user, events:[journalEntry]}` – spelar upp varje loggrad med `date > user.lastDay` i datumordning; rad med `ready: false` ger ingen affär och inget lägesbyte; sätter `user.lastDay`.
  - `summary(events) -> string` – t.ex. `"Medan du var borta gjorde jag 2 affärer: köpte bitcoin för 12 000 kr och sålde …"`; tom lista → `""`.
- [ ] **Step 1:** `make_fixtures.py` skriver `engine-cases.json`: minst 8 fall (OFFENSIV från kontanter, NORMAL halva taken, AVVAKTAR rör inget, PARKERA säljer allt, buffert 6 röda från PARKERA vilar kvar, buffert 5 röda vaknar, ETH-villkor uppfyllt på Level 2, guld vid VIX > 20 på Level 3 även i PARKERA) med indata och förväntat utfall räknat av `walter_paper.propose`/`apply` (Python är facit; `asOf`-fältet jämförs inte).
- [ ] **Step 2: JS-tester:** `parity_<fall>` för varje fall (affärer, belopp, kontanter, läge lika med Python); `missing_paxg_stays_cash` (börs utan `GOLD`, Level 3, VIX 25 → ingen guldaffär, `missing` = `["GOLD"]`, `plain` innehåller "Guld finns inte på din börs"); `catchup_skips_not_ready` (rad med `ready:false` → ingen händelse, läget oförändrat); `catchup_gaps` (logg med 1, 2, 10 okt; `lastDay` 30 sep → exakt tre dagar spelas, inga påhittade 3–9 okt); `catchup_90_days` (90 rader → klar på under 200 ms); `level2_early_unlock` (dag 15, +20 %, DD 7 %, 7 gröna → level 2 och en journalpost); `level_sticky` (vinsten faller efter upplåsning → nivån står kvar); `summary_two_trades`.
- [ ] **Step 3:** run.html → FAIL.
- [ ] **Step 4:** Implementera.
- [ ] **Step 5:** run.html → PASS. Commit `Steg 9: trade-motorn i JS med ikapp-räkning`.

### Task 7: Börslistan

**Files:**
- Create: `js/exchanges.js`, `tests/js/exchanges.test.js`

**Interfaces:**
- Produces: `window.WALTER_EXCHANGES = [{id, name, licence:{country, authority, register:"ESMA"}, quote:"EUR"|"USD"|"SEK", assets:{BTC:bool, ETH:bool, GOLD:bool}, takerPct, slippagePct, fxPct, source:url, checked:"YYYY-MM-DD"}]`, sorterad på namn.
- [ ] **Step 1: Research (ingen kod):** för varje kandidat (Kraken, Coinbase, Bitstamp, Bybit EU, OKX, Bitpanda, Crypto.com, Safello) – kolla i ESMA:s interim-register för CASP och/eller FI:s register att tillståndet finns och gäller Sverige; hämta lägsta tier taker-avgift från börsens officiella avgiftssida; kolla om ETH och PAXG går att handla. Ta bara med börser som klarar tillståndskollen. `slippagePct` = 0,2 för alla (samma antagande som `rules.withdrawalFees`). `fxPct` = börsens egen växlingsavgift om den finns publicerad, annars `rules.withdrawalFees.fxPct` (1) och skriv det i en kommentar.
- [ ] **Step 2: Tester:** `all_have_source_and_date`; `no_binance`; `fees_are_numbers` (takerPct, slippagePct, fxPct ändliga, 0–5); `assets_btc_true` (alla har BTC, annars hör de inte hemma här).
- [ ] **Step 3:** run.html → FAIL. **Step 4:** skriv filen. **Step 5:** PASS, commit `Steg 9: MiCA-börser med avgifter, källa och datum`.

### Task 8: Uppstart, användarens lagring och kopia

**Files:**
- Create: `js/user-state.js`, `js/boot.js`, `tests/js/user-state.test.js`
- Modify: `js/app.js` (hela IIFE:n blir `window.WalterApp = { start(S, ctx) {…} }`; `S` kommer som argument, inte från `window.WALTER_STATE`), `index.html` (skriptordning nedan)

**Interfaces:**
- Consumes: `WalterVault.decrypt`, `WalterEngine.catchUp/summary/levelFor`, `WALTER_EXCHANGES`, `WALTER_MARKET`.
- Produces:
  - `WalterUser.load() -> user | null`, `WalterUser.save(user) -> boolean` (false när lagring är blockerad), `WalterUser.storageOk() -> boolean`
  - `WalterUser.create(amountSek: number, exchangeId: string, today: string) -> user` – `{v:1, startDate, exchangeId, start, level:1, mode:"AVVAKTAR", lastDay:<senaste loggdatum eller today>, portfolio:{start, value, peak, holdings:{BTC:0,ETH:0,GOLD:0,CASH:start}, positions:{}, firstTrade:null, history:[{date, value:start, cash:start, note:"start", flow:start}]}, journal:[], trades:[]}`
  - `WalterUser.exportFile(user) -> Blob` (filnamn `walter-kopia-YYYY-MM-DD.json`), `WalterUser.importText(text) -> user` (kastar `Error("Det här är ingen Walter-kopia")` om `v !== 1` eller fält saknas)
  - `WalterUser.toState(user, market) -> WALTER_STATE` – samma form som ägarens `state.js` som `app.js` läser: `version, startDate, updatedAt, fetchedAt, mode, level, levels, portfolio, journal, lamps, lampScore {red,total,asOf,source}, market, rules, k4: []`, plus `proposal` från `WalterEngine.propose` på `market.now`.
  - `ctx` till `WalterApp.start`: `{who: "owner-local"|"owner"|"user", exchange, catchUpText, storageOk}`
  - `boot.js`-ordning: (1) finns `window.WALTER_STATE` → `owner-local`; (2) finns `walter.ownerKey` → hämta `data/owner.enc`, dekryptera, `owner` (vid fel: ta bort nyckeln, visa beskedet "Koden stämde inte. Du ser den vanliga appen." och fortsätt); (3) visa landningen om `sessionStorage.walterEntered` saknas; (4) `GÅ IN` → finns användare: `catchUp`, spara, starta appen; annars introt (Task 10).
  - `index.html`: `data/market.js`, `data/state.js` (finns bara lokalt; `onerror` ignoreras), `js/vault.js`, `js/engine.js`, `js/exchanges.js`, `js/user-state.js`, `js/landing.js`, `js/intro.js`, `js/app.js`, `js/boot.js`.
- [ ] **Step 1: Tester:** `create_shape`; `export_import_roundtrip`; `import_rejects_garbage` (`"{}"` och `"hej"` → felet ovan); `storage_blocked` (ersätt `localStorage` med ett objekt som kastar → `save` ger `false`, `load` ger `null`, inget undantag); `toState_has_app_fields` (alla nycklarna ovan finns, `lampScore.total === 10`).
- [ ] **Step 2:** run.html → FAIL.
- [ ] **Step 3:** Implementera. I `app.js` ändras bara starten och läsningen av `S` i detta task.
- [ ] **Step 4:** run.html → PASS. Öppna http://localhost:8771/index.html lokalt (där `state.js` finns) → ägarens app ser ut som före ändringen (skärmdump före/efter).
- [ ] **Step 5:** Commit `Steg 9: uppstart som väljer ägare, ägare med kod eller användare`.

### Task 9: Landningssidan

**Files:**
- Create: `css/landing.css`, `js/landing.js`
- Modify: `index.html` (sektion `<section id="landing">` före `<header>`)

**Interfaces:**
- Consumes: `WALTER_MARKET.now.lamps`.
- Produces: `WalterLanding.show(market, onEnter: () => void)`, `WalterLanding.hide()`.
- Utgå från `.superpowers/brainstorm/landning-v3.html` och behåll allt som står under "1. Landningssidan" i specen. Skillnader mot skissen: lamporna bakom glaset ritas från `market.now.lamps` (röd, grön, väntar = dämpad), temat använder `document.documentElement.dataset.theme` som appen (inte `body[data-v]`), `GÅ IN` sätter `sessionStorage.walterEntered = "1"` och tonar ut landningen (600 ms, ingen fade med reduced motion), canvasen stoppas när landningen är dold.
- [ ] **Step 1:** Implementera.
- [ ] **Step 2: Kontroll i webbläsaren** (preview `walter-2`, ta bort `data/state.js` tillfälligt eller använd en ny flik utan den – byggaren väljer): ljust och mörkt, bredd 360, 768, 1280; kickern bryts aldrig; inget överlappar; musen torkar glaset; temaval följer med in i appen och tillbaka; reduced motion (via `resize_window`/emulering eller CSS-kontroll) ger stilla sida. Ta skärmdumpar.
- [ ] **Step 3:** Commit `Steg 9: filmisk landningssida`.

### Task 10: Intro – Walter presenterar sig, summa, börs

**Files:**
- Create: `js/intro.js`, `tests/js/intro.test.js`
- Modify: `index.html` (`<section id="intro" hidden>`), `css/landing.css` (introt delar glasrutan)

**Interfaces:**
- Consumes: `WalterUser.create/save`, `WALTER_EXCHANGES`.
- Produces: `WalterIntro.start(onDone: (user) => void)`; `WalterIntro.parseAmount(text: string) -> number | null` (accepterar `"10 000"`, `"10000"`, `"10 000 kr"`, `"2,5 miljoner"` → nej; bara siffror, mellanslag och `kr`; 100 ≤ belopp ≤ 100 000 000; annars `null`).
- Rutor (texten exakt):
  1. "Jag är Walter. Jag läser marknaden varje dag – tio signaler, alltid samma regler."
  2. "Jag förvaltar åt dig: köper när läget är bra, vilar när det stormar. Aldrig mer än 75 % investerat."
  3. "Jag rör inga riktiga pengar. Det kan jag inte än. Vi börjar med låtsaspengar, tills du är redo."
  Knappen "Hoppa över" syns på alla tre och går direkt till summan.
- Summa: ett fält, knappen "Fortsätt" är avstängd tills `parseAmount` ger ett tal. Börs: en lista med namn, land för tillståndet och taker-avgift; saknas PAXG eller ETH står det under namnet ("Guld finns inte här").
- Lagring blockerad → en rad ovanför knappen: "Din webbläsare låter mig inte spara. Allt försvinner när du stänger fliken." Introt går ändå att slutföra.
- [ ] **Step 1: Tester:** `parse_ok` (`"10 000"`→10000, `"250000 kr"`→250000); `parse_rejects` (`""`, `"0"`, `"-5"`, `"abc"`, `"99"`, `"1e9"`, `"200000000"` → `null`).
- [ ] **Step 2:** FAIL → implementera → PASS.
- [ ] **Step 3: Kontroll i webbläsaren:** hela vägen landning → intro → hoppa över → summa → börs → översikten, på 360 och 1280, båda teman. Skärmdumpar.
- [ ] **Step 4:** Commit `Steg 9: Walter presenterar sig, summa och börs`.

### Task 11: Appen för användare – förklaringar, Pro-läge, ärlighet

**Files:**
- Modify: `js/app.js`, `css/walter.css`, `index.html`

**Interfaces:**
- Consumes: `ctx` från Task 8, `EXPLAIN` i `app.js` (~rad 486).
- Ändringar:
  - `ctx.who === "user"`: K4-fliken och rapportlänkarna döljs; PAPER/LIVE-knapparna och LIVE-dialogen ersätts av texten "Live: inte än" (ingen knapp); förslagsrutan säger vad Walter gjorde, inte "godkänn med paper.bat"; `ctx.catchUpText` visas överst som notis om den inte är tom.
  - Förklaringar: varje lampa på översikten får sin `EXPLAIN`-text under sig (`<p class="explain">`); läget, Sharpe ("Avkastning per risk. Visas efter 30 dagars handel."), drawdown ("Hur långt värdet har fallit från sin högsta punkt.") och nivåerna får en mening var. Gäller alla `who`.
  - Pro-läge: inställningen `walter.settings.pro` (boolean, standard `false`). En växel "Pro-läge – dölj förklaringarna" i Inställningar. `body.pro .explain { display: none }`. Fasta höjder där förklaringar döljs, så att inget hoppar mer än nödvändigt.
  - Inställningar för `user`: knapparna "Spara kopia" och "Läs in kopia" (Task 8), texten "Din Walter finns bara i den här webbläsaren. Rensar du den är portföljen borta – spara en kopia ibland." och "Börja om" (bekräftelse med texten BÖRJA OM).
  - Inställningar för alla som inte är `owner-local`: fältet "Lås upp min Walter" (kod → sparas i `walter.ownerKey` först när dekrypteringen lyckats; fel kod → "Koden stämde inte.").
- [ ] **Step 1: Kontroll i webbläsaren** för `user`: K4 syns inte, ingen LIVE-knapp, "Live: inte än" syns, förklaringar syns, Pro-läge döljer dem, spara/läs in kopia fungerar (läs in den sparade filen i en ny flik → samma portfölj), fel kod ger beskedet.
- [ ] **Step 2: Kontroll för `owner-local`:** som före steg 9 (K4, rapporter, LIVE-knapparna finns kvar för ägaren).
- [ ] **Step 3:** Commit `Steg 9: användarvy med förklaringar, Pro-läge och "Live: inte än"`.

### Task 12: Hela vägen + dokumentation

**Files:**
- Modify: `CLAUDE.md` (data-flödet: `state.enc`, `owner-cache.json`, `market.js`, `owner.enc`, valvet, appens filer, användarens lagring), `docs/ROADMAP.md` (steg 9 ✓ med datum, nytt steg för SOL/andra valutor, öppna frågan om git-historiken), `README_DEPLOY.md`

- [ ] **Step 1:** `python -m unittest discover -s tests -v` → alla PASS. run.html → PASS.
- [ ] **Step 2: Genomgång i webbläsaren** (ny flik, tom lagring): landning → intro → översikt; ladda om → ingen landning i samma flik; ny flik → landning, GÅ IN → direkt till översikten; ändra `lastDay` bakåt i `localStorage` → ikapp-notisen visas och stämmer mot loggen; ange ägarkoden i Inställningar → ägarens Walter visas; mobil 360 och dator 1280, ljust och mörkt. Skärmdumpar.
- [ ] **Step 3:** Kontrollera `deploy/` en sista gång med `leak_check` och sök efter ägarens startbelopp (`254600`) i alla publicerade filer utom `owner.enc` → inga träffar.
- [ ] **Step 4:** Uppdatera dokumenten. Commit `Steg 9: dokumentation`.
- [ ] **Step 5:** Ägarens engångssteg listas för ägaren (görs inte av byggaren): skapa koden, lägg den i `fetcher/.env` och som GitHub Secret `WALTER_OWNER_KEY`, skriv in den i mobilen. Pusha och öppna PR först när ägaren har lagt in sin Secret, annars publicerar Actionen sidan utan `owner.enc`.
