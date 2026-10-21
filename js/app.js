// WALTER V1.6.3 – renderar data/state.js. Ingen build, inga beroenden.
(function () {
  "use strict";

  const S = window.WALTER_STATE;
  const $ = (id) => document.getElementById(id);

  // ---------- Lokal lagring (bara den här webbläsaren, try/catch om den är blockerad) ----------
  const store = {
    get(k, def, area = localStorage) { try { const v = area.getItem(k); return v ? JSON.parse(v) : def; } catch { return def; } },
    set(k, v, area = localStorage) { try { area.setItem(k, JSON.stringify(v)); } catch { /* lagring blockerad */ } }
  };
  const settings = store.get("walter.settings", {});
  // Avgifter är inställningar, aldrig hårdkodade. null = inte angivet.
  const fees = {
    tradingPct: Number.isFinite(settings.tradingFeePct) ? settings.tradingFeePct : null,
    withdrawalSek: Number.isFinite(settings.withdrawalFeeSek) ? settings.withdrawalFeeSek : null
  };

  // ---------- Format ----------
  const nf = (d = 0) => new Intl.NumberFormat("sv-SE", { minimumFractionDigits: d, maximumFractionDigits: d });
  const kr = (v) => nf(0).format(v) + " kr";
  const pct = (v, d = 1) => (v > 0 ? "+" : v < 0 ? "−" : "") + nf(d).format(Math.abs(v)) + " %";
  const usd = (v) => "$" + nf(0).format(v);
  const usdM = (v) => (v < 0 ? "−" : "+") + "$" + nf(0).format(Math.abs(v) / 1e6) + "M";
  const MONTHS = ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep", "okt", "nov", "dec"];
  const day = (iso) => { const d = new Date(iso + "T12:00:00"); return d.getDate() + " " + MONTHS[d.getMonth()]; };
  const esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

  const daysSince = (iso) => {
    const start = new Date(iso + "T00:00:00");
    const now = new Date();
    now.setHours(0, 0, 0, 0);
    return Math.floor((now - start) / 86400000) + 1;
  };

  // true = uppfyllt, false = inte, null = väntar på data
  const check = (ok) => ok === null || ok === undefined
    ? '<span class="dot off" title="Väntar på data"></span>'
    : ok ? '<span class="dot green" title="Uppfyllt"></span>'
         : '<span class="dot" title="Inte uppfyllt"></span>';

  // ---------- Härledda värden ----------
  const pf = S.portfolio;
  const m = S.market;
  const dd = pf.peak > 0 ? ((pf.peak - pf.value) / pf.peak) * 100 : 0;
  const invested = pf.value > 0 ? (pf.value - pf.holdings.CASH) / pf.value : 0;
  // Alltid 10 lampor. PARKERA när rules.parkeraAtRed (7) av 10 är risk-off.
  const LAMPS = 10;
  const red = S.lampScore.red;
  const total = LAMPS;
  const lampCountOk = S.lamps.length === LAMPS && S.lampScore.total === LAMPS;
  const green = total - red;
  const days = daysSince(S.startDate);
  const parked = S.mode === "PARKERA";
  const start = Number.isFinite(settings.startCapital) && settings.startCapital > 0 ? settings.startCapital : pf.start;

  // USDSEK: senast sparade live-kurs med datum, annars null. Ingen fast reservkurs.
  // Funktion, eftersom Uppdatera-knappen kan byta ut m.usdsek / m.btc mot färskare värden.
  const fx = () => {
    const usdsek = m.usdsek && m.usdsek.value != null ? m.usdsek : null;
    const ageDays = usdsek ? Math.floor((Date.now() - new Date(usdsek.asOf + "T12:00:00")) / 86400000) : null;
    const stale = ageDays != null && ageDays > 4;
    const btcSek = usdsek && m.btc.value != null ? m.btc.value * usdsek.value : null;
    return { usdsek, stale, btcSek };
  };

  // ---------- Logos (fasta filer, aldrig genererade) ----------
  const logos = document.querySelectorAll("[data-logo]");
  let failed = 0;
  const onLogoError = (img) => {
    img.hidden = true;
    if (++failed === logos.length) document.querySelector(".logo-text").hidden = false;
  };
  logos.forEach((img) => {
    // Bilden kan ha hunnit misslyckas innan skriptet körs
    if (img.complete && img.naturalWidth === 0) onLogoError(img);
    else img.addEventListener("error", () => onLogoError(img));
  });

  // ---------- Topbar ----------
  $("version").textContent = "V" + S.version;
  const pill = $("mode-pill");
  pill.innerHTML = `<span class="dot${parked ? "" : " green"}"></span>${esc(S.mode)}`;
  pill.classList.toggle("is-active", !parked);

  // ---------- Ticker ----------
  const renderTicker = () => {
  const { usdsek, stale: fxStale } = fx();
  const ticks = [
    { l: "10Y", v: nf(2).format(m.us10y.value) + " %", d: (m.us10y.changeBp > 0 ? "+" : "−") + Math.abs(m.us10y.changeBp) + " bp", c: m.us10y.changeBp > 0 ? "down" : "up" },
    { l: "DXY", v: nf(2).format(m.dxy.value), d: "", c: "flat" },
    { l: "VIX", v: m.vix.value != null ? nf(2).format(m.vix.value) : pct(m.vix.changePct), d: m.vix.value != null ? pct(m.vix.changePct) : day(m.vix.asOf), c: m.vix.changePct > 0 ? "down" : "up" },
    { l: "ETF", v: usdM(m.etfFlow.mtdUsd), d: m.etfFlow.asOf ? MONTHS[+m.etfFlow.asOf.slice(5, 7) - 1] : "okt", c: m.etfFlow.mtdUsd < 0 ? "down" : "up" },
    { l: "NDX", v: pct(m.nasdaq.changePct), d: "", c: m.nasdaq.changePct < 0 ? "down" : "up" },
    { l: "SPX", v: pct(m.spx.changePct), d: "", c: m.spx.changePct < 0 ? "down" : "up" },
    { l: "BTC", v: usd(m.btc.value), d: "", c: "flat" },
    { l: "USDSEK", v: usdsek ? nf(2).format(usdsek.value) : "väntar på data", d: usdsek && fxStale ? "per " + day(usdsek.asOf) : "", c: fxStale ? "down" : "flat" }
  ];
  $("ticker").innerHTML = ticks.map((t, i) =>
    (i ? '<span class="tick-sep">·</span>' : "") +
    `<span class="tick"><span class="tick-label">${t.l}</span>` +
    `<span class="tick-value num ${t.c}">${esc(t.v)}</span>` +
    (t.d ? `<span class="tick-delta num ${t.c}">${esc(t.d)}</span>` : "") + "</span>"
  ).join("");
  };
  renderTicker();

  // ---------- Portfolio ----------
  // Graf: historiken i state.json + dagens värde om det är nyare
  // Tom historik = platt linje på startkapitalet, så grafen alltid ritas.
  const hist = (pf.history || []).slice();
  if (!hist.length) hist.push({ date: S.startDate, value: start }, { date: S.updatedAt, value: start });
  if (hist[hist.length - 1].date < S.updatedAt) hist.push({ date: S.updatedAt, value: pf.value, cash: pf.holdings.CASH });
  if (hist.length < 2) hist.unshift({ date: S.startDate, value: start });
  const chart = (() => {
    const W = 320, H = 110, P = 8;
    const vals = hist.map((h) => h.value);
    let lo = Math.min(...vals, start), hi = Math.max(...vals, start);
    if (hi - lo < 1) { lo -= 5; hi += 5; }
    const x = (i) => P + (i * (W - 2 * P)) / (hist.length - 1);
    const y = (v) => H - P - ((v - lo) * (H - 2 * P)) / (hi - lo);
    const pts = hist.map((h, i) => `${x(i).toFixed(1)},${y(h.value).toFixed(1)}`).join(" ");
    const last = hist[hist.length - 1];
    return `<svg class="pf-chart" viewBox="0 0 ${W} ${H}" role="img" aria-label="Portföljens värde ${day(hist[0].date)} till ${day(last.date)}">
        <line x1="${P}" x2="${W - P}" y1="${y(start)}" y2="${y(start)}" class="pf-start"/>
        <polyline points="${P},${H - P} ${pts} ${W - P},${H - P}" class="pf-area"/>
        <polyline points="${pts}" class="pf-line"/>
        ${hist.map((h, i) => `<circle cx="${x(i)}" cy="${y(h.value)}" r="${i === hist.length - 1 ? 4.5 : 2.5}" class="pf-dot"/>`).join("")}
        <text x="${W - P - 12}" y="${Math.max(14, y(last.value) - 10)}" text-anchor="end" class="pf-label">${nf(0).format(last.value)} kr</text>
      </svg>
      <div class="pf-axis sub"><span>${day(hist[0].date)}</span><span>streckat = startkapital</span><span>${day(last.date)}</span></div>`;
  })();

  $("portfolio").innerHTML = `
    <h2>Portfolio</h2>
    <div class="pf-value num">${nf(0).format(pf.value)}<small>kr</small></div>
    ${chart}
    <div class="pf-cash"><span class="pulse" aria-hidden="true"></span>Kontant <strong class="num">${kr(pf.holdings.CASH)}</strong></div>
    <div class="chips">
      <span class="chip"><span class="dot ${dd < 8 ? "green" : dd < 12 ? "amber" : ""}"></span>DD <strong class="num">${nf(1).format(dd)} %</strong></span>
      <span class="chip">Level <strong>${S.level}</strong></span>
      <span class="chip">Kontant <strong class="num">${nf(0).format((1 - invested) * 100)} %</strong></span>
      <span class="chip">Dag <strong class="num">${days}</strong></span>
    </div>
    <div class="pf-ref num" id="pf-ref"></div>`;
  const renderRef = () => {
    const { usdsek, stale, btcSek } = fx();
    $("pf-ref").textContent = `Referens: ${nf(5).format(pf.refBtc)} BTC · startkapital ${kr(start)} · 1 BTC ` +
      (btcSek != null ? "≈ " + kr(btcSek) + (stale ? " (kurs per " + day(usdsek.asOf) + ")" : "") : "i kr: väntar på data");
  };
  renderRef();

  // ---------- Status + Uppdatera ----------
  // Webbläsaren kan bara hämta från källor som tillåter det (CORS): CoinGecko och valutakurser.
  // Riksbanken provas först; den skickar i dag inget CORS-svar, så då används ECB:s referenskurs (Frankfurter).
  // Lamporna (yfinance, BGeometrics, ETF m.fl.) kräver hämtaren.
  const MODE_TEXT = { PARKERA: "vilar", NORMAL: "är igång", OFFENSIV: "kör offensivt" };
  const stamp = (iso) => {
    if (!iso) return "okänt";
    const d = new Date(iso);
    return `${d.getDate()} ${MONTHS[d.getMonth()]} ${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
  };
  const diff = pf.value - start;
  // Samma takt som .github/workflows/walter-auto.yml: PARKERA ca var 3:e timme, annars var 15:e minut.
  const autoMsg = `Uppdateras automatiskt ${parked ? "ungefär var 3:e timme (WALTER är parkerad)" : "var 15e min"} via GitHub Actions – både kurser och WALTER-lampor.`;
  $("status").innerHTML = `
    <div class="status-grid">
      <div class="status-item"><span class="sub">Senast uppdaterad</span><strong class="num" id="status-time">${stamp(S.fetchedAt)}</strong></div>
      <div class="status-item"><span class="sub">WALTER</span><strong><span class="dot${parked ? "" : " green"}"></span>${esc(S.mode)} – ${esc(MODE_TEXT[S.mode] || "okänt läge")}</strong><span class="sub num">${red}/${total} röda lampor</span></div>
      <div class="status-item"><span class="sub">Portfölj</span><strong class="num">${kr(pf.value)}</strong><span class="num ${diff < 0 ? "down" : "up"}">${diff < 0 ? "−" : "+"}${kr(Math.abs(diff))} sedan start (${pct(start > 0 ? (diff / start) * 100 : 0)})</span></div>
      <button type="button" class="btn btn-primary status-btn" id="btn-refresh">Uppdatera</button>
    </div>
    <p class="sub status-msg" id="status-msg" aria-live="polite">Knappen hämtar färska kurser för BTC, USDSEK och EURSEK. ${autoMsg}</p>`;

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
    btn.textContent = "Hämtar …";
    const got = [], failedSrc = [];
    const [btcRes, fxRes] = await Promise.allSettled([
      getJson("https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd"),
      freshFx()
    ]);
    const now = new Date();
    if (btcRes.status === "fulfilled" && btcRes.value.bitcoin) {
      m.btc = { value: Math.round(btcRes.value.bitcoin.usd), unit: "usd", asOf: now.toISOString().slice(0, 10) };
      got.push(`BTC ${usd(m.btc.value)}`);
    } else failedSrc.push("CoinGecko");
    if (fxRes.status === "fulfilled") {
      Object.assign(m, fxRes.value);
      got.push(`USDSEK ${nf(4).format(m.usdsek.value)} och EURSEK ${nf(4).format(m.eursek.value)} (${m.usdsek.source}, ${day(m.usdsek.asOf)})`);
    } else failedSrc.push("valutakurser");
    renderTicker();
    renderRef();
    if (got.length) $("status-time").textContent = stamp(now.toISOString()) + " (kurser)";
    $("status-msg").innerHTML =
      (got.length ? `Färskt ${stamp(now.toISOString())}: ${esc(got.join(" · "))}. ` : "") +
      (failedSrc.length ? `<span class="warn">Kunde inte hämta: ${esc(failedSrc.join(", "))}. Senast sparade värden visas.</span> ` : "") +
      autoMsg;
    btn.disabled = false;
    btn.textContent = "Uppdatera";
  });

  // ---------- Notis (vanlig människa, inte siffervägg) ----------
  const notice = (() => {
    if (parked) {
      return {
        title: "WALTER står still – pengarna är parkerade",
        body: `${red} av ${total} varningslampor lyser. Marknaden är orolig just nu, så ${pf.holdings.CASH >= pf.value ? `alla ${kr(pf.value)} ligger kvar som kontanter` : `${kr(pf.holdings.CASH)} av ${kr(pf.value)} ligger som kontanter`}. Du behöver inte göra något.`,
        next: `WALTER börjar köpa igen när högst ${S.rules.parkeraAtRed - 1} lampor lyser.`
      };
    }
    return {
      title: "WALTER är igång",
      body: `${red} av ${total} varningslampor lyser. ${nf(0).format(invested * 100)} % av pengarna är investerade, resten ligger som kontanter.`,
      next: `WALTER parkerar allt om ${S.rules.parkeraAtRed} lampor eller fler börjar lysa.`
    };
  })();
  const latest = S.journal[0];
  $("notice").innerHTML = `
    <h2>Läget just nu</h2>
    <p class="notice-title">${esc(notice.title)}</p>
    <p class="notice-body">${esc(notice.body)}</p>
    ${latest ? `<p class="notice-body"><b>Senast (${day(latest.date)}):</b> ${esc(latest.plain)}</p>` : ""}
    <div class="notice-next"><span class="dot ${parked ? "amber" : "green"}" style="margin-top:6px"></span><span><b>Nästa steg:</b> ${esc(notice.next)}</span></div>`;

  // ---------- Lampor ----------
  const confirmed = S.lamps.filter((l) => l.status !== null).length;
  const fromData = S.lampScore.source === "data";
  // Mode ändras bara via journalen – säg till om datan pekar åt andra hållet
  const dataWantsPark = red >= S.rules.parkeraAtRed;
  const lampNote = !fromData
    ? `${confirmed} av ${total} lampor har data här. Poängen kommer från journalen tills datahämtningen är på plats.`
    : dataWantsPark === parked
      ? `Poängen räknas från hämtad data (${day(S.lampScore.asOf)}).`
      : `Poängen räknas från hämtad data (${day(S.lampScore.asOf)}). Datan säger ${dataWantsPark ? "PARKERA" : "att WALTER inte längre behöver parkera"}, men journalen säger ${S.mode}. Läget ändras först när du skriver en journalpost.`;
  $("lamps").innerHTML = `
    <h2>Varningslampor</h2>
    <div class="lamp-score"><span class="big num">${red}/${total}</span><span class="sub">risk-off · ${day(S.lampScore.asOf)} · PARKERA vid ${S.rules.parkeraAtRed}/${total}</span></div>
    <div class="lamp-row">${Array.from({ length: total }, (_, i) => `<span class="${i < red ? "red" : ""}"></span>`).join("")}</div>
    <ul class="lamp-list">
      ${S.lamps.map((l) => `
        <li>${check(l.status === null ? null : l.status === "green")}
          <span class="name">${esc(l.name)}<span class="rule">${esc(l.rule)}</span></span>
          <span class="val num">${l.value ? esc(l.value) : "väntar på data"}</span>
        </li>`).join("")}
    </ul>
    <p class="sub" style="margin:14px 0 0">${esc(lampNote)}</p>
    ${lampCountOk ? "" : `<p class="warn">state.json har ${S.lamps.length} lampor (poäng av ${S.lampScore.total}). WALTER räknar alltid med 10 – rätta i state.json.</p>`}`;

  // ---------- Allokering ----------
  const share = (k) => (pf.value > 0 ? pf.holdings[k] / pf.value : 0);
  const unlocked = { BTC: S.level >= 1, ETH: S.level >= 2, GOLD: S.level >= 3 };
  const rows = [
    { k: "BTC", name: "Bitcoin", note: "Level 1", cap: S.rules.caps.BTC },
    { k: "ETH", name: "Ethereum", note: "Level 2", cap: S.rules.caps.ETH },
    { k: "GOLD", name: "Guld", note: "PAXG / XAUT · L3", cap: S.rules.caps.GOLD },
    { k: "CASH", name: "Kontant", note: "minst 25 %", cap: null }
  ];
  $("allocation").innerHTML = `
    <h2>Fördelning</h2>
    <div class="alloc">
      ${rows.map((r) => {
        const locked = r.cap !== null && !unlocked[r.k];
        const s = share(r.k);
        const capPos = r.cap !== null ? r.cap * 100 : S.rules.minCash * 100;
        return `<div class="alloc-row">
          <div class="lbl"><b>${r.name}</b><span>${esc(r.note)}</span></div>
          <div class="bar${locked ? " locked" : ""}">
            <span class="fill" style="width:${s * 100}%"></span>
            <span class="cap" style="left:${capPos}%" title="${r.cap !== null ? "Tak" : "Golv"} ${capPos} %"></span>
          </div>
          <div class="pct num">${locked ? "låst" : nf(0).format(s * 100) + " %"}${r.cap !== null ? " / " + r.cap * 100 + " %" : ""}</div>
        </div>`;
      }).join("")}
    </div>
    <p class="alloc-foot">Investerat ${nf(0).format(invested * 100)} % av max ${S.rules.maxInvested * 100} %. Strecket visar tak (eller golv för kontanter).</p>`;

  // ---------- Levels ----------
  const levels = [
    { n: 1, name: "Level 1 · Bitcoin", tag: "BTC max 35 % · kontant minst 25 %", conds: [
      ["Aktiv från start", true],
      [`Inte PARKERA (färre än ${S.rules.parkeraAtRed}/${total} röda lampor)`, !parked]
    ] },
    { n: 2, name: "Level 2 · Ethereum", tag: "ETH 20 %", conds: [
      ["BTC är LONG", m.btcLong],
      ["ETH/BTC över 30-dagars snitt", m.ethBtcAbove30dMa],
      ["SOPR under 1,0", m.sopr.value == null ? null : m.sopr.value < 1]
    ] },
    { n: 3, name: "Level 3 · Guld", tag: "PAXG / XAUT 20 %", conds: [
      [`Dollarindex över 105 (nu ${nf(1).format(m.dxy.value)})`, m.dxy.value > 105],
      [`10-årig ränta över 4,5 % (nu ${nf(2).format(m.us10y.value)} %)`, m.us10y.value > 4.5],
      [`VIX upp mer än 10 % (${day(m.vix.asOf)}: ${pct(m.vix.changePct)})`, m.vix.changePct > 10]
    ] }
  ];
  $("levels").innerHTML = `
    <h2>Nivåer</h2>
    ${levels.map((l) => `
      <div class="level${l.n === S.level ? " current" : ""}">
        <div class="level-head"><span>${l.name}${l.n === S.level ? " · nu" : ""}</span><span class="tag">${esc(l.tag)}</span></div>
        <ul class="conds">${l.conds.map(([t, ok]) => `<li>${check(ok)}${esc(t)}</li>`).join("")}</ul>
      </div>`).join("")}`;

  // ---------- Upplåsning ----------
  const u = S.rules.unlock;
  const paths = [
    { name: "Tidig upplåsning", conds: [
      [`Minst ${u.early.days} dagar (dag ${days})`, days >= u.early.days],
      [`Upp ${u.early.gainPct} % till ${kr(start * (1 + u.early.gainPct / 100))} (nu ${kr(pf.value)})`, pf.value >= start * (1 + u.early.gainPct / 100)],
      [`Drawdown under ${u.early.maxDd} % (nu ${nf(1).format(dd)} %)`, dd < u.early.maxDd],
      [`Minst ${u.early.minGreen}/${total} gröna lampor (nu ${green})`, green >= u.early.minGreen]
    ] },
    { name: "Normal upplåsning", conds: [
      [`Minst ${u.normal.days} dagar (dag ${days})`, days >= u.normal.days],
      [`Över ${kr(u.normal.minValue)} (nu ${kr(pf.value)})`, pf.value > u.normal.minValue],
      [`Drawdown under ${u.normal.maxDd} % (nu ${nf(1).format(dd)} %)`, dd < u.normal.maxDd],
      [`Sharpe över ${u.normal.minSharpe}${pf.sharpe != null ? " (nu " + nf(2).format(pf.sharpe) + ")" : ""}`, pf.sharpe == null ? null : pf.sharpe > u.normal.minSharpe]
    ] }
  ];
  $("unlock").innerHTML = `
    <h2>Nästa level</h2>
    ${paths.map((p) => {
      const done = p.conds.filter(([, ok]) => ok === true).length;
      return `<div class="unlock-path">
        <h3>${p.name} <span class="sub">· ${done}/${p.conds.length}</span></h3>
        <ul class="conds">${p.conds.map(([t, ok]) => `<li>${check(ok)}${esc(t)}</li>`).join("")}</ul>
      </div>`;
    }).join("")}`;

  // ---------- Journal ----------
  $("journal").innerHTML = `
    <h2>Journal</h2>
    <div class="entries">
      ${S.journal.map((e) => `
        <article class="entry">
          <div class="entry-head">
            <span class="entry-date">${day(e.date)}</span>
            <span class="chip"><span class="dot${e.mode === "PARKERA" ? "" : " green"}"></span>${esc(e.mode)}</span>
            <span class="chip"><strong class="num">${e.red}/${total}</strong> röda</span>
          </div>
          <p class="entry-plain">${esc(e.plain)}</p>
          <details><summary>Siffrorna</summary><ul>${e.facts.map((f) => `<li>${esc(f)}</li>`).join("")}</ul></details>
        </article>`).join("")}
    </div>`;

  // ---------- Footer ----------
  // ---------- Sparmål (slider 5 000–500 000 kr + eget belopp) ----------
  const PURPOSES = { bil: ["Bil", "en bil"], husinsats: ["Husinsats", "en husinsats"], resa: ["Resa", "en resa"], rakningar: ["Räkningar", "räkningar"], buffert: ["Buffert", "en buffert"] };
  const HORIZONS = { "1v": [7, "1 vecka"], "1m": [30, "1 månad"], "3m": [91, "3 månader"], "6m": [182, "6 månader"] };
  const goal = Object.assign({ amount: 50000, purpose: "buffert", horizon: "1m" }, store.get("walter.goal", {}));
  if (!HORIZONS[goal.horizon]) goal.horizon = "1m";
  if (!PURPOSES[goal.purpose]) goal.purpose = "buffert";
  if (!(goal.amount > 0)) goal.amount = 50000;
  const feesKnown = fees.tradingPct != null && fees.withdrawalSek != null;

  $("goal").innerHTML = `
    <h2>Mitt mål</h2>
    <div class="goal-form">
      <label class="field field-wide"><span>Belopp att ta ut (netto)</span>
        <div class="goal-amount">
          <input type="range" id="goal-range" min="5000" max="500000" step="1000" aria-label="Målbelopp">
          <input type="number" id="goal-custom" min="1" step="1" inputmode="numeric" class="input num" aria-label="Eget belopp i kronor">
        </div>
      </label>
      <label class="field"><span>Till vad?</span>
        <select id="goal-purpose" class="input">${Object.entries(PURPOSES).map(([k, v]) => `<option value="${k}">${v[0]}</option>`).join("")}</select>
      </label>
      <div class="field"><span>När?</span>
        <div class="seg" role="group" aria-label="Tidshorisont">${Object.keys(HORIZONS).map((k) =>
          `<button type="button" class="seg-btn" data-h="${k}">${k}</button>`).join("")}</div>
      </div>
    </div>
    <div id="goal-out"></div>`;

  const renderGoal = () => {
    const [daysH, label] = HORIZONS[goal.horizon];
    const netto = goal.amount;
    // Netto är alltid ≤ brutto: brutto − säljavgift − uttagsavgift = netto
    const brutto = feesKnown ? (netto + fees.withdrawalSek) / (1 - fees.tradingPct / 100) : netto;
    const gain = pf.value > 0 ? brutto / pf.value - 1 : null;
    const perMonth = gain != null ? Math.pow(1 + gain, 30 / daysH) - 1 : null;
    const what = PURPOSES[goal.purpose][1];

    let plain;
    if (gain == null) plain = "Portföljens värde saknas, så målet kan inte räknas ut än.";
    else if (gain <= 0) plain = `Du har redan nog för ${what}: ${kr(pf.value)} räcker till ${kr(netto)}.`;
    else plain = `För ${what} om ${label} behöver ${kr(pf.value)} växa till ${kr(brutto)}. Det är ${pct(gain * 100, 0)}, ungefär ${pct(perMonth * 100, 0)} i månaden.` +
      (parked ? " Just nu är pengarna parkerade och växer inte." : " Det finns ingen garanti att nå dit – det här visar bara hur stor ökningen skulle behöva vara.");

    $("goal-out").innerHTML = `
      <p class="notice-body goal-plain">${esc(plain)}</p>
      ${feesKnown ? "" : '<p class="warn">Avgifterna är inte angivna, så beloppet räknas utan avgifter. Fyll i dem under <a href="#installningar">Inställningar</a>.</p>'}
      <details><summary>Siffrorna</summary><ul class="facts">
        <li>Netto (det du får ut): ${kr(netto)}</li>
        <li>Brutto (det som måste säljas): ${kr(brutto)}</li>
        <li>Avgifter: ${feesKnown ? `${kr(brutto - netto)} (trading fee ${nf(2).format(fees.tradingPct)} % + withdrawal fee ${kr(fees.withdrawalSek)})` : "inte angivna"}</li>
        <li>Portfölj nu: ${kr(pf.value)} · tid: ${label} (${daysH} dagar)</li>
      </ul></details>`;
  };

  const range = $("goal-range"), custom = $("goal-custom");
  const syncGoal = () => {
    range.value = Math.min(500000, Math.max(5000, goal.amount));
    custom.value = goal.amount;
    $("goal-purpose").value = goal.purpose;
    document.querySelectorAll("#goal [data-h]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.h === goal.horizon)));
    store.set("walter.goal", goal);
    renderGoal();
  };
  range.addEventListener("input", () => { goal.amount = +range.value; syncGoal(); });
  custom.addEventListener("change", () => { const v = Math.round(+custom.value); if (v > 0) goal.amount = v; syncGoal(); });
  $("goal-purpose").addEventListener("change", (e) => { goal.purpose = e.target.value; syncGoal(); });
  document.querySelectorAll("#goal [data-h]").forEach((b) => b.addEventListener("click", () => { goal.horizon = b.dataset.h; syncGoal(); }));
  syncGoal();

  // ---------- K4 ----------
  // Avgifter: bara trading_fee + withdrawal_fee. Slippage ligger redan i försäljningspriset, bankens FX-avgift hör inte till K4.
  const k4 = (S.k4 || []).map((r) => ({
    ...r,
    vinst: r.forsaljningspris_sek - r.omkostnad_sek - (r.trading_fee_sek || 0) - (r.withdrawal_fee_sek || 0)
  }));
  const gains = k4.filter((r) => r.vinst >= 0).reduce((a, r) => a + r.vinst, 0);
  const losses = Math.abs(k4.filter((r) => r.vinst < 0).reduce((a, r) => a + r.vinst, 0));
  $("k4").innerHTML = `
    <h2>K4 · deklaration</h2>
    ${!k4.length ? '<p class="notice-body">Inga försäljningar ännu, så det finns inget att deklarera.</p>' : `
    <p class="notice-body">Vinster ${kr(gains)}, förluster ${kr(losses)}. 70 % av förlusten är avdragsgill: ${kr(losses * 0.7)}.</p>
    <details><summary>Siffrorna</summary><div class="table-wrap"><table class="k4-table num">
      <thead><tr><th>Köpt</th><th>Såld</th><th>Antal</th><th>Försäljningspris</th><th>Omkostnad</th><th>Trading fee</th><th>Withdrawal fee</th><th>Vinst/förlust</th><th>Typ</th></tr></thead>
      <tbody>${k4.map((r) => `<tr><td>${esc(r.kopdatum)}</td><td>${esc(r.saljdatum)}</td><td>${esc(r.antal)}</td><td>${kr(r.forsaljningspris_sek)}</td><td>${kr(r.omkostnad_sek)}</td><td>${kr(r.trading_fee_sek || 0)}</td><td>${kr(r.withdrawal_fee_sek || 0)}</td><td class="${r.vinst < 0 ? "down" : "up"}">${kr(r.vinst)}</td><td>${esc(r.typ || "")}</td></tr>`).join("")}</tbody>
    </table></div></details>`}
    <p class="sub">Omkostnad räknas FIFO inklusive köp-courtage. Vinster och förluster står på separata rader.</p>`;

  // ---------- Inställningar (sparas bara i den här webbläsaren) ----------
  const SETTING_KEYS = ["startCapital", "tradingFeePct", "withdrawalFeeSek"];
  $("settings").innerHTML = `
    <section class="card glass settings-card">
      <h2>Inställningar</h2>
      <form id="settings-form" class="settings-form">
        <label class="field"><span>Startkapital (kr)</span>
          <input class="input num" type="number" name="startCapital" min="1" step="1" placeholder="${esc(pf.start)} (från state.json)">
          <small class="sub">Används för upplåsningen och grafens startlinje. Tomt = värdet i state.json.</small>
        </label>
        <label class="field"><span>Trading fee vid försäljning (%)</span>
          <input class="input num" type="number" name="tradingFeePct" min="0" max="10" step="0.01" placeholder="från din börs prislista">
        </label>
        <label class="field"><span>Withdrawal fee per uttag (kr)</span>
          <input class="input num" type="number" name="withdrawalFeeSek" min="0" step="1" placeholder="från din börs prislista">
        </label>
        <p class="sub">Sparas bara i den här webbläsaren. API-nycklar läggs aldrig in här.</p>
        <div class="dialog-actions">
          <a class="btn" href="#">Tillbaka</a>
          <button type="submit" class="btn btn-primary">Spara</button>
        </div>
      </form>
    </section>`;
  const sf = $("settings-form");
  SETTING_KEYS.forEach((k) => { if (Number.isFinite(settings[k])) sf.elements[k].value = settings[k]; });
  sf.addEventListener("submit", (e) => {
    e.preventDefault();
    const next = {};
    SETTING_KEYS.forEach((k) => {
      const raw = sf.elements[k].value.trim();
      if (raw !== "" && Number.isFinite(+raw) && +raw >= 0) next[k] = +raw;
    });
    store.set("walter.settings", next);
    location.hash = "";
    location.reload();
  });

  const route = () => {
    const onSettings = location.hash === "#installningar";
    $("settings").hidden = !onSettings;
    document.querySelector(".grid").hidden = onSettings;
  };
  window.addEventListener("hashchange", route);
  route();

  // ---------- PAPER / LIVE ----------
  // PAPER är standard. LIVE kräver "JA GÅ LIVE" och gäller bara den här fliken (sessionStorage).
  const LIVE_PHRASE = "JA GÅ LIVE";
  let live = store.get("walter.live", false, sessionStorage) === true;
  const dlg = $("live-dialog"), confirmInput = $("live-confirm"), okBtn = $("live-ok");
  const renderLive = () => {
    $("btn-paper").setAttribute("aria-pressed", String(!live));
    $("btn-live").setAttribute("aria-pressed", String(live));
    document.body.classList.toggle("is-live", live);
    $("footer").textContent = (live
      ? "LIVE · riktiga pengar · WALTER lägger inga order själv"
      : "Paper trading · inga riktiga pengar") + ` · data per ${day(S.updatedAt)}`;
  };
  $("btn-paper").addEventListener("click", () => { live = false; store.set("walter.live", false, sessionStorage); renderLive(); });
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
      store.set("walter.live", true, sessionStorage);
    }
    renderLive();
  });
  renderLive();
})();
