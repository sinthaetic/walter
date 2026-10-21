# WALTER audit log

## 2026-10-21 – Granskning av installations-prompten (Meta AI)

Källa: lång installations-prompt ("Walter-installeraren"). CLAUDE.md är INTE ändrad – rättelserna ligger bara här tills du bestämmer.

### Hallucinationer / ej verifierat
- Hittade fel: `caveman@claude-plugins-official` – finns inte i officiella marknadsplatsen. Fixat till: installeras inte.
- Hittade fel: `/compact`, `/rewind` beskrivs som skills att installera – de är inbyggda i Claude Code. Fixat till: ingen installation.
- Ej verifierat: `/handoff`, Magpie, Orca, Hindsight, PageIndex, ponytail, Headroom, codeburn, Taste Skill, transitions.dev, designlang, Attention Span, Agent Reach. Stjärnantal ser påhittade ut. Fixat till: installeras inte förrän det finns ett konkret behov och källan är kontrollerad.
- Verifierat finns: superpowers, security-guidance, claude-code-setup, code-review, playwright, figma, frontend-design (officiella); graphifyy (PyPI, Graphify-Labs/graphify); krakenex (PyPI, veox/python3-krakenex).
- Miljö: WalterVault = `C:\Users\jujut\walter`. Inga `WALTER_*.md`, `paper-journal-V2.38.csv` eller `k4_journal` finns. Node/npm/git saknas, så npm-verktyg (Playwright, GSAP, React Bits m.fl.) kan inte installeras.

### Logik- och formelfel
1. Hittade fel: BALANSERAT "50 200 brutto → 51 400 netto". Fixat till: netto är alltid ≤ brutto (netto = brutto − avgifter − ev. skattereserv).
2. Hittade fel: "Green 11/10", "Green 11/Red 8" med 10 lampor, och "Green Core 5/9". Fixat till: räkna X/10; regeln i CLAUDE.md gäller (PARKERA vid 7/10 risk-off).
3. Hittade fel: fallback USDSEK 10,8 – samma mekanism som 87 SEK-buggen. Fixat till: SEK = BTC_Amount × BTC_Price_USD × USDSEK_live; vid fel används senast sparade live-kurs med tidsstämpel + varning, annars `null` ("väntar på data"). Aldrig fast 10,8.
4. Hittade fel: K4-kolumner motsäger sig (steg 2 vill ha `slippage_sek`/`fx_fee_sek`, steg 3 inte). Fixat till: kolumner köpdatum, säljdatum, antal, försäljningspris_sek (faktiskt, slippage redan inbakad), omkostnad_sek (FIFO, inkl. köp-courtage), trading_fee_sek (sälj-courtage), vinst_forlust_sek, typ. Bankens FX-avgift efter försäljning hör inte till K4. Vinster och förluster på separata rader; förlust 70 % avdragsgill.
5. Hittade fel: max dagsförlust 0,5 % + 1 % risk per trade – en enda SL bryter gränsen. Fixat till: välj ett – t.ex. 0,5 % risk/trade med 1 % dagsgräns, eller behåll 1 %/trade och sätt dagsgräns ≥ 1 %.
6. Hittade fel: "Kelly 35 % cap" blandas ihop med "BTC max 35 %" (Level 1). Fixat till: två separata gränser; positionsstorlek = min(Kelly-andel, 35 % BTC-tak, risk-regeln).
7. Hittade fel: Level-upplåsning "baserat på time-in-market" ändrar befintliga regler (30 dagar, > 550 kr, DD < 12 %, Sharpe > 1). Fixat till: CLAUDE.md-reglerna gäller; paus-vid-EXIT är ett förslag som kräver ditt beslut.
8. Hittade fel: uttagsexemplet anger avgifter 821 och 817 SEK för samma fall. Fixat till: ~817 SEK (203 + 102 + 12 + 500); avgiftssatser ska vara inställningar, inte hårdkodade, och EUR/SEK hämtas live.
9. OK: TP1/TP2/SL-beloppen (90,76 / 97,74 / 82,03 SEK på bas 87,27 SEK) stämmer – men bara om USDSEK är oförändrad.

### Krockar med CLAUDE.md (kräver ditt beslut)
- Nytt W-märke/brand-filer vs "Byt aldrig ut, generera aldrig nya" logos.
- Nya brand-färger vs liquid glass-paletten.
- React/Vite-dashboard vs "statisk frontend, ingen build".
- Supabase/Vercel (molnet) vs "allt lokalt".

### Säkerhet
- Magpie (tredjeparts-gateway) = samma riskklass som OmniRoute. Fixat till: skippas.
- Scrapling StealthyFetcher (Cloudflare-bypass) behövs inte – Riksbanken och FRED har gratis officiella API:er. Fixat till: använd officiella API:er.
- "Withdraw OFF"-kontroll via REST: oklart om Kraken exponerar nyckelns behörigheter. Måste verifieras mot Kraken-dokumentationen innan den byggs; tills dess gäller manuell kontroll vid nyckelskapande.
- API-nycklar läggs alltid in manuellt av dig. Dashboard får aldrig läsa `.env`.
