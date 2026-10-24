// WALTER – renderar data/state.js i nya designen (okt 2026). Ingen build, inga beroenden.
// Sidor via adressens #: översikt, pro, logg, k4, inställningar. W-Cipher är egen sida (cipher.html).
(function () {
  "use strict";

  // Startas av js/boot.js med ett WALTER_STATE-objekt: ägaren lokalt, ägaren med kod eller användaren.
  // ctx = {who: "owner-local"|"owner"|"user", exchange, catchUpText, storageOk} (användarvyn läser den).
  function start(S, ctx) {
  const $ = (id) => document.getElementById(id);

  // ---------- Lokal lagring (bara den här webbläsaren, try/catch om den är blockerad) ----------
  const store = {
    // area = "localStorage" eller "sessionStorage"; slås upp inne i try, eftersom själva åtkomsten kan kasta
    get(k, def, area = "localStorage") { try { const v = window[area].getItem(k); return v ? JSON.parse(v) : def; } catch { return def; } },
    set(k, v, area = "localStorage") { try { window[area].setItem(k, JSON.stringify(v)); } catch { /* lagring blockerad */ } }
  };
  const who = (ctx && ctx.who) || "owner-local";
  const isUser = who === "user";
  // Användarens plan, mål, inställningar och LIVE-flagga har egna nycklar, så att ägarens värden aldrig blandas in.
  const own = (k) => keyFor(who, k);
  const settings = store.get(own("settings"), {});
  // Startkapital kommer bara från state.json. Ett gammalt eget värde (från 500-kronorstiden) rensas bort.
  if ("startCapital" in settings) { delete settings.startCapital; store.set(own("settings"), settings); }
  // Pro-läge: förklaringarna döljs (walter.settings.pro, standard false)
  document.body.classList.toggle("pro", settings.pro === true);
  // Uttagsavgifter: ägaren har standard i state.json (rules.withdrawalFees), användaren sin börs (ctx.exchange)
  // med Walters standard för det börsen inte publicerar (SEPA). Kan skrivas över under Inställningar.
  // Aldrig hårdkodade här. null = inte angivet.
  const FEE_KEYS = ["takerPct", "slippagePct", "sepaEur", "fxPct"];
  const ex = isUser && ctx.exchange ? ctx.exchange : null;
  const ruleFees = S.rules.withdrawalFees || {};
  const feeDefaults = ex ? { takerPct: ex.takerPct, slippagePct: ex.slippagePct, sepaEur: ruleFees.sepaEur, fxPct: ex.fxPct } : ruleFees;
  const feeName = ex ? ex.name : isUser ? "Börsen" : "Kraken";
  const fees = Object.fromEntries(FEE_KEYS.map((k) => [k,
    Number.isFinite(settings[k]) ? settings[k] : Number.isFinite(feeDefaults[k]) ? feeDefaults[k] : null]));

  // ---------- Format ----------
  const nf = (d = 0) => new Intl.NumberFormat("sv-SE", { minimumFractionDigits: d, maximumFractionDigits: d });
  const kr = (v) => nf(0).format(v) + " kr";
  const kr2 = (v) => nf(2).format(v) + " kr";
  const pct = (v, d = 1) => (v > 0 ? "+" : v < 0 ? "−" : "") + nf(d).format(Math.abs(v)) + " %";
  const usd = (v) => "$" + nf(0).format(v);
  const MONTHS = ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep", "okt", "nov", "dec"];
  const day = (iso) => { const d = new Date(iso.slice(0, 10) + "T12:00:00"); return d.getDate() + " " + MONTHS[d.getMonth()]; };
  const MONTHS_LONG = ["januari", "februari", "mars", "april", "maj", "juni", "juli", "augusti", "september", "oktober", "november", "december"];
  const monthYear = (iso) => `${MONTHS_LONG[+iso.slice(5, 7) - 1]} ${iso.slice(0, 4)}`;
  const addMonthsIso = (iso, n) => {
    const d = new Date(iso + "T12:00:00");
    d.setMonth(d.getMonth() + n);
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  };
  // En mening per rad (egna block-spans), så att en rad aldrig börjar mitt i en mening. Bara för korta påståenden.
  const lines = (el, text) => {
    el.textContent = "";
    String(text).split(/(?<=[.!?])\s+(?=[A-ZÅÄÖ])/).forEach((t, i) => {
      if (i) el.append(" ");
      const s = document.createElement("span");
      s.className = "line"; s.textContent = t; el.appendChild(s);
    });
  };
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const pad = (n) => String(n).padStart(2, "0");
  // "22.10 · 20:11" (statusraden) och "22 okt 20:11" (löptext)
  const dotStamp = (iso) => { const d = new Date(iso); return `${pad(d.getDate())}.${pad(d.getMonth() + 1)} · ${pad(d.getHours())}:${pad(d.getMinutes())}`; };
  const stamp = (iso) => {
    if (!iso) return "okänt";
    const d = new Date(iso);
    return `${d.getDate()} ${MONTHS[d.getMonth()]} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
  };
  // Små belopp med ören (624,77), stora i hela kronor
  const amount = (v) => new Intl.NumberFormat("sv-SE", { maximumFractionDigits: Math.abs(v) < 10000 ? 2 : 0 }).format(v);

  const daysSince = (iso) => {
    const start = new Date(iso + "T00:00:00");
    const now = new Date();
    now.setHours(0, 0, 0, 0);
    return Math.floor((now - start) / 86400000) + 1;
  };

  // true = uppfyllt (grön), false = inte (röd), null = väntar på data (streckad)
  const check = (ok) => ok === null || ok === undefined
    ? '<span class="dot" title="Väntar på data"></span>'
    : ok ? '<span class="dot green" title="Uppfyllt"></span>'
         : '<span class="dot red" title="Inte uppfyllt"></span>';

  // ---------- Tema (ljust standard, mörkt via knappen) ----------
  const themeBtn = $("theme");
  const syncTheme = () => {
    const dark = document.documentElement.dataset.theme === "dark";
    themeBtn.setAttribute("aria-label", dark ? "Byt till ljust läge" : "Byt till mörkt läge");
    document.querySelector('meta[name="theme-color"]').content = dark ? "#0A1216" : "#D7E0E3";
  };
  themeBtn.addEventListener("click", () => {
    const dark = document.documentElement.dataset.theme !== "dark";
    if (dark) document.documentElement.dataset.theme = "dark"; else delete document.documentElement.dataset.theme;
    try { localStorage.setItem("walterDark", dark ? "1" : "0"); } catch { /* lagring blockerad */ }
    syncTheme();
  });
  syncTheme();

  // ---------- Härledda värden ----------
  const pf = S.portfolio;
  const m = S.market;
  const dd = pf.peak > 0 ? ((pf.peak - pf.value) / pf.peak) * 100 : 0;
  const invested = pf.value > 0 ? (pf.value - pf.holdings.CASH) / pf.value : 0;
  // Alltid 10 lampor. Walter vilar när rules.parkeraAtRed (7) av 10 är risk-off.
  const LAMPS = 10;
  const red = S.lampScore.red;
  const total = LAMPS;
  const lampCountOk = S.lamps.length === LAMPS && S.lampScore.total === LAMPS;
  const green = total - red;
  const days = daysSince(S.startDate);
  const parked = S.mode === "PARKERA";
  const start = pf.start;
  // Insättningar = startkapital + manuella påfyllningar (capitalChange.manualTopUp). Bara det som är över
  // insättningarna är marknadsvinst – den räknas för vinst, upplåsning och OPTIMERAT.
  // Månadssparandet (historikrader med note "månadssparande") är också insättningar, aldrig vinst.
  const savedIn = (pf.history || []).reduce((t, h) => t + (h && h.note === "månadssparande" && h.flow > 0 ? h.flow : 0), 0);
  const topUp = ((pf.capitalChange && pf.capitalChange.manualTopUp) || 0) + savedIn;
  const deposits = start + topUp;
  const marketGain = pf.value - deposits;
  const marketPct = deposits > 0 ? (marketGain / deposits) * 100 : 0;

  // Journalens läge → ordet användaren ser. Läget ändras bara via journalen (Walter skriver posten själv).
  // Lampnivåerna står i rules.modes / parkeraAtRed / wakeAtRed och räknas i fetcher/walter_paper.py.
  const MODES = {
    PARKERA: { word: "VILAR", acc: "red", quote: "Marknaden är orolig. Pengarna står i kontanter tills datan vänder." },
    AVVAKTAR: { word: "AVVAKTAR", acc: "blurple", quote: "Signalerna pekar åt olika håll. Jag rör ingenting förrän bilden klarnar." },
    NORMAL: { word: "KÖPER LITE", acc: "green", quote: "Fler lampor är gröna. Jag går in med en liten del, resten ligger kvar." },
    OFFENSIV: { word: "KÖPER", acc: "green", quote: "Läget är bra. Jag går in, aldrig över 75 %. En fjärdedel ligger alltid kvar." }
  };
  const modeOf = (k) => MODES[k] || { word: String(k || "OKÄNT"), acc: "blurple", quote: isUser ? "Jag känner inte igen läget i min egen anteckning. Läs in en kopia eller börja om." : "Journalen har ett läge Walter inte känner igen. Rätta det i state.json." };
  const MODE = modeOf(S.mode);

  // USDSEK: senast sparade live-kurs med datum, annars null. Ingen fast reservkurs.
  // Funktion, eftersom Uppdatera-knappen kan byta ut m.usdsek / m.btc mot färskare värden.
  const fx = () => {
    const usdsek = m.usdsek && m.usdsek.value != null ? m.usdsek : null;
    const ageDays = usdsek ? Math.floor((Date.now() - new Date(usdsek.asOf + "T12:00:00")) / 86400000) : null;
    const stale = ageDays != null && ageDays > 4;
    const btcSek = usdsek && m.btc.value != null ? m.btc.value * usdsek.value : null;
    return { usdsek, stale, btcSek };
  };

  // Taket på nuvarande level = summan av upplåsta tak (Level 1: 35 %, Level 3: 75 %)
  // Autopiloten (rules.strategy, standard sedan 23 okt 2026): fasta andelar, koll en dag i veckan.
  // Lamporna och läget säger bara hur marknaden mår, och Levels låser inget.
  const AUTO = (S.rules.strategy || "autopilot") === "autopilot";
  const unlocked = AUTO ? { BTC: true, ETH: true, GOLD: true } : { BTC: S.level >= 1, ETH: S.level >= 2, GOLD: S.level >= 3 };
  const levelCap = Math.min(S.rules.maxInvested, ["BTC", "ETH", "GOLD"].reduce((a, k) => a + (unlocked[k] ? S.rules.caps[k] : 0), 0));
  // Autopilotens andelar: det motorn faktiskt använder (proposal.weights; en tillgång börsen saknar = 0),
  // annars rules.caps med börsens saknade tillgångar som 0.
  const apWeights = (S.proposal && S.proposal.weights) || ["BTC", "ETH", "GOLD"].reduce((o, k) => {
    o[k] = ex && (!ex.assets || ex.assets[k] !== true) ? 0 : S.rules.caps[k]; return o; }, {});
  const AP_NAMES = { BTC: "bitcoin", ETH: "ethereum", GOLD: "guld" };
  const apNote = (k, txt) => (apWeights[k] > 0 ? txt : "finns inte på din börs");
  const apDay = String((S.rules.decision && S.rules.decision.weekday) || "söndag").toLowerCase();
  const apBand = S.rules.decision && S.rules.decision.bandPp != null ? S.rules.decision.bandPp : 5;
  const E = window.WalterEngine;
  const apNext = (S.proposal && S.proposal.nextCheck) || (E && S.updatedAt ? E.nextCheck(S.updatedAt, S.rules) : null);
  const apNextText = apNext && E ? E.dayText(apNext) : null;
  const apCash = 1 - ["BTC", "ETH", "GOLD"].reduce((a, k) => a + (apWeights[k] || 0), 0);
  const autoLine = "Jag håller kursen: " + ["BTC", "ETH", "GOLD"].filter((k) => apWeights[k] > 0)
    .map((k) => `${nf(0).format(apWeights[k] * 100)} % ${AP_NAMES[k]}`).concat(`${nf(0).format(apCash * 100)} % kontant`).join(" · ") +
    `. Jag justerar på ${apDay}ar om något glidit mer än ${apBand} procentenheter.`;

  // Rapporterna skickas 08:13 och 22:05 (se .github/workflows/walter-auto.yml)
  const nextReport = () => {
    const now = new Date(), mins = now.getHours() * 60 + now.getMinutes();
    return mins < 8 * 60 + 13 || mins >= 22 * 60 + 5 ? "08:13" : "22:05";
  };

  // ---------- Topp, sidfot ----------
  // Rapporterna (mejl) är ägarens. Användaren får ingen rapporttid.
  $("stamp").textContent = isUser ? "" : "NÄSTA RAPPORT " + nextReport();
  // Vad Walter gjorde medan sidan var stängd (boot.js räknade ikapp), överst som notis
  if (isUser && ctx.catchUpText) {
    const box = document.createElement("div");
    box.className = "panel catchup-note";
    box.setAttribute("role", "status");
    const p = document.createElement("p");
    p.className = "plain";
    lines(p, ctx.catchUpText);
    box.appendChild(p);
    const main = document.querySelector("main.page");
    main.insertBefore(box, main.firstChild);
  }

  // ================================================================
  // ÖVERSIKT
  // ================================================================
  // Autopiloten: det stora ordet är vad Walter gör. Lamporna säger hur marknaden mår.
  const MOOD = (E && E.MOODS && E.MOODS[S.mode]) || "okänd";
  $("status-line").textContent = (AUTO ? "AUTOPILOT · " : "STATUS · ") + (S.fetchedAt ? dotStamp(S.fetchedAt) : day(S.updatedAt));
  $("mode").innerHTML = `<span class="mode-light" style="color: var(--${AUTO ? "teal" : MODE.acc})" aria-hidden="true"><i></i><b></b></span>
    <h1 class="mode-name">${AUTO ? "AUTOPILOT" : esc(MODE.word)}</h1>`;
  // Ägarens läge byts via journalen, som Walter skriver själv i Actionen: säg rakt ut när lamporna redan pekar på något annat
  const Pnow = S.proposal || {};
  const pending = !AUTO && !isUser && Pnow.ready && Pnow.mode && Pnow.mode !== S.mode;
  $("quote").classList.toggle("auto", AUTO);
  lines($("quote"), AUTO
    ? autoLine + (apNextText ? ` Nästa koll ${apNextText}.` : "")
    : MODE.quote + (pending
      ? ` Lamporna säger nu ${modeOf(Pnow.mode).word} – Walter byter läge vid nästa körning i GitHub (högst en gång per dag).`
      : ""));
  $("mode-explain").textContent = AUTO
    ? `Marknaden är just nu ${MOOD} (${red} av ${total} varningar). Det ändrar inte vad jag gör: jag säljer det som stigit och köper det som fallit – få affärer, låga avgifter och lite skatt.`
    : "Röd lampa = varning, grön = lugnt. Få varningar och Walter köper, många varningar och han vilar i kontanter. Han köper aldrig för att lamporna är röda.";

  // ---------- Ringen: tio bågar, en per lampa ----------
  const lampState = (l) => (l.status === "red" ? "red" : l.status === "green" ? "green" : "wait");
  const nRed = S.lamps.filter((l) => l.status === "red").length;
  const nGreen = S.lamps.filter((l) => l.status === "green").length;
  const nWait = S.lamps.length - nRed - nGreen;
  const pt = (a, r) => { const t = (a - 90) * Math.PI / 180; return `${(75 + r * Math.cos(t)).toFixed(2)} ${(75 + r * Math.sin(t)).toFixed(2)}`; };
  const arcs = S.lamps.slice(0, LAMPS).map((l, i) =>
    `<path class="arc ${lampState(l)}" d="M ${pt(i * 36 + 3, 62)} A 62 62 0 0 1 ${pt(i * 36 + 33, 62)}" style="animation-delay:${(-i * 0.48).toFixed(2)}s"/>`).join("");
  const left = S.rules.parkeraAtRed - red;
  $("ring").innerHTML = `
    <div class="ring">
      <svg viewBox="0 0 150 150" role="img" aria-label="Tio lampor: ${nRed} röda, ${nGreen} gröna, ${nWait} väntar på data">
        <circle class="base" cx="75" cy="75" r="72"/>${arcs}
      </svg>
      <div class="ring-center" aria-hidden="true"><span class="num">${pad(red)}/${total}</span><span class="label">VARNINGAR</span></div>
    </div>
    <div class="legend">
      <span><i class="r"></i>${nRed} röda = varning</span>
      <span><i class="g"></i>${nGreen} gröna = lugnt</span>
      <span><i class="w"></i>${nWait} väntar</span>
      <span class="note">${AUTO ? `MARKNADEN: ${MOOD.toUpperCase()} · STYR INTE KÖPEN` : parked
        ? (red <= S.rules.wakeAtRed ? `LAMPORNA SÄGER VAKNA` : `VAKNAR VID ${S.rules.wakeAtRed}/${total}`)
        : `VILA VID ${S.rules.parkeraAtRed}/${total}${left > 0 ? ` · ${left} KVAR` : ""}`}</span>
    </div>`;

  // ---------- Portfölj ----------
  // Nästa månadssparande (när det är påslaget): "Nästa sparande 25 nov: 1 000 kr."
  const isoToday = (() => { const d = new Date(); return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`; })();
  const nextSave = AUTO && E && S.savings ? E.nextSavings(S.savings, pf.history, isoToday) : null;
  const saveLine = nextSave ? `Nästa sparande ${nextSave === isoToday ? "i dag" : day(nextSave)}: ${kr(S.savings.monthlySek)}.` : "";
  const avk = Math.abs(marketPct) < 0.005 ? "±0,00 %" : pct(marketPct, 2);
  $("pf").innerHTML = `
    <div class="pf-top">
      <div class="pf-value"><span class="label">PORTFÖLJ</span><strong>${kr(pf.value)}</strong></div>
      <div class="stats">
        <div><span>AVKASTNING</span><strong title="Marknadsvinst över alla insättningar">${avk}</strong></div>
        <div><span>KONTANT</span><strong>${nf(0).format((1 - invested) * 100)} %</strong></div>
        <div><span>INVESTERAT</span><strong title="${AUTO ? "Autopilotens mål" : `Tak på Level ${S.level}`}">${nf(0).format(invested * 100)} / ${nf(0).format((AUTO ? 1 - apCash : levelCap) * 100)} %</strong></div>
      </div>
    </div>
    ${saveLine ? `<p class="pf-save"><span class="dot teal" aria-hidden="true"></span>${esc(saveLine)}</p>` : ""}
    <div class="pf-foot"><a href="#wc">BITCOIN · W-CIPHER ↓</a><a href="#siffror">SIFFRORNA →</a></div>`;

  // ---------- Målet (valfritt): hur långt kvar, och hur mycket Walter redan flyttat till kontanter ----------
  (() => {
    const el = $("goal-card"), g = S.goal;
    if (!el) return;
    if (!AUTO || !g || !(g.amountSek > 0) || !/^\d{4}-\d{2}-\d{2}$/.test(g.date || "")) { el.hidden = true; return; }
    const f = S.proposal && typeof S.proposal.glide === "number" ? S.proposal.glide : E ? E.glideFactor(g, S.updatedAt) : 1;
    const share = pf.value > 0 ? pf.value / g.amountSek : 0;
    const glideTxt = f >= 1 ? `Walter börjar flytta gradvis till kontanter i ${monthYear(addMonthsIso(g.date, -24))}, 24 månader före.`
      : f <= 0 ? "Datumet är nått: Walter håller allt som kontanter."
      : `Walter flyttar gradvis till kontanter: nu ${nf(0).format(f * 100)} % av vanliga andelar.`;
    el.hidden = false;
    el.innerHTML = `
      <div class="panel-head"><span>MÅL · ${esc(String(g.name || "Mitt mål").toUpperCase())}</span><span class="num">${esc(monthYear(g.date).toUpperCase())}</span></div>
      <p class="goal-line">Mål: ${esc(g.name || "Mitt mål")} – ${kr(g.amountSek)} till ${esc(monthYear(g.date))}. Just nu ${kr(pf.value)} (${nf(0).format(share * 100)} %). ${esc(glideTxt)}</p>
      <div class="goal-track" role="progressbar" aria-label="Del av målet" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(Math.min(1, share) * 100)}">
        <span class="fill" style="width:${(Math.min(1, share) * 100).toFixed(1)}%"></span>
      </div>
      <div class="goal-legend"><span>0 KR</span><span>${f >= 1 ? "FULLA ANDELAR" : f <= 0 ? "ALLT KONTANT" : `ANDELAR ${nf(0).format(f * 100)} %`}</span><span>${esc(kr(g.amountSek).toUpperCase())}</span></div>
      <p class="explain">Inget löfte om att nå målet. I historiken gav det en lugnare resa men oftast mindre pengar – det är ett val för den som inte tål ett stort fall strax före datumet. <a href="#installningar">Ändra målet →</a></p>`;
  })();

  // ---------- W-Cipher under hjälten ----------
  // Samma graf som cipher.html i CIPHER-läget (js/cipher-chart.js), plus Walters lampor (data/pulse.js + market.js-loggen)
  // och Walters affärer ur journalen. Börsen: användarens om grafen har den, ägarens Kraken, annars W-Cipherns standard.
  // Lightweight Charts laddas först här (inte som blockerande skripttagg), så att resten av översikten ritas direkt.
  // Ett fel här får aldrig stoppa resten av översikten.
  (() => {
    const CC = window.WalterCipherChart, el = $("wc-chart");
    if (!el) return;
    const fail = () => { if ($("wc-live")) $("wc-live").textContent = "GRAFEN KUNDE INTE LADDAS"; };
    try {
      if (!CC || !window.WCipher) { fail(); return; }
      if ($("wc-copy")) CC.mountCopy($("wc-copy"));
      const CHART_EX = { kraken: "kraken", "bybit-eu": "bybit", "okx-europe": "okx" };
      const exId = isUser ? (ex && CHART_EX[ex.id]) || "binance" : "kraken";
      const pair = "BTC/" + CC.EX[exId].quote;
      const exName = { binance: "Binance", kraken: "Kraken", bybit: "Bybit", okx: "OKX", coinbase: "Coinbase" }[exId];
      const pulse = CC.mergePulse(window.WALTER_PULSE, (window.WALTER_MARKET && window.WALTER_MARKET.log) || []);
      const trades = CC.tradeMarks(S.journal);
      const extras = { pulse: pulse.length ? pulse : null, trades: trades.length ? trades : null };
      const TF_KEY = "walterOverviewTf";
      let tf = store.get(TF_KEY, "1D");
      if (!["4h", "1D", "1W"].includes(tf)) tf = "1D";
      const sync = () => document.querySelectorAll("#wc-tf button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.tf === tf)));
      // Samma rader på alla tidsramar (lamprutan syns bara på DAG/VECKA), så att panelen aldrig hoppar
      $("wc-legend").innerHTML = CC.legendHTML("cipher", extras);
      sync();
      CC.loadChartLib().then(() => {
        if (el._wc) el._wc.destroy();
        const graph = el._wc = CC.mount(el, { view: "cipher", wavePane: 0.32, pulsePane: 64 });
        graph.setExtras(extras);
        let loading = 0;
        const load = async (reset) => {
          const my = ++loading;
          if (reset) $("wc-live").textContent = "HÄMTAR …";
          try {
            const bars = await CC.fetchBars(exId, pair, tf);
            if (my !== loading) return;
            graph.setBars(bars, tf, reset);
            $("wc-live").textContent = `${pair} · ${exName.toUpperCase()} · ${new Date().toLocaleTimeString("sv-SE", { hour: "2-digit", minute: "2-digit" })}`;
          } catch (e) {
            if (my !== loading) return;
            $("wc-live").textContent = "KUNDE INTE HÄMTA · " + exName.toUpperCase();
            if (reset) graph.clear();
          }
        };
        $("wc-tf").onclick = (e) => {
          const b = e.target.closest("button[data-tf]");
          if (!b || b.dataset.tf === tf) return;
          tf = b.dataset.tf; store.set(TF_KEY, tf); sync(); load(true);
        };
        // Ljust/mörkt byts av knappen i toppen: läs om färgerna. Städas av graph.destroy().
        const mo = new MutationObserver(() => { graph.applyTheme(); graph.redraw(); });
        mo.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
        const timer = setInterval(() => { if (!document.hidden && !$("view-oversikt").hidden) load(false); }, 60000);
        graph.onDestroy(() => { mo.disconnect(); clearInterval(timer); });
        load(true);
      }).catch(fail);
    } catch (e) {
      fail();
    }
  })();

  // ---------- Tio lampor ----------
  // Förklaringar i vanliga ord (under varje lampa på översikten och i Pro-fliken)
  const EXPLAIN = {
    spx: "USA:s breda aktieindex jämfört med sitt eget snitt de senaste 50 dagarna. Under snittet betyder att trenden har vänt nedåt.",
    btcTrend: "Bitcoins pris mot snittet de senaste 200 dagarna. Under snittet är bitcoin i en svagare, längre trend.",
    btcWeek: "Hur mycket bitcoin har rört sig på en vecka. Ett fall på mer än 10 % är en varning.",
    vix: "Marknadens oro-mätare. Över 20 betyder att många är nervösa.",
    us10y: "USA:s tioåriga statsränta. Stiger den snabbt blir risk dyrare för alla.",
    dxy: "Dollarns styrka mot andra valutor. En dollar över sitt snitt brukar trycka ned krypto.",
    etf: "Pengar in i och ut ur bitcoin-fonderna (ETF) de senaste fem handelsdagarna. Utflöde är en varning.",
    cpi: "Inflationen i USA mot vad marknaden väntade sig. Högre än väntat är en varning. Värdet skrivs in för hand.",
    mvrv: "Visar om bitcoin är dyrt jämfört med vad ägarna har betalat. Över 3 betyder att det börjar bli varmt, inte att toppen är nådd.",
    sopr: "Visar om bitcoin säljs med vinst eller förlust. Under 1 i snitt över en vecka betyder att folk säljer med förlust."
  };
  const STATE_WORD = { red: "RISK", green: "LUGN", wait: "VÄNTAR" };
  const confirmed = S.lamps.filter((l) => l.status !== null).length;
  const fromData = S.lampScore.source === "data";
  // Läget ändras bara via journalen – säg till om datan pekar åt ett annat läge (förslaget från trade-motorn)
  const P = S.proposal || { ready: false, plain: "Kör hämtaren så räknar Walter ett förslag." };
  const lampNote = !fromData
    ? isUser
      ? `${confirmed} av ${total} lampor har data här. Walter väntar på resten innan han gör något.`
      : `${confirmed} av ${total} lampor har data här. Poängen kommer från journalen tills datahämtningen är på plats.`
    : AUTO
      ? `Poängen räknas från hämtad data (${day(S.lampScore.asOf)}). Lamporna visar hur marknaden mår – de styr inte affärerna.`
    : !P.ready || P.mode === S.mode
      ? `Poängen räknas från hämtad data (${day(S.lampScore.asOf)}).`
      : isUser
        ? `Datan (${day(S.lampScore.asOf)}) pekar på ${modeOf(P.mode).word}. Walter byter läge själv nästa gång han räknar.`
        : `Datan (${day(S.lampScore.asOf)}) pekar på ${modeOf(P.mode).word}. Walter byter läge vid nästa körning i GitHub (högst en gång per dag).`;
  $("lamps").innerHTML = `
    <div class="panel-head"><span>TIO LAMPOR</span><span class="num">DATA ${esc(day(S.lampScore.asOf).toUpperCase())}</span></div>
    <ul class="lamp-grid">
      ${S.lamps.map((l) => { const s = lampState(l); return `
        <li><div class="lamp-row"><span class="dot ${s === "wait" ? "" : s + " lit"}"></span>
          <span class="txt"><span class="nm">${esc(l.name)}</span><span class="rl">${esc(l.rule)}</span></span>
          <span class="st">${STATE_WORD[s]}</span></div>
          ${EXPLAIN[l.id] ? `<p class="explain">${esc(EXPLAIN[l.id])}</p>` : ""}</li>`; }).join("")}
    </ul>
    <p class="lamp-note">${esc(lampNote)} <a href="#pro">Värdena bakom lamporna →</a></p>
    ${lampCountOk ? "" : isUser ? `<p class="warn small">Marknadsfilen har ${S.lamps.length} lampor. Walter räknar alltid med 10.</p>` : `<p class="warn small">state.json har ${S.lamps.length} lampor (poäng av ${S.lampScore.total}). Walter räknar alltid med 10 – rätta i state.json.</p>`}`;

  // ---------- Walter gjorde (trade-motorn, fetcher/walter_paper.py) ----------
  // Walter handlar själv: användarens i webbläsaren (boot.js), ägarens i GitHub Actionen (walter_paper.py --auto).
  const sh = pf.sharpe || {};
  const sharpeTxt = sh.value != null ? nf(2).format(sh.value) : `dag ${sh.days || 0}/${sh.need || 30}`;
  // Rutan säger vad Walter gjorde, inget att godkänna – samma för ägaren och användaren.
  const lastDone = S.journal[0];
  $("proposal").innerHTML = `
    <h3>WALTER GJORDE</h3>
    <div class="kv">
      <div><span>${AUTO ? "MARKNADEN" : "LÄGE ENLIGT LAMPORNA"}</span><strong>${P.ready && P.mode ? esc(AUTO ? ((E && E.MOODS[P.mode]) || "–").toUpperCase() : modeOf(P.mode).word) : "VÄNTAR"}</strong></div>
      ${AUTO
        ? `<div><span>NÄSTA KOLL</span><strong>${apNextText ? esc(apNextText.toUpperCase()) : "–"}</strong></div>`
        : `<div><span>RÖDA LAMPOR</span><strong>${P.ready ? `${P.red}/${total}` : "–"}</strong></div>`}
      <div><span>SHARPE</span><strong title="Avkastning per risk, räknas efter 30 dagars handel. Insättningar räknas inte.">${sharpeTxt}</strong></div>
    </div>
    <p class="explain"><b>Sharpe:</b> Avkastning per risk. Visas efter 30 dagars handel.</p>
    ${AUTO && P.ready ? `<p class="plain"><b>${esc(P.plain)}</b></p>` : P.ready ? "" : `<p class="plain"><b>${esc(P.plain)}</b></p>`}
    <p class="plain">${lastDone ? `<b>Senast (${day(lastDone.date)}):</b> ${esc(lastDone.plain)}` : "Walter har inte gjort något än. Han räknar och handlar nästa gång marknadsdatan uppdateras."}</p>
    <p class="small" style="margin-top:12px">Walter handlar själv åt dig och skriver upp varje affär i loggen. Du behöver inte godkänna något. Låtsaspengar (PAPER).</p>`;

  // ---------- Status + Uppdatera ----------
  // Webbläsaren kan bara hämta från källor som tillåter det (CORS): CoinGecko och valutakurser.
  // Riksbanken provas först; den skickar i dag inget CORS-svar, så då används ECB:s referenskurs (Frankfurter).
  // Lamporna (yfinance, BGeometrics, ETF m.fl.) kräver hämtaren.
  // Samma takt som .github/workflows/walter-auto.yml: vilar = ca var 3:e timme, annars var 15:e minut.
  const autoMsg = `Uppdateras automatiskt ${parked ? "ungefär var 3:e timme (Walter vilar)" : "var 15:e minut"} via GitHub Actions – både kurser och lampor.`;
  const latest = S.journal[0];
  const notisOld = S.notis && S.notis.at && Date.now() - new Date(S.notis.at) > 36 * 3600 * 1000;
  $("status").innerHTML = `
    <h3>STATUS</h3>
    <div class="kv">
      <div><span>SENAST HÄMTAD</span><strong id="status-time">${stamp(S.fetchedAt)}</strong></div>
      <div><span>${AUTO ? "MARKNADEN" : "WALTER"}</span><strong>${esc(AUTO ? MOOD.toUpperCase() : MODE.word)} · ${red}/${total}</strong></div>
      <div><span>MARKNADSVINST</span><strong class="${marketGain < 0 ? "down" : marketGain > 0 ? "up" : ""}">${marketGain < 0 ? "−" : "+"}${kr(Math.abs(marketGain))}</strong></div>
    </div>
    ${S.notis && S.notis.text ? `<p class="plain">${esc(S.notis.text)}${notisOld ? ` <span class="small">(från ${day(S.notis.at)})</span>` : ""}</p>` : ""}
    ${latest && !isUser ? `<p class="plain"><b>Senast (${day(latest.date)}):</b> ${esc(latest.plain)}</p>` : ""}
    <div class="status-actions"><button type="button" class="btn btn-primary" id="btn-refresh">UPPDATERA</button>
      <span class="small">Insättningar ${kr(deposits)}${topUp ? ` (${kr(start)} + ${kr(topUp)})` : ""}</span></div>
    <p class="status-msg" id="status-msg" aria-live="polite">Knappen hämtar färska kurser för BTC, USDSEK och EURSEK. ${autoMsg}</p>`;

  const getJson = async (url) => {
    const r = await fetch(url, { cache: "no-store" });
    if (!r.ok) throw new Error(r.status);
    return r.json();
  };
  const freshFx = async () => {
    try {
      const [u, e] = await Promise.all(["SEKUSDPMI", "SEKEURPMI"].map((id) => getJson(`https://api.riksbank.se/swea/v1/Observations/Latest/${id}`)));
      return { usdsek: { value: u.value, asOf: u.date, source: "Riksbanken" }, eursek: { value: e.value, asOf: e.date, source: "Riksbanken" } };
    } catch {
      const x = await getJson("https://api.frankfurter.dev/v1/latest?base=EUR&symbols=SEK,USD");
      return {
        usdsek: { value: +(x.rates.SEK / x.rates.USD).toFixed(4), asOf: x.date, source: "ECB via Frankfurter" },
        eursek: { value: x.rates.SEK, asOf: x.date, source: "ECB via Frankfurter" }
      };
    }
  };
  $("btn-refresh").addEventListener("click", async (ev) => {
    const btn = ev.currentTarget;
    btn.disabled = true;
    btn.textContent = "HÄMTAR …";
    const got = [], failedSrc = [];
    const [btcRes, fxRes] = await Promise.allSettled([
      getJson("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"),
      freshFx()
    ]);
    const now = new Date();
    if (btcRes.status === "fulfilled" && btcRes.value.bitcoin) {
      m.btc = { ...m.btc, value: Math.round(btcRes.value.bitcoin.usd), asOf: now.toISOString().slice(0, 10) };
      got.push(`BTC ${usd(m.btc.value)}`);
    } else failedSrc.push("CoinGecko");
    if (fxRes.status === "fulfilled") {
      Object.assign(m, fxRes.value);
      got.push(`USDSEK ${nf(4).format(m.usdsek.value)} och EURSEK ${nf(4).format(m.eursek.value)} (${m.usdsek.source}, ${day(m.usdsek.asOf)})`);
    } else failedSrc.push("valutakurser");
    renderPrices();
    renderGoal();
    if (got.length) $("status-time").textContent = stamp(now.toISOString()) + " (kurser)";
    $("status-msg").innerHTML =
      (got.length ? `Färskt ${stamp(now.toISOString())}: ${esc(got.join(" · "))}. ` : "") +
      (failedSrc.length ? `<span class="warn">Kunde inte hämta: ${esc(failedSrc.join(", "))}. Senast sparade värden visas.</span> ` : "") +
      autoMsg;
    btn.disabled = false;
    btn.textContent = "UPPDATERA";
  });

  // ---------- Fördelning ----------
  const share = (k) => (pf.value > 0 ? pf.holdings[k] / pf.value : 0);
  const rows = [
    { k: "BTC", name: "Bitcoin", note: AUTO ? apNote("BTC", "mål") : "Level 1", cap: AUTO ? apWeights.BTC : S.rules.caps.BTC },
    { k: "ETH", name: "Ethereum", note: AUTO ? apNote("ETH", "mål") : "Level 2", cap: AUTO ? apWeights.ETH : S.rules.caps.ETH },
    { k: "GOLD", name: "Guld", note: AUTO ? apNote("GOLD", "PAXG · mål") : "PAXG / XAUT · L3", cap: AUTO ? apWeights.GOLD : S.rules.caps.GOLD },
    { k: "CASH", name: "Kontant", note: AUTO ? "mål · minst 25 %" : "minst 25 %", cap: null }
  ];
  $("allocation").innerHTML = `
    <h3>FÖRDELNING</h3>
    <div class="alloc">
      ${rows.map((r) => {
        const locked = r.cap !== null && !unlocked[r.k];
        const s = share(r.k);
        const capPos = r.cap !== null ? r.cap * 100 : (AUTO ? apCash : S.rules.minCash) * 100;
        return `<div class="alloc-row">
          <div class="lbl"><b>${r.name}</b><span>${esc(r.note)}</span></div>
          <div class="bar${locked ? " locked" : ""}">
            <span class="fill" style="width:${s * 100}%"></span>
            <span class="cap" style="left:${capPos}%" title="${r.cap !== null ? "Tak" : "Golv"} ${capPos} %"></span>
          </div>
          <div class="pct">${locked ? "låst" : nf(0).format(s * 100) + " %"}${r.cap !== null ? " / " + nf(0).format(r.cap * 100) + " %" : AUTO ? " / " + nf(0).format(apCash * 100) + " %" : ""}</div>
        </div>`;
      }).join("")}
    </div>
    <p class="small" style="margin-top:16px">${AUTO
      ? `Investerat ${nf(0).format(invested * 100)} %. Strecket visar autopilotens mål. Inom ${apBand} procentenheter från målet rör jag ingenting.`
      : `Investerat ${nf(0).format(invested * 100)} %. På Level ${S.level} är taket ${nf(0).format(levelCap * 100)} %, eftersom bara upplåsta tillgångar räknas. Max ${S.rules.maxInvested * 100} % nås först på Level 3. Strecket visar tak (eller golv för kontanter).`}</p>`;

  // ---------- Nivåer ----------
  // Upplåsning räknas ALLTID på marknadsvinst över insättningarna – insättningar låser aldrig upp.
  // Level 2: en av vägarna i rules.unlock räcker. Level 3: +levels.3.gainPct % och drawdown under levels.3.maxDd.
  // Beloppen räknas här (inte fasta i state.json), så en ny insättning flyttar kraven med sig.
  const LV = S.levels || {};
  const u = S.rules.unlock;
  const krFor = (p) => kr(deposits * p / 100);
  const gainCond = (p) => [`Marknadsvinst ${nf(0).format(Math.max(0, marketPct))} % / ${p} % (krävs +${krFor(p)} över insättningarna ${kr(deposits)})`, marketPct >= p];
  const paths = [
    { name: "Tidig väg", conds: [
      [`Minst ${u.early.days} dagar (dag ${days})`, days >= u.early.days],
      gainCond(u.early.gainPct),
      [`Drawdown under ${u.early.maxDd} % (nu ${nf(1).format(dd)} %)`, dd < u.early.maxDd],
      [`Minst ${u.early.minGreen}/${total} gröna lampor (nu ${green})`, green >= u.early.minGreen]
    ] },
    { name: "Normal väg", conds: [
      [`Minst ${u.normal.days} dagar (dag ${days})`, days >= u.normal.days],
      gainCond(u.normal.gainPct),
      [`Drawdown under ${u.normal.maxDd} % (nu ${nf(1).format(dd)} %)`, dd < u.normal.maxDd]
    ] }
  ];
  const lv3 = LV[3] || null;
  const lvUnlocked = (n) => n === 1
    || (n === 2 && marketGain > 0 && paths.some((p) => p.conds.every(([, ok]) => ok === true)))
    || (n === 3 && lv3 != null && marketGain > 0 && marketPct >= lv3.gainPct && dd < lv3.maxDd);
  // Närmaste vägens vinstkrav till Level 2 (används i nivåerna och i planen)
  const lv2Gain = Math.min(u.early.gainPct, u.normal.gainPct);

  // Guld är skyddet: önskas när oron är hög (VIX över gränsen eller S&P under sitt snitt). null = väntar på data.
  const g = S.rules.gold;
  const vixHigh = m.vix.value == null ? null : m.vix.value > g.vixAbove;
  const spxLow = m.spx.belowMa == null ? null : m.spx.belowMa;
  const goldWanted = vixHigh === true || spxLow === true ? true : vixHigh === null || spxLow === null ? null : false;

  // Låst level: villkoren visas släckta ("tänds" först när leveln är upplåst)
  const lockedDot = '<span class="dot" title="Låst tills leveln är upplåst"></span>';
  const lv2Profit = deposits * lv2Gain / 100;
  const lv2pct = lv2Profit > 0 ? Math.min(100, Math.max(0, marketGain) / lv2Profit * 100) : 0;
  const levels = [
    { n: 1, name: "Level 1 · Bitcoin", tag: "BTC max 35 % · kontant minst 25 %", conds: [
      ["Aktiv från start", true],
      [`Walter vilar inte (färre än ${S.rules.parkeraAtRed}/${total} röda lampor${isUser ? "" : " i journalen"})`, !parked]
    ] },
    { n: 2, name: "Level 2 · Ethereum", tag: "ETH 20 %", bar: lvUnlocked(2) ? null : lv2pct, conds: [
      [`Upplåst: tidig eller normal väg klar (marknadsvinst nu ${kr(Math.max(0, marketGain))} av ${kr(lv2Profit)})`, lvUnlocked(2), true],
      ["BTC är LONG", m.btcLong],
      ["ETH/BTC över 30-dagars snitt", m.ethBtcAbove30dMa],
      [`Högst ${S.rules.ethMaxRed} röda lampor (nu ${red})`, red <= S.rules.ethMaxRed]
    ] },
    { n: 3, name: "Level 3 · Guld", tag: "PAXG / XAUT 20 % · även när Walter vilar", conds: [
      [`Upplåst: +${lv3 ? lv3.gainPct : "?"} % marknadsvinst (${kr(Math.max(0, marketGain))} / ${lv3 ? krFor(lv3.gainPct) : "?"})`, lvUnlocked(3), true],
      [`Oro: VIX över ${g.vixAbove} (nu ${m.vix.value != null ? nf(1).format(m.vix.value) : "?"}) eller S&P 500 under 50-dagarssnitt`, goldWanted]
    ] }
  ];
  $("unlock").hidden = AUTO;
  if (AUTO) {
    $("levels").innerHTML = `
    <h3>NIVÅER</h3>
    <p class="plain">Inte aktivt i autopiloten. Bitcoin, ethereum och guld köps från första dagen, i fasta andelar.</p>`;
  } else $("levels").innerHTML = `
    <h3>NIVÅER</h3>
    <p class="explain">Walter får handla med fler tillgångar först när han har tjänat pengar på marknaden. Insättningar låser aldrig upp något.</p>
    ${levels.map((l) => `
      <div class="level${l.n === S.level ? " current" : ""}">
        <div class="level-head"><b>${l.name}${l.n === S.level ? " · nu" : ""}</b><span>${esc(l.tag)}</span></div>
        ${l.bar != null ? `<div class="lv-bar" role="progressbar" aria-label="Marknadsvinst mot Level 2" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(l.bar)}"><span style="width:${l.bar}%"></span></div>` : ""}
        <ul class="conds">${l.conds.map(([t, ok, gate]) => `<li>${gate || lvUnlocked(l.n) ? check(ok) : lockedDot}<span>${esc(t)}</span></li>`).join("")}</ul>
      </div>`).join("")}`;

  // ---------- Vägen till Level 2 ----------
  if (!AUTO) $("unlock").innerHTML = `
    <h3>VÄGEN TILL LEVEL 2</h3>
    <p class="small">En av vägarna räcker.</p>
    <p class="explain"><b>Drawdown:</b> Hur långt värdet har fallit från sin högsta punkt.</p>
    ${paths.map((p) => {
      const done = p.conds.filter(([, ok]) => ok === true).length;
      return `<div class="unlock-path" style="margin-top:14px">
        <h4>${p.name} <span class="small">· ${done}/${p.conds.length}</span></h4>
        <ul class="conds">${p.conds.map(([t, ok]) => `<li>${check(ok)}<span>${esc(t)}</span></li>`).join("")}</ul>
      </div>`;
    }).join("")}`;

  // ---------- Resan: fas 1 och fas 2 som två grafer med ett brott emellan ----------
  // Faser: capitalChange i state.json delar historiken. Före = fas 1 (paper-test), från och med = fas 2.
  // Insättningen är ingen vinst, så faserna ritas aldrig som en sammanhängande linje.
  const cc = pf.capitalChange || null;
  const allHist = (pf.history || []).slice();
  if (allHist.length && allHist[allHist.length - 1].date < S.updatedAt) allHist.push({ date: S.updatedAt, value: pf.value, cash: pf.holdings.CASH });
  const phase1 = cc ? allHist.filter((h) => h.date < cc.date) : [];
  const phase2 = cc ? [{ date: cc.date, value: cc.value, note: "insättning" }, ...allHist.filter((h) => h.date >= cc.date)] : allHist;
  const phaseChart = (pts, label) => {
    const W = 300, H = 130, P = 14, TOP = 24, BOT = 22;
    const vals = pts.map((h) => h.value);
    let lo = Math.min(...vals), hi = Math.max(...vals);
    const pd = (hi - lo) * 0.15 || Math.max(1, hi * 0.02);
    lo -= pd; hi += pd;
    const x = (i) => P + 18 + (i * (W - 2 * P - 36)) / Math.max(1, pts.length - 1);
    const y = (v) => H - BOT - ((v - lo) * (H - TOP - BOT)) / (hi - lo);
    const line = pts.map((h, i) => `${x(i).toFixed(1)},${y(h.value).toFixed(1)}`).join(" ");
    return `<svg class="pf-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(label)}: ${pts.map((h) => `${day(h.date)} ${nf(0).format(h.value)} kr`).join(", ")}">
      <polyline points="${x(0).toFixed(1)},${H - BOT} ${line} ${x(pts.length - 1).toFixed(1)},${H - BOT}" class="pf-area"/>
      <polyline points="${line}" class="pf-line"/>
      ${pts.map((h, i) => `<circle cx="${x(i)}" cy="${y(h.value)}" r="${i === pts.length - 1 ? 4 : 2.5}" class="pf-dot"/>
        <text x="${x(i)}" y="${y(h.value) - 9}" text-anchor="middle" class="journey-val">${amount(h.value)}</text>
        <text x="${i === 0 ? P : i === pts.length - 1 ? W - P : x(i)}" y="${H - 6}" text-anchor="${i === 0 ? "start" : i === pts.length - 1 ? "end" : "middle"}" class="journey-date">${[i && pts[i - 1].date === h.date ? "" : day(h.date), i === pts.length - 1 && !h.note ? "nu" : h.note || ""].filter(Boolean).map(esc).join(" · ")}</text>`).join("")}
    </svg>`;
  };
  // Fas 1 innehåller en DCA-insättning, så skillnaden där är ingen vinst – visa bara från/till.
  // Fas 2: bara det som blir kvar efter insättningarna kallas marknad.
  const phaseSpan = (pts, split) => {
    const from = `${amount(pts[0].value)} kr`, to = `${amount(pts[pts.length - 1].value)} kr`;
    if (!split) return `${from} → ${to}`;
    const sign = (v) => (v < 0 ? "−" : "+") + kr(Math.abs(v));
    const manual = cc.manualTopUp || 0;
    const market = pts[pts.length - 1].value - pts[0].value - manual;
    const parts = [manual ? `${sign(manual)} insättning` : "", Math.abs(market) >= 1 ? `${sign(market)} marknad` : ""].filter(Boolean);
    return `${from} → ${to}${parts.length ? ` (${parts.join(", ")})` : ""}`;
  };
  if (cc && phase1.length && phase2.length > 1) {
    // Hur stor "vinsten" hade sett ut om linjen dragits rakt igenom, avrundat nedåt (40 650 % -> 40 000 %)
    const raw = (phase2[phase2.length - 1].value / phase1[phase1.length - 1].value - 1) * 100;
    const mag = 10 ** Math.floor(Math.log10(Math.max(1, raw)));
    const jump = Math.floor(raw / mag) * mag;
    $("journey").hidden = false;
    $("journey").innerHTML = `
      <h3>RESAN</h3>
      <div class="journey-grid">
        <div><div class="journey-head"><b>Fas 1 · paper-test</b><span class="num">${esc(phaseSpan(phase1, false))}</span></div>${phaseChart(phase1, "Fas 1, paper-test")}</div>
        <div class="journey-break" role="separator"><span>${day(cc.date)}</span>${esc(cc.text)}</div>
        <div><div class="journey-head"><b>Fas 2 · nu</b><span class="num">${esc(phaseSpan(phase2, true))}</span></div>${phaseChart(phase2, "Fas 2, nytt startkapital")}</div>
      </div>
      <p class="small" style="margin-top:12px">Fas 1 = paper-test ${kr(phase1[0].value)}. Fas 2 = nytt kapital ${kr(cc.value)}. Ingen ${nf(0).format(jump)} % vinst – hoppet är en insättning.${cc.manualTopUp ? ` Även ${kr(cc.value)} → ${kr(phase2[phase2.length - 1].value)} är manuella insättningar, inte marknadsvinst, tills Walter går LIVE.` : ""}</p>`;
  }

  // ================================================================
  // PRO – varje lampas värde, gräns, källa och tid
  // ================================================================
  const SOURCES = {
    spx: "yfinance ^GSPC", btcTrend: "CoinGecko", btcWeek: "CoinGecko", vix: "yfinance ^VIX",
    us10y: (m.us10y && m.us10y.source) || "FRED DGS10", dxy: "yfinance DX-Y.NYB", etf: "bykaranteli (ETF-flöden)",
    cpi: isUser ? "handskrivet värde i Walters marknadsfil" : "state.json, handskriven", mvrv: (m.mvrvZ && m.mvrvZ.source) || "Coin Metrics", sopr: "BGeometrics"
  };
  const maxAge = S.rules.lampMaxAgeDays || {};
  let proSel = Math.max(0, S.lamps.findIndex((l) => l.status === "red"));
  const pv = (v, f) => (v == null ? "väntar på data" : f(v));
  const renderPrices = () => {
    const el = $("prices");
    if (!el) return;
    const { usdsek } = fx();
    const list = [
      ["Bitcoin", pv(m.btc && m.btc.value, usd)],
      [`ETH/BTC${m.ethBtc && m.ethBtc.ma30 ? ` (30d-snitt ${nf(5).format(m.ethBtc.ma30)})` : ""}`, pv(m.ethBtc && m.ethBtc.value, (v) => nf(5).format(v))],
      ["USD/SEK", pv(usdsek && usdsek.value, (v) => nf(4).format(v))],
      ["EUR/SEK", pv(m.eursek && m.eursek.value, (v) => nf(4).format(v))],
      ["S&P 500", pv(m.spx && m.spx.value, (v) => nf(0).format(v))],
      ["VIX", pv(m.vix && m.vix.value, (v) => nf(2).format(v))],
      ["Dollarindex", pv(m.dxy && m.dxy.value, (v) => nf(2).format(v))],
      ["10-årig ränta", pv(m.us10y && m.us10y.value, (v) => nf(2).format(v) + " %")]
    ];
    el.innerHTML = list.map(([n, v]) => `<li><span>${esc(n)}</span><span class="num">${esc(v)}</span></li>`).join("");
  };
  const renderPro = () => {
    const l = S.lamps[proSel], s = lampState(l);
    const word = { red: "RISK", green: "LUGN", wait: "VÄNTAR" };
    $("view-pro").innerHTML = `
      <p class="kicker">PRO · DATAN BAKOM LAMPORNA · SENAST HÄMTAD ${S.fetchedAt ? dotStamp(S.fetchedAt) : "OKÄNT"}</p>
      <div class="title-row">
        <h1>PRO</h1>
        <div class="legend row">
          <span><i class="r"></i>${nRed} röda</span><span><i class="g"></i>${nGreen} gröna</span><span><i class="w"></i>${nWait} väntar</span>
          <span class="note" style="margin:0">VILA VID ${S.rules.parkeraAtRed}/${total}${left > 0 ? ` · ${left} KVAR` : ""}</span>
        </div>
      </div>
      <div class="two">
        <div class="panel">
          <div class="table-wrap"><table class="pro-table">
            <thead><tr><th>LAMPA</th><th class="r">VÄRDE</th><th>GRÄNS</th><th>STATUS</th><th>KÄLLA</th><th class="r">DATA FRÅN</th></tr></thead>
            <tbody>${S.lamps.map((x, i) => { const st = lampState(x); return `
              <tr class="pro-row" data-i="${i}" aria-selected="${i === proSel}">
                <td><span class="nm"><button type="button" data-i="${i}" aria-pressed="${i === proSel}"><span class="dot ${st === "wait" ? "" : st}"></span>${esc(x.name)}</button></span></td>
                <td class="r"><span class="mono">${x.value ? esc(x.value) : "väntar på data"}</span></td>
                <td><span class="mono">${esc(x.rule)}</span></td>
                <td><span class="mono">${word[st]}</span></td>
                <td><span class="src">${esc(SOURCES[x.id] || "–")}</span></td>
                <td class="r"><span class="mono">${x.asOf ? day(x.asOf) : "–"}</span></td>
              </tr>`; }).join("")}</tbody>
          </table></div>
          <p class="small" style="margin-top:12px">Tryck på en rad för detaljer. En lampa vars data är äldre än ${maxAge.default || "?"} dagar (ETF ${maxAge.etf || "?"}, MVRV-Z och SOPR ${maxAge.mvrv || "?"}, KPI ${maxAge.cpi || "?"}) blir "väntar", så gammal data aldrig räknas som färsk.</p>
        </div>
        <div class="side">
          <div class="panel sel" aria-live="polite">
            <span class="label">VALD LAMPA</span>
            <div class="sel-name"><span class="dot ${s === "wait" ? "" : s}"></span>${esc(l.name)}</div>
            <p class="sel-text">${esc(EXPLAIN[l.id] || l.rule)} Nu: ${esc(l.value || "väntar på data")}.</p>
            <div class="sel-foot"><span>${esc(SOURCES[l.id] || "–")}</span><span>${l.asOf ? day(l.asOf) : "–"}</span></div>
          </div>
          <div class="panel">
            <div class="panel-head"><span>DAGENS PRISER</span><span class="num">${esc(day(m.asOf || S.updatedAt).toUpperCase())}</span></div>
            <ul class="rows" id="prices"></ul>
          </div>
        </div>
      </div>`;
    renderPrices();
    $("view-pro").querySelectorAll(".pro-row").forEach((tr) => tr.addEventListener("click", () => {
      proSel = +tr.dataset.i;
      renderPro();
      const b = $("view-pro").querySelector(`button[data-i="${proSel}"]`);
      if (b) b.focus();
    }));
  };
  renderPro();

  // ================================================================
  // LOGG – tradelogg och rapporter
  // ================================================================
  // Avgifter: trading_fee (taker + slippage vid försäljningen) + withdrawal_fee. Samma som fetcher/walter_k4.py.
  const k4 = (S.k4 || []).map((r) => {
    const fee = (r.trading_fee_sek || 0) + (r.withdrawal_fee_sek || 0);
    return { ...r, fee, vinst: r.forsaljningspris_sek - r.omkostnad_sek - fee };
  });
  // Trades: försäljningar från K4 + köp/DCA ur historiken. Insättningar (flow) är inga trades.
  // Tillgången står bara där den är känd (K4-raden med samma köpdatum), annars "–".
  const trades = [
    ...k4.map((r) => ({ date: r.saljdatum, type: "SÄLJ", dot: "red", asset: r.beteckning, note: `${r.typ || "försäljning"}, ${nf(8).format(r.antal)} st`, amt: kr2(r.forsaljningspris_sek), fee: kr2(r.fee) })),
    ...allHist.filter((h) => h.note && !h.flow && /^(köp|dca)$/i.test(h.note)).map((h) => {
      const k = k4.find((r) => r.kopdatum === h.date);
      return { date: h.date, type: h.note.toUpperCase(), dot: "green", asset: k ? k.beteckning : "–",
        note: `Portföljen värd ${amount(h.value)} kr${h.test ? " · paper-test" : ""}`, amt: "–", fee: "–" };
    })
  ].sort((a, b) => b.date.localeCompare(a.date));
  const sold = k4.reduce((a, r) => a + r.vinst, 0);
  const feeSum = k4.reduce((a, r) => a + r.fee, 0);
  const flows = allHist.filter((h) => h.flow);
  let logTab = 0, logSel = 0;
  const renderLog = () => {
    const e = S.journal[logSel];
    $("view-logg").innerHTML = `
      <p class="kicker">LOGG · TRADELOGG OCH RAPPORTER</p>
      <div class="title-row">
        <h1>${logTab ? "RAPPORTER" : "TRADELOGG"}</h1>
        <div class="seg" role="group" aria-label="Välj logg">
          <button type="button" data-tab="0" aria-pressed="${!logTab}">TRADELOGG</button>
          <button type="button" data-tab="1" aria-pressed="${!!logTab}">RAPPORTER</button>
        </div>
      </div>
      <p class="intro">${logTab ? "Walters rapporter med ett svar du kan läsa på tio sekunder. Siffrorna ligger bakom." : "Varje köp och sälj Walter har gjort, i tidsordning. Allt är paper, inga riktiga pengar."}</p>
      <div class="two">
        <div class="panel">
          <div class="panel-head"><span>${logTab ? "RAPPORTHISTORIK" : "ALLA TRADES"}</span><span class="num">${logTab ? S.journal.length + " RAPPORTER" : trades.length + " POSTER"}</span></div>
          ${logTab ? `
            <ul class="reports" style="margin-top:8px">${S.journal.map((j, i) => `
              <li><button type="button" data-sel="${i}" aria-pressed="${i === logSel}">
                <span class="when">${day(j.date)}</span>
                <span class="md"><span class="dot ${modeOf(j.mode).acc}"></span>${esc(modeOf(j.mode).word)}</span>
                <span class="tx">${esc(j.plain)}</span>
                <span class="rd">${j.red == null ? "–" : esc(j.red)}/${total}</span>
              </button></li>`).join("")}</ul>
            <p class="small" style="margin-top:12px">Tryck på en rapport för siffrorna bakom.${isUser ? "" : " Journalen är facit."}</p>` : `
            <div class="table-wrap"><table class="log-table">
              <thead><tr><th>DATUM</th><th>TYP</th><th>TILLGÅNG</th><th class="r">BELOPP</th><th class="r">AVGIFT</th></tr></thead>
              <tbody>${trades.map((t) => `<tr>
                <td class="num">${day(t.date)}</td>
                <td><span class="type"><span class="dot ${t.dot}"></span>${esc(t.type)}</span></td>
                <td><span class="asset">${esc(t.asset)}<span>${esc(t.note)}</span></span></td>
                <td class="r num">${esc(t.amt)}</td><td class="r num">${esc(t.fee)}</td></tr>`).join("") || '<tr><td colspan="5" class="small">Inga trades ännu.</td></tr>'}</tbody>
            </table></div>
            <p class="small" style="margin-top:12px">Okända belopp visas som "–".${flows.length ? ` Insättningar (${flows.map((h) => day(h.date)).join(", ")}) är inga trades och syns inte här.` : ""}</p>`}
        </div>
        <div class="side">
          ${logTab && e ? `
          <div class="panel">
            <span class="label">SIFFRORNA · ${esc(day(e.date).toUpperCase())}</span>
            <div class="sel-name" style="font-size:18px"><span class="dot ${modeOf(e.mode).acc}"></span>${esc(modeOf(e.mode).word)} · ${e.red == null ? "–" : esc(e.red)}/${total}</div>
            <ul class="facts">${(e.facts || []).map((f) => `<li>${esc(f)}</li>`).join("")}</ul>
          </div>` : `
          <div class="panel">
            <span class="label">SAMMANFATTNING</span>
            <ul class="rows">
              <li><span>Antal trades</span><span class="num">${trades.length}</span></li>
              <li><span>Sålda affärer</span><span class="num">${k4.length}</span></li>
              <li><span>Resultat sålda</span><span class="num ${sold < 0 ? "down" : sold > 0 ? "up" : ""}">${sold < 0 ? "−" : "+"}${kr2(Math.abs(sold))}</span></li>
              <li><span>Avgifter totalt</span><span class="num">${kr2(feeSum)}</span></li>
            </ul>
            <p class="plain">${invested === 0 ? "Walter står helt i kontanter just nu." : `${nf(0).format(invested * 100)} % av pengarna är investerade.`}</p>
          </div>`}
        </div>
      </div>`;
    $("view-logg").querySelectorAll("[data-tab]").forEach((b) => b.addEventListener("click", () => { logTab = +b.dataset.tab; renderLog(); }));
    $("view-logg").querySelectorAll("[data-sel]").forEach((b) => b.addEventListener("click", () => {
      logSel = +b.dataset.sel; renderLog();
      const nb = $("view-logg").querySelector(`[data-sel="${logSel}"]`);
      if (nb) nb.focus();
    }));
  };
  renderLog();

  // ================================================================
  // K4 – underlag (PAPER). Hela kronor som fetcher/walter_k4.py: försäljning efter avgift, omkostnad.
  // ================================================================
  const sales = k4.map((r) => r.saljdatum).filter(Boolean).sort();
  const reportYear = sales.length ? sales[sales.length - 1].slice(0, 4) : String(new Date().getFullYear());
  const yearRows = k4.filter((r) => (r.saljdatum || "").startsWith(reportYear));
  const gains = yearRows.filter((r) => r.vinst >= 0).reduce((a, r) => a + r.vinst, 0);
  const losses = Math.abs(yearRows.filter((r) => r.vinst < 0).reduce((a, r) => a + r.vinst, 0));
  const k4Sale = (r) => Math.round(r.forsaljningspris_sek - r.fee);
  const k4Cost = (r) => Math.round(r.omkostnad_sek);
  const FILES = [
    [`K4_${reportYear}_WALTER_PAPER.pdf`, "Läsbar version", "PDF"],
    [`K4-WALTER-${reportYear}-PAPER.xlsx`, "Kalkylark", "XLSX"],
    [`K4_${reportYear}_WALTER_PAPER.csv`, "Rådata", "CSV"],
    [`Avgiftsrapport_${reportYear}_WALTER_PAPER.pdf`, "Alla avgifter", "PDF"]
  ];
  let k4Open = -1;
  const renderK4 = () => {
    $("view-k4").innerHTML = `
      <p class="kicker">K4 · UNDERLAG ${reportYear}</p>
      <div class="title-row"><h1>K4-UNDERLAG</h1><span class="label" style="color:var(--teal)">PAPER · SIMULERING</span></div>
      <p class="intro">Så skulle försäljningarna se ut i en K4-blankett. Inte för Skatteverket eller banken.</p>
      <div class="two">
        <div class="panel">
          <div class="panel-head"><span>SEKTION D · ÖVRIGA TILLGÅNGAR (KRYPTO)</span><span class="num">${yearRows.length} RAD${yearRows.length === 1 ? "" : "ER"}</span></div>
          ${yearRows.length ? `
          <div class="table-wrap"><table class="pro-table" style="min-width:640px">
            <thead><tr><th>BETECKNING</th><th class="r">ANTAL</th><th class="r">FÖRSÄLJNING</th><th class="r">OMKOSTNAD</th><th class="r">VINST</th></tr></thead>
            <tbody>${yearRows.map((r, i) => `
              <tr class="pro-row" data-k="${i}" aria-selected="${i === k4Open}">
                <td><span class="nm"><button type="button" data-k="${i}" aria-expanded="${i === k4Open}"><span style="display:flex;flex-direction:column;gap:2px;line-height:1.3">${esc(r.beteckning)}<span class="small" style="color:inherit;opacity:.75">köpt ${day(r.kopdatum)} · såld ${day(r.saljdatum)}</span></span></button></span></td>
                <td class="r"><span class="mono">${nf(8).format(r.antal)}</span></td>
                <td class="r"><span class="mono">${nf(2).format(r.forsaljningspris_sek)}</span></td>
                <td class="r"><span class="mono">${nf(2).format(r.omkostnad_sek)}</span></td>
                <td class="r"><span class="mono">${r.vinst < 0 ? "−" : "+"}${nf(2).format(Math.abs(r.vinst))}</span></td>
              </tr>`).join("")}</tbody>
          </table></div>
          <div class="k4-sums">
            <div><span class="label">I KRONOR OCH ÖREN</span>${yearRows.map((r) => `<span class="num">Försäljning ${nf(2).format(r.forsaljningspris_sek)} · Omkostnad ${nf(2).format(r.omkostnad_sek)} · Avgift ${nf(2).format(r.fee)} · ${r.vinst < 0 ? "Förlust" : "Vinst"} ${nf(2).format(Math.abs(r.vinst))}</span>`).join("")}</div>
            <div><span class="label">AVRUNDAT TILL HELA KRONOR (K4)</span>${yearRows.map((r) => `<span class="num">Försäljning ${k4Sale(r)} · Omkostnad ${k4Cost(r)} · ${k4Sale(r) - k4Cost(r) < 0 ? "Förlust" : "Vinst"} ${Math.abs(k4Sale(r) - k4Cost(r))}</span>`).join("")}</div>
          </div>
          <p class="plain" style="min-height:52px">${k4Open >= 0 ? esc(`Typ: ${yearRows[k4Open].typ || "–"}. ${yearRows[k4Open].not || ""}`) : "Tryck på raden för detaljer. Försäljningspriset på blanketten är efter avgiften, avrundat till hela kronor."}</p>`
          : `<p class="plain">Inga försäljningar ${reportYear} ännu, så det finns inget att deklarera.</p>`}
          <p class="small">Omkostnad räknas med genomsnittsmetoden (Skatteverkets regel för krypto) inklusive köpavgift. Vinster och förluster står på separata rader.</p>
        </div>
        <div class="side">
          <div class="panel">
            <span class="label">SUMMA ${reportYear}</span>
            <ul class="rows">
              <li><span>Vinster</span><span class="num">${kr2(gains)}</span></li>
              <li><span>Förluster</span><span class="num">${kr2(losses)}</span></li>
              <li class="total"><span>Skatt, ungefär</span><span class="num">${kr2(Math.max(0, (gains - losses * 0.7) * 0.3))}</span></li>
            </ul>
            <p class="small" style="margin-top:12px">30 % skatt på vinsten, 70 % av förlusten får dras av.${topUp ? ` Insättningen på ${kr(topUp)} är ingen försäljning och syns inte här.` : ""}</p>
          </div>
          <div class="panel">
            <span class="label">FILER</span>
            <ul class="files">${FILES.map(([f, hint, kind]) => `<li><a href="reports/${f}" download><span class="fn">${f}<span>${hint}</span></span><span class="kind">${kind}</span></a></li>`).join("")}</ul>
            <p class="small" style="margin-top:12px">Filerna byggs av hämtaren (walter_k4.py) och finns på den publicerade sidan.</p>
          </div>
        </div>
      </div>`;
    $("view-k4").querySelectorAll(".pro-row").forEach((tr) => tr.addEventListener("click", () => {
      const i = +tr.dataset.k; k4Open = k4Open === i ? -1 : i; renderK4();
      const b = $("view-k4").querySelector(`button[data-k="${i}"]`);
      if (b) b.focus();
    }));
  };
  // K4 och rapportfilerna är ägarens. Användaren får varken flik eller länkar.
  if (!isUser) renderK4();
  else { const a = document.querySelector('.nav [data-view="k4"]'); if (a) a.remove(); $("view-k4").remove(); }

  // ================================================================
  // INSTÄLLNINGAR – din plan, uttag, avgifter, PAPER/LIVE. Allt sparas bara i den här webbläsaren.
  // ================================================================
  // Målet med datum och månadssparandet ersätter den gamla planen (walter.plan: startsumma, +% och tidslinje).
  // En gammal plan fyller bara i målformuläret – målet slås på först när man sparar (det ändrar Walters affärer).
  const GOALS = [10, 20, 50, 100], TIMES = [6, 12, 36, 60];
  const oldPlan = S.goal ? null : store.get(own("plan"), null);
  const addMonths = addMonthsIso;
  const goalDraft = S.goal ? Object.assign({}, S.goal)
    : oldPlan && oldPlan.start > 0 && GOALS[oldPlan.goal] && TIMES[oldPlan.time]
      ? { name: "Mitt mål", amountSek: Math.round(oldPlan.start * (1 + GOALS[oldPlan.goal] / 100)), date: addMonths(isoToday, TIMES[oldPlan.time]), fromPlan: true }
      : { name: "", amountSek: "", date: "" };
  const savingsNow = S.savings && S.savings.monthlySek > 0 ? S.savings : null;

  const PURPOSES = { bil: ["Bil", "en bil"], husinsats: ["Husinsats", "en husinsats"], resa: ["Resa", "en resa"], rakningar: ["Räkningar", "räkningar"], buffert: ["Buffert", "en buffert"], annat: ["Annat", "ditt mål"] };
  const HORIZONS = { "1v": [7, "1 vecka"], "1m": [30, "1 månad"], "3m": [91, "3 månader"], "6m": [182, "6 månader"] };
  const goal = Object.assign({ amount: 50000, purpose: "buffert", horizon: "1m" }, store.get(own("goal"), {}));
  if (!HORIZONS[goal.horizon]) goal.horizon = "1m";
  if (!PURPOSES[goal.purpose]) goal.purpose = "buffert";
  if (!(goal.amount > 0)) goal.amount = 50000;
  const feesKnown = FEE_KEYS.every((k) => fees[k] != null);
  // Användaren: säg ärligt vilken börs avgifterna kommer från, källan och när den kontrollerades
  const feeSourceText = ex
    ? `Taker-avgiften kommer från ${ex.source ? `<a href="${esc(ex.source)}" target="_blank" rel="noopener">${esc(ex.name)}s prislista</a>` : `${esc(ex.name)}s prislista`}, ${/^\d{4}-\d{2}-\d{2}$/.test(ex.checked || "") ? `kontrollerad ${esc(day(ex.checked))} ${esc(ex.checked.slice(0, 4))}` : "kontrollerat datum saknas"}. Slippage, valutaväxling och SEPA-uttag är Walters antaganden, inte börsens. Tomt fält = det värdet.`
    : "Jag hittar inte din börs i listan, så avgifterna är Walters standard. Tomt fält = standard.";

  $("view-installningar").innerHTML = `
    <p class="kicker">INSTÄLLNINGAR · DITT MÅL</p>
    <div class="title-row"><h1>DITT MÅL</h1></div>
    <p class="intro">Ett mål med ett datum, och ett sparande varje månad. Båda är valfria. Allt är låtsaspengar (PAPER).</p>
    ${AUTO ? "" : '<p class="warn">Målet och månadssparandet fungerar bara med autopiloten. Walter kör nu lamp-strategin (rules.strategy = "lamps"), så de ändrar inget.</p>'}
    <div class="plan sv-plan"${AUTO ? "" : " hidden"}>
      <section class="panel" aria-label="Mål">
        <h3>MÅL MED DATUM</h3>
        <form id="goal-form" class="sv-form" novalidate>
          <label class="field wide"><span>VAD SPARAR DU TILL?</span>
            <input class="input" name="name" type="text" maxlength="60" autocomplete="off" placeholder="Till exempel Studio"></label>
          <div class="form-grid">
            <label class="field"><span>BELOPP (KR)</span>
              <input class="input num" name="amountSek" type="number" min="1" step="1" inputmode="numeric" placeholder="300 000"></label>
            <label class="field"><span>DATUM</span>
              <input class="input num" name="date" type="date"></label>
          </div>
          <p class="plain sv-explain">De sista 24 månaderna före datumet flyttar Walter gradvis till kontanter, en bit vid varje söndagskoll. Ett krypto-fall på 50 % strax före datumet går inte att vänta ut. I historiken gav det en lugnare resa men oftast mindre pengar – det är ett val för den som inte tål ett stort fall strax före datumet.</p>
          <p class="small sv-glide" id="goal-glide" aria-live="polite"></p>
          <p class="small">Inget löfte: Walter kan inte lova att du når målet. Han minskar bara svängningarna när datumet närmar sig, inte nödvändigtvis det sämsta utfallet.</p>
          <div class="form-actions start">
            <button type="submit" class="btn btn-primary">SPARA MÅLET</button>
            <button type="button" class="btn" id="goal-remove"${S.goal ? "" : " hidden"}>TA BORT MÅLET</button>
          </div>
          <p class="small msg" id="goal-msg" aria-live="polite">${goalDraft.fromPlan ? "Förifyllt från din gamla plan. Spara för att slå på målet." : ""}</p>
        </form>
      </section>
      <section class="panel" aria-label="Månadssparande">
        <h3>MÅNADSSPARANDE</h3>
        <form id="savings-form" class="sv-form" novalidate>
          <div class="form-grid">
            <label class="field"><span>BELOPP PER MÅNAD (KR)</span>
              <input class="input num" name="monthlySek" type="number" min="0" step="1" inputmode="numeric" placeholder="0 = av"></label>
            <label class="field"><span>DAG I MÅNADEN</span>
              <select name="day">${Array.from({ length: 28 }, (_, i) => `<option value="${i + 1}">${i + 1}</option>`).join("")}</select></label>
          </div>
          <p class="plain sv-explain">Den dagen sätter Walter in beloppet och köper direkt efter sina andelar – bara med de nya pengarna, han säljer inget. Var sidan stängd gör han det nästa gång han räknar, en gång per månad.</p>
          <p class="sv-honest"><b>PAPER</b><span>Låtsasinsättning – inga riktiga pengar flyttas.</span></p>
          <div class="form-actions start"><button type="submit" class="btn btn-primary">SPARA SPARANDET</button></div>
          <p class="small msg" id="savings-msg" aria-live="polite"></p>
        </form>
        <div class="fixed">
          <span class="label">FASTA REGLER · GÅR INTE ATT ÄNDRA</span>
          <div><span>Max investerat</span><span class="num">${nf(0).format(S.rules.maxInvested * 100)} %</span></div>
          <div><span>Kontant, alltid minst</span><span class="num">${nf(0).format(S.rules.minCash * 100)} %</span></div>
          <div><span>Insättningar räknas som vinst</span><span class="num">aldrig</span></div>
        </div>
      </section>
    </div>
    ${isUser ? "" : `<div class="panel sv-owner" id="owner-snippet" hidden>
      <h3>ÄGARENS WALTER · DATA/STATE.JSON</h3>
      <p class="plain">Din Walter läser målet och sparandet från <b>data/state.json</b> – sidan kan inte skriva där. Byt ut hela blocken <b>"savings": {…}</b> och <b>"goal": …</b> i state.json (de går över flera rader) mot raderna nedan och kör sedan <b>walter deploy</b> – den låser state.enc och skickar den till main. Först då ser Walter i GitHub Actionen ändringen; hämtaren ensam når aldrig dit.</p>
      <pre class="sv-pre" id="owner-snippet-text"></pre>
    </div>`}

    <div class="section-title"><h2>UTTAG</h2><span class="small">Vad du kan ta ut, och när.</span></div>
    <div class="panel" style="margin-top:20px" id="goal">
      <div class="form-grid">
        <label class="field wide"><span>BELOPP ATT TA UT (NETTO)</span>
          <div class="goal-amount">
            <input type="range" id="goal-range" min="5000" max="500000" step="1000" aria-label="Målbelopp">
            <input type="number" id="goal-custom" min="1" step="1" inputmode="numeric" class="input num" aria-label="Eget belopp i kronor">
          </div>
        </label>
        <label class="field"><span>TILL VAD?</span>
          <select id="goal-purpose">${Object.entries(PURPOSES).map(([k, v]) => `<option value="${k}">${v[0]}</option>`).join("")}</select>
        </label>
        <div class="field"><span>NÄR?</span>
          <div class="seg full" role="group" aria-label="Tidshorisont">${Object.keys(HORIZONS).map((k) =>
            `<button type="button" data-h="${k}">${k.toUpperCase()}</button>`).join("")}</div>
        </div>
      </div>
      <div id="goal-out"></div>
    </div>

    <div class="cards">
      <section class="panel" aria-label="Avgifter">
        <h3>${isUser ? "AVGIFTER · BARA FÖR UTTAGSRÄKNAREN" : "AVGIFTER"}</h3>
        ${isUser ? `<p class="plain" style="margin-bottom:12px">Fälten här ändrar bara uträkningen under Uttag. Walters affärer räknas alltid med ${esc(feeName)}s avgifter.</p>` : ""}
        <form id="settings-form">
          <div class="form-grid">
            ${[["takerPct", `${esc(feeName.toUpperCase())} TAKER FEE (%)`], ["slippagePct", "SLIPPAGE (%)"], ["sepaEur", "SEPA-UTTAG (€)"], ["fxPct", "VALUTAVÄXLING PÅ BANKEN (%)"]].map(([k, t]) => `
            <label class="field"><span>${t}</span>
              <input class="input num" type="number" name="${k}" min="0" max="100" step="0.01" placeholder="${feeDefaults[k] != null ? esc(feeDefaults[k]) + " (standard)" : "från din börs prislista"}">
            </label>`).join("")}
          </div>
          <p class="small" style="margin-top:12px">${isUser ? feeSourceText : "Tomt fält = standard från state.json."} Sparas bara i den här webbläsaren. API-nycklar läggs aldrig in här.</p>
          <div class="form-actions"><button type="submit" class="btn btn-primary">SPARA</button></div>
        </form>
      </section>
      <section class="panel" aria-label="Handelsläge">
        <h3>HANDELSLÄGE</h3>
        ${isUser ? `
        <p class="live-not-yet"><b>PAPER</b><span>Live: inte än</span></p>
        <p class="small" style="margin-top:12px">Walter handlar bara med låtsaspengar. Han kan inte röra riktiga pengar än, så det finns ingen knapp och inget fält för nycklar.</p>` : `
        <div class="seg" role="group" aria-label="Handelsläge" style="width:max-content">
          <button type="button" id="btn-paper">PAPER</button>
          <button type="button" id="btn-live">LIVE</button>
        </div>
        <p class="small" style="margin-top:12px">PAPER är standard: inga riktiga pengar. LIVE kräver att du skriver JA GÅ LIVE och gäller bara den här fliken. Walter lägger aldrig order själv.</p>`}
      </section>
      <section class="panel" aria-label="Visning">
        <h3>VISNING</h3>
        <label class="switch"><input type="checkbox" role="switch" id="pro-toggle"><span>Pro-läge – dölj förklaringarna</span></label>
        <p class="small" style="margin-top:12px">Förklaringarna i vanliga ord är påslagna från början. Pro-läget döljer dem, siffrorna finns kvar.</p>
      </section>
      ${isUser ? `
      <section class="panel" aria-label="Kopia">
        <h3>KOPIA</h3>
        <p class="plain">Din Walter finns bara i den här webbläsaren. Rensar du den är portföljen borta – spara en kopia ibland.</p>
        ${ctx.storageOk === false ? '<p class="warn small">Din webbläsare låter mig inte spara. Allt försvinner när du stänger fliken.</p>' : ""}
        <div class="form-actions start">
          <button type="button" class="btn btn-primary" id="btn-export">SPARA KOPIA</button>
          <button type="button" class="btn" id="btn-import">LÄS IN KOPIA</button>
          <input type="file" id="import-file" accept=".json,application/json" hidden>
        </div>
        <p class="small msg" id="copy-msg" aria-live="polite"></p>
        <div class="form-actions start" id="import-confirm" style="display:none">
          <button type="button" class="btn btn-danger" id="import-ok">ERSÄTT</button>
          <button type="button" class="btn" id="import-cancel">AVBRYT</button>
        </div>
      </section>
      <section class="panel" aria-label="Börja om">
        <h3>BÖRJA OM</h3>
        <form id="reset-form">
          <p class="small">Tar bort din Walter, portföljen och loggen i den här webbläsaren. Skriv <b>BÖRJA OM</b> för att bekräfta.</p>
          <input id="reset-confirm" class="input" type="text" autocomplete="off" spellcheck="false" placeholder="BÖRJA OM" aria-label="Skriv BÖRJA OM för att bekräfta" style="margin-top:12px">
          <div class="form-actions"><button type="submit" class="btn btn-danger" id="reset-ok" disabled>BÖRJA OM</button></div>
        </form>
      </section>` : ""}
      ${who === "owner" ? `
      <section class="panel" aria-label="Glöm koden">
        <h3>DEN HÄR ENHETEN</h3>
        <p class="plain">Koden är sparad i den här webbläsaren, därför ser du din Walter här.</p>
        <div class="form-actions start"><button type="button" class="btn" id="btn-forget-owner">GLÖM KODEN PÅ DEN HÄR ENHETEN</button></div>
        <p class="small msg" id="forget-msg" aria-live="polite"></p>
      </section>` : ""}
      ${isUser ? `
      <section class="panel" aria-label="Lås upp min Walter">
        <h3>LÅS UPP MIN WALTER</h3>
        <form id="owner-form">
          <label class="field"><span>KOD</span>
            <input id="owner-code" class="input" type="password" autocomplete="off" spellcheck="false" aria-describedby="owner-msg">
          </label>
          <div class="form-actions"><button type="submit" class="btn btn-primary" id="owner-ok">LÅS UPP</button></div>
        </form>
        <p class="small msg" id="owner-msg" aria-live="polite">Bara för ägaren. Koden sparas i den här webbläsaren först när den stämmer.</p>
      </section>` : ""}
    </div>`;

  // ---------- Mål och månadssparande ----------
  // Användaren: sparas i walter.user (WalterUser.setGoal / setSavings) och gäller från nästa gång Walter räknar.
  // Ägaren: state.json (top-level goal / savings) – sidan visar raderna att klistra in.
  const gf = $("goal-form"), svf = $("savings-form");
  gf.elements.name.value = goalDraft.name || "";
  gf.elements.amountSek.value = goalDraft.amountSek || "";
  gf.elements.date.value = goalDraft.date || "";
  svf.elements.monthlySek.value = savingsNow ? savingsNow.monthlySek : "";
  svf.elements.day.value = String((S.savings && S.savings.day) || 25);
  const glideText = () => {
    const d = gf.elements.date.value;
    if (!E || !/^\d{4}-\d{2}-\d{2}$/.test(d)) { $("goal-glide").textContent = ""; return; }
    const f = E.glideFactor({ date: d }, isoToday);
    $("goal-glide").textContent = f >= 1 ? `Med det datumet: full andel tills ${monthYear(addMonths(d, -24))}, sedan gradvis mot kontanter.`
      : f <= 0 ? "Med det datumet: allt som kontanter vid nästa koll."
      : `Med det datumet: nu ${nf(0).format(f * 100)} % av vanliga andelar.`;
  };
  gf.elements.date.addEventListener("input", glideText);
  glideText();
  const U = window.WalterUser;
  const ownerSnippet = (goal, savings) => {
    const lines = [];
    if (savings) lines.push(`"savings": ${JSON.stringify(savings)},`);
    lines.push(`"goal": ${JSON.stringify(goal === undefined ? (S.goal || null) : goal)},`);
    $("owner-snippet-text").textContent = lines.join("\n");
    $("owner-snippet").hidden = false;
    $("owner-snippet").scrollIntoView({ block: "nearest" });
  };
  // Användarens Walter läses, ändras och sparas – sedan ritas sidan om med det nya målet/sparandet
  const saveUser = (change, msgEl) => {
    const user = U.load();
    if (!user) { msgEl.textContent = "Jag hittar ingen sparad Walter att ändra."; return; }
    if (!change(user)) { msgEl.textContent = "Kontrollera fälten – något stämmer inte."; return; }
    if (!U.save(user)) { msgEl.textContent = "Din webbläsare låter mig inte spara."; return; }
    try { window.localStorage.removeItem(own("plan")); } catch { /* lagring blockerad */ }
    location.reload();
  };
  const readGoal = () => ({ name: gf.elements.name.value, amountSek: Math.round(+gf.elements.amountSek.value), date: gf.elements.date.value });
  gf.addEventListener("submit", (e) => {
    e.preventDefault();
    const g = readGoal();
    if (!(g.amountSek > 0) || !/^\d{4}-\d{2}-\d{2}$/.test(g.date)) { $("goal-msg").textContent = "Skriv ett belopp och välj ett datum."; return; }
    if (isUser) { saveUser((u) => U.setGoal(u, g), $("goal-msg")); return; }
    ownerSnippet({ name: String(g.name).trim().slice(0, 60) || "Mitt mål", amountSek: g.amountSek, date: g.date });
    $("goal-msg").textContent = "Klistra in raden under formulären i state.json.";
  });
  $("goal-remove").addEventListener("click", () => {
    if (isUser) { saveUser((u) => U.setGoal(u, null), $("goal-msg")); return; }
    ownerSnippet(null);
    $("goal-msg").textContent = "Klistra in raden under formulären i state.json.";
  });
  svf.addEventListener("submit", (e) => {
    e.preventDefault();
    const amt = Math.round(+svf.elements.monthlySek.value || 0), d = +svf.elements.day.value;
    if (!(amt >= 0) || !(d >= 1 && d <= 28)) { $("savings-msg").textContent = "Skriv ett belopp (0 = av)."; return; }
    if (isUser) { saveUser((u) => U.setSavings(u, amt, d, isoToday), $("savings-msg")); return; }
    const since = savingsNow && savingsNow.since ? savingsNow.since : isoToday;
    ownerSnippet(undefined, { monthlySek: amt, day: d, since });
    $("savings-msg").textContent = "Klistra in raden under formulären i state.json.";
  });

  // ---------- Uttag: generisk uttagsräknare (slider 5 000–500 000 kr + eget belopp) ----------
  // Brutto = det som måste säljas för att netto ska landa på banken i SEK:
  // sälj på börsen (taker + slippage) → EUR → SEPA-uttag (fast €) → banken växlar till SEK (FX %).
  // null när avgifter eller dagens EURSEK saknas – då räknas inget på gissning.
  const grossFor = (netto) => {
    const eursek = m.eursek && m.eursek.value;
    if (!feesKnown || !eursek) return null;
    const t = fees.takerPct / 100, s = fees.slippagePct / 100, f = fees.fxPct / 100;
    const sepa = fees.sepaEur * eursek;
    const beforeFx = netto / (1 - f);
    const brutto = (beforeFx + sepa) / ((1 - t) * (1 - s));
    return {
      brutto,
      parts: [
        [`${feeName} taker ${nf(2).format(fees.takerPct)} %`, brutto * t],
        [`Slippage ${nf(1).format(fees.slippagePct)} %`, brutto * (1 - t) * s],
        [`SEPA-uttag €${nf(0).format(fees.sepaEur)} (EURSEK ${nf(4).format(eursek)}, ${day(m.eursek.asOf)})`, sepa],
        [`Valutaväxling ${nf(1).format(fees.fxPct)} %`, beforeFx - netto]
      ]
    };
  };
  function renderGoal() {
    const [daysH, label] = HORIZONS[goal.horizon];
    const netto = goal.amount;
    const gr0 = grossFor(netto);
    const brutto = gr0 ? gr0.brutto : netto;
    const what = PURPOSES[goal.purpose][1];
    const enough = pf.value > 0 && pf.value >= brutto;
    const growth = (target) => {
      const need = target / pf.value - 1;
      return { need, perMonth: Math.pow(1 + need, 30 / daysH) - 1 };
    };

    let plain;
    if (!(pf.value > 0)) plain = "Portföljens värde saknas, så målet kan inte räknas ut än.";
    else if (enough) plain = `Du har redan nog för ${what}: ${kr(pf.value)} räcker till ${kr(netto)}.` +
      (pf.holdings.CASH >= brutto ? " Pengarna ligger redan som kontanter, så du kan ta ut dem när du vill." : "");
    else {
      const gr = growth(brutto);
      plain = `För ${what} om ${label} behöver ${kr(pf.value)} växa till ${kr(brutto)}. Det är ${pct(gr.need * 100, 0)}, ungefär ${pct(gr.perMonth * 100, 0)} i månaden.` +
        (parked ? " Just nu vilar Walter och pengarna växer inte." : " Det finns ingen garanti att nå dit – det här visar bara hur stor ökningen skulle behöva vara.");
    }

    // Tre vägar. BALANSERAT = när Walter inte skulle vila. OPTIMERAT (TP) = när uttaget ryms över startkapitalet –
    // i marknadsvinst om det finns, annars i de manuella insättningarna (sägs rakt ut).
    const maxRed = S.rules.parkeraAtRed - 1;
    const calm = red <= maxRed;
    const short = kr(Math.max(0, brutto - pf.value));
    const tp = start + brutto;
    const alts = [
      { name: "AKUT", when: "Sälj nu", ok: enough,
        text: enough ? `Du kan ta ut ${kr(netto)} i dag. Kvar i Walter: ${kr(pf.value - brutto)}.` : `Räcker inte i dag – det fattas ${short}.` },
      { name: "BALANSERAT", when: `När högst ${maxRed} lampor lyser`, ok: enough && calm,
        text: !calm ? `Vänta tills högst ${maxRed} av ${total} lampor lyser (nu ${red}).`
          : enough ? `Marknaden är lugn nog (${red} av ${total} lampor). Du kan sälja direkt.` : `Lugnt nu (${red} av ${total} lampor), men det fattas ${short}.` },
      { name: "OPTIMERAT", when: "Vänta på TP", ok: pf.value > 0 && pf.value >= tp,
        text: !(pf.value > 0) ? "Portföljens värde saknas."
          : marketGain >= brutto ? `Uttaget ryms i marknadsvinsten (${kr(marketGain)}). Insättningarna lämnas orörda.`
          : pf.value >= tp ? `Uttaget ryms i insättningar (${kr(topUp)})${marketGain > 0 ? ` och marknadsvinst (${kr(marketGain)})` : " – ingen marknadsvinst än"}. Startkapitalet på ${kr(start)} lämnas orört.`
          : (() => { const gr = growth(tp); return `Vänta tills portföljen är värd ${kr(tp)} – då ryms uttaget över startkapitalet. Det är ${pct(gr.need * 100, 0)} till, ungefär ${pct(gr.perMonth * 100, 0)} i månaden på ${label}.`; })() }
    ];

    $("goal-out").innerHTML = `
      <p class="goal-plain">${esc(plain)}</p>
      ${feesKnown ? "" : '<p class="warn small">Avgifterna är inte angivna, så beloppet räknas utan avgifter. Fyll i dem under Avgifter nedan.</p>'}
      ${feesKnown && !gr0 ? '<p class="warn small">Dagens EURSEK saknas, så beloppet räknas utan avgifter tills kursen har hämtats.</p>' : ""}
      <div class="goal-alts">${alts.map((a) => `
        <div class="goal-alt">
          <div class="goal-alt-head">${check(a.ok)}<b>${a.name}</b><span>${esc(a.when)}</span></div>
          <p>${esc(a.text)}</p>
        </div>`).join("")}
      </div>
      <details style="margin-top:12px"><summary>SIFFRORNA</summary><ul>
        <li>Netto (det du får på banken): ${kr(netto)}</li>
        ${gr0 ? gr0.parts.map(([n, v]) => `<li>${esc(n)}: ${kr(v)}</li>`).join("") : ""}
        <li>Avgifter totalt: ${gr0 ? kr(brutto - netto) : "inte uträknade"}</li>
        <li>Brutto (det som måste säljas): ${kr(brutto)}</li>
        <li>TP (startkapital + brutto): ${kr(tp)}</li>
        <li>Portfölj nu: ${kr(pf.value)} · tid: ${label} (${daysH} dagar)</li>
      </ul></details>`;
  }

  const range = $("goal-range"), custom = $("goal-custom");
  const syncGoal = () => {
    range.value = Math.min(500000, Math.max(5000, goal.amount));
    custom.value = goal.amount;
    $("goal-purpose").value = goal.purpose;
    document.querySelectorAll("#goal [data-h]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.h === goal.horizon)));
    store.set(own("goal"), goal);
    renderGoal();
  };
  range.addEventListener("input", () => { goal.amount = +range.value; syncGoal(); });
  custom.addEventListener("change", () => { const v = Math.round(+custom.value); if (v > 0) goal.amount = v; syncGoal(); });
  $("goal-purpose").addEventListener("change", (e) => { goal.purpose = e.target.value; syncGoal(); });
  document.querySelectorAll("#goal [data-h]").forEach((b) => b.addEventListener("click", () => { goal.horizon = b.dataset.h; syncGoal(); }));
  syncGoal();

  // ---------- Avgifter ----------
  const sf = $("settings-form");
  FEE_KEYS.forEach((k) => { if (Number.isFinite(settings[k])) sf.elements[k].value = settings[k]; });
  sf.addEventListener("submit", (e) => {
    e.preventDefault();
    const next = settings.pro === true ? { pro: true } : {};
    FEE_KEYS.forEach((k) => {
      const raw = sf.elements[k].value.trim();
      if (raw !== "" && Number.isFinite(+raw) && +raw >= 0) next[k] = +raw;
    });
    store.set(own("settings"), next);
    location.reload();
  });

  // ---------- PAPER / LIVE ----------
  // PAPER är standard. LIVE kräver "JA GÅ LIVE" och gäller bara den här fliken (sessionStorage).
  // Användaren har ingen LIVE: "Live: inte än" står där knapparna skulle ha legat, och dialogen tas bort.
  const LIVE_PHRASE = "JA GÅ LIVE";
  let live = !isUser && store.get(own("live"), false, "sessionStorage") === true;
  const dlg = $("live-dialog"), confirmInput = $("live-confirm"), okBtn = $("live-ok");
  const renderLive = () => {
    if (!isUser) {
      $("btn-paper").setAttribute("aria-pressed", String(!live));
      $("btn-live").setAttribute("aria-pressed", String(live));
    }
    document.body.classList.toggle("is-live", live);
    $("trade-mode").textContent = live ? "LIVE" : "PAPER";
    $("footer").textContent = (live
      ? "LIVE · RIKTIGA PENGAR · WALTER LÄGGER INGA ORDER SJÄLV"
      : "PAPER TRADING · INGA RIKTIGA PENGAR" + (isUser ? " · LIVE: INTE ÄN" : "")) +
      `${S.version ? ` · V${S.version}` : ""} · DATA PER ${day(S.updatedAt).toUpperCase()}`;
  };
  if (isUser) {
    if (dlg) dlg.remove();
  } else {
    $("btn-paper").addEventListener("click", () => { live = false; store.set(own("live"), false, "sessionStorage"); renderLive(); });
    $("btn-live").addEventListener("click", () => {
      if (live) return;
      confirmInput.value = "";
      okBtn.disabled = true;
      dlg.showModal();
      confirmInput.focus();
    });
    confirmInput.addEventListener("input", () => { okBtn.disabled = confirmInput.value.trim() !== LIVE_PHRASE; });
    $("live-form").addEventListener("submit", (e) => {
      if (e.submitter && e.submitter.value === "live" && confirmInput.value.trim() === LIVE_PHRASE) {
        live = true;
        store.set(own("live"), true, "sessionStorage");
      }
      renderLive();
    });
  }
  renderLive();

  // ---------- Pro-läge ----------
  const proToggle = $("pro-toggle");
  proToggle.checked = settings.pro === true;
  proToggle.addEventListener("change", () => {
    settings.pro = proToggle.checked;
    if (!settings.pro) delete settings.pro;
    store.set(own("settings"), settings);
    document.body.classList.toggle("pro", proToggle.checked);
  });

  // ---------- Kopia och Börja om (bara användaren) ----------
  if (isUser) {
    const U = window.WalterUser;
    const copyMsg = $("copy-msg");
    $("btn-export").addEventListener("click", () => {
      const user = U.load();
      if (!user) { copyMsg.textContent = "Jag hittar ingen sparad Walter att kopiera."; return; }
      const file = U.exportFile(user);
      const url = URL.createObjectURL(file);
      const a = document.createElement("a");
      a.href = url; a.download = file.name;
      document.body.appendChild(a); a.click(); a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      copyMsg.textContent = `Kopian ${file.name} är sparad i dina nedladdningar.`;
    });
    const fileInput = $("import-file");
    $("btn-import").addEventListener("click", () => fileInput.click());
    fileInput.addEventListener("change", async () => {
      const f = fileInput.files && fileInput.files[0];
      fileInput.value = "";
      if (!f) return;
      let user;
      try { user = U.importText(await f.text()); } catch (e) {
        pending = null; importConfirm.style.display = "none"; copyMsg.textContent = "Det här är ingen Walter-kopia."; return;
      }
      // Kopian ersätter Walter i den här webbläsaren – fråga först, så att ingen portfölj försvinner av misstag.
      pending = user;
      copyMsg.textContent = "Det här ersätter din nuvarande Walter.";
      importConfirm.style.display = "";
      $("import-cancel").focus();
    });
    const importConfirm = $("import-confirm");
    let pending = null;
    $("import-cancel").addEventListener("click", () => {
      pending = null; importConfirm.style.display = "none"; copyMsg.textContent = "Inget ändrat.";
    });
    $("import-ok").addEventListener("click", () => {
      if (!pending) return;
      if (!U.save(pending)) { copyMsg.textContent = "Din webbläsare låter mig inte spara kopian."; return; }
      location.reload();
    });

    const RESET_PHRASE = "BÖRJA OM";
    const resetInput = $("reset-confirm"), resetOk = $("reset-ok");
    resetInput.addEventListener("input", () => { resetOk.disabled = resetInput.value.trim() !== RESET_PHRASE; });
    $("reset-form").addEventListener("submit", (e) => {
      e.preventDefault();
      if (resetInput.value.trim() !== RESET_PHRASE) return;
      try {
        const ls = window.localStorage;
        const keys = [];
        for (let i = 0; i < ls.length; i++) keys.push(ls.key(i));
        keys.filter(isUserKey).forEach((k) => ls.removeItem(k));
        Object.keys(window.sessionStorage).filter(isUserKey).forEach((k) => window.sessionStorage.removeItem(k));
      } catch (err) { /* lagring blockerad: inget sparat att ta bort */ }
      location.reload();
    });
  }

  // ---------- Glöm koden (bara ägaren i mobilen, inte lokalt med state.js) ----------
  if (who === "owner") {
    $("btn-forget-owner").addEventListener("click", () => {
      if (!window.WalterUser.forgetOwner()) { $("forget-msg").textContent = "Din webbläsare låter mig inte ta bort koden."; return; }
      location.reload();
    });
  }

  // ---------- Lås upp min Walter (bara användaren – ägaren är redan upplåst) ----------
  // Samma upplåsning som introt (WalterUser.unlockOwner): koden sparas bara när den stämmer.
  if (isUser) {
    const ownerMsg = $("owner-msg"), ownerOk = $("owner-ok");
    $("owner-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const code = $("owner-code").value;
      if (!code) return;
      ownerOk.disabled = true;
      ownerMsg.textContent = "Provar koden …";
      const res = await window.WalterUser.unlockOwner(code);
      if (!res.ok) { ownerMsg.textContent = res.msg; ownerOk.disabled = false; return; }
      location.reload();
    });
  }

  // ================================================================
  // Sidbyte via # (#siffror och okända # visar översikten)
  // ================================================================
  const PAGES = ["oversikt", "pro", "logg", "k4", "installningar"].filter((p) => !(isUser && p === "k4"));
  const route = () => {
    const h = location.hash.slice(1);
    const page = PAGES.includes(h) ? h : "oversikt";
    document.querySelectorAll("[data-page]").forEach((s) => { s.hidden = s.dataset.page !== page; });
    document.querySelectorAll(".nav [data-view]").forEach((a) => {
      if (a.dataset.view === page) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current");
    });
    document.title = page === "oversikt" ? `WALTER · ${AUTO ? "AUTOPILOT" : MODE.word}` : `WALTER · ${page === "installningar" ? "INSTÄLLNINGAR" : page.toUpperCase()}`;
    if (PAGES.includes(h)) window.scrollTo(0, 0);
  };
  window.addEventListener("hashchange", route);
  route();
  // Menyn börjar alltid till vänster, som på W-Cipher (Safari kan annars minnas en sidledsrullning)
  const navStart = () => document.querySelectorAll(".nav").forEach((n) => { n.scrollLeft = 0; });
  navStart(); window.addEventListener("pageshow", navStart);
  }

  // Nyckeln i localStorage/sessionStorage: användaren får walter.user.*, ägaren walter.*
  function keyFor(who, k) { return (who === "user" ? "walter.user." : "walter.") + k; }
  // Det som "Börja om" rensar: användarens Walter och allt under walter.user.*
  function isUserKey(k) { return k === "walter.user" || String(k).startsWith("walter.user."); }

  window.WalterApp = { start, keyFor, isUserKey };
})();
