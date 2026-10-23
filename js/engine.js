// Walters trade-motor i webbläsaren. Samma matte och avrundning som fetcher/walter_paper.py
// (Python är facit, se tests/fixtures/engine-cases.json). Inga DOM-anrop.
// Handlar automatiskt för användarens paper-Walter och spelar upp missade dagar från den publika loggen.
(function (root) {
  "use strict";

  const ASSETS = ["BTC", "ETH", "GOLD"];
  const NAMES = { BTC: "bitcoin", ETH: "ethereum", GOLD: "guld" };
  const WORDS = { PARKERA: "Vilar", AVVAKTAR: "Avvaktar", NORMAL: "Köper lite", OFFENSIV: "Köper" };
  const LAMPS = 10;

  // Pythons round(): närmaste decimal på det exakta talet, lika avstånd → jämn siffra.
  function round(x, d) {
    if (!isFinite(x)) return x;
    const s = Math.abs(x), f = Math.pow(10, d), y = s * f, fl = Math.floor(y);
    let r;
    if (y - fl === 0.5 && (fl + 0.5) / f === s) r = (fl % 2 === 0 ? fl : fl + 1) / f;
    else r = Number(s.toFixed(d));
    return x < 0 ? -r : r;
  }
  // Som num() i Python: "12 000", "1 234,56", minus som "−"
  function num(v, d) {
    d = d || 0;
    const [i, frac] = Math.abs(round(v, d)).toFixed(d).split(".");
    const s = i.replace(/\B(?=(\d{3})+(?!\d))/g, " ") + (frac ? "," + frac : "");
    return (v < 0 && round(v, d) !== 0 ? "−" : "") + s;
  }
  const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
  const sum = (o) => Object.keys(o).reduce((t, k) => t + o[k], 0);
  const list = (xs) => xs.length < 2 ? xs.join("") : xs.slice(0, -1).join(", ") + " och " + xs[xs.length - 1];

  // ---------- Läge ----------
  function suggestMode(red, current, rules) {
    if (red >= rules.parkeraAtRed || (current === "PARKERA" && red > rules.wakeAtRed)) return "PARKERA";
    if (red <= rules.modes.buyAtRed) return "OFFENSIV";
    if (red <= rules.modes.buyLittleAtRed) return "NORMAL";
    return "AVVAKTAR";
  }

  // ---------- Värde ----------
  // Innehav i SEK till dagens pris. Saknas pris används senast kända värdet (som valuation i Python).
  function valuation(pf, px) {
    const pos = pf.positions || {}, hold = {};
    for (const a of ASSETS) {
      const units = (pos[a] || {}).units || 0, p = px && px[a];
      hold[a] = units && p ? round(units * p, 2) : (!units ? 0 : (pf.holdings[a] || 0));
    }
    hold.CASH = pf.holdings.CASH;
    return { hold, total: round(sum(hold), 2) };
  }
  const goldWanted = (row, g) => (row.vix != null && row.vix > g.vixAbove) || row.spxBelowMa === true;

  // ---------- Förslag ----------
  function propose(user, row, rules, exchange) {
    const current = user.mode;
    if (!row || !row.ready) {
      return { ready: false, red: row ? row.red : null, mode: current, currentMode: current, trades: [],
        valueSek: null, missing: [], plain: "Jag väntar på data för alla tio lampor innan jag gör något." };
    }
    const r = rules, pf = user.portfolio, red = row.red, level = user.level;
    const mode = suggestMode(red, current, r);
    const px = {};
    for (const a of ASSETS) px[a] = (row.px && row.px[a]) || null;
    const { hold, total } = valuation(pf, px);
    const share = { OFFENSIV: 1, NORMAL: r.modes.littleShare, AVVAKTAR: null, PARKERA: 0 }[mode];

    // Mål i SEK per tillgång. null = behåll det som finns (Avvaktar).
    const target = {};
    target.BTC = share === null ? null : r.caps.BTC * share * total;
    const ethOk = level >= 2 && (target.BTC || 0) > 0 && row.ethBtcAbove30dMa === true && red <= r.ethMaxRed;
    target.ETH = share === null ? null : (ethOk ? r.caps.ETH * share * total : 0);
    // Guld är skyddet: följer oron, inte läget, och får köpas även när Walter vilar.
    target.GOLD = level >= 3 && goldWanted(row, r.gold) ? r.caps.GOLD * total : 0;

    // Det börsen inte har kan Walter inte köpa: målet blir 0 och pengarna ligger kvar som kontanter.
    const missing = [], wantedMissing = [];
    for (const a of ASSETS) {
      if (!exchange.assets || exchange.assets[a] !== true) {
        missing.push(a);
        if (target[a] > 0) wantedMissing.push(a);
        target[a] = 0;
      }
    }

    const fee = (exchange.takerPct + exchange.slippagePct + (exchange.quote !== "SEK" ? exchange.fxPct : 0)) / 100;
    const minTrade = r.paper.minTradePct / 100 * total;
    let cashFree = hold.CASH - r.minCash * total;
    const trades = [], waiting = [];
    for (const a of ASSETS) { // sälj först, så att kontanterna finns till köpen
      if (target[a] !== null && target[a] < hold[a] - minTrade) {
        if (px[a] === null) { waiting.push(a); continue; }
        const units = target[a] === 0 ? pf.positions[a].units : (hold[a] - target[a]) / px[a];
        const gross = units * px[a];
        trades.push({ asset: a, side: "sälj", units, priceSek: px[a], sek: gross, feeSek: gross * fee });
        cashFree += gross * (1 - fee);
      }
    }
    for (const a of ASSETS) {
      if (target[a] !== null && target[a] > hold[a] + minTrade) {
        if (px[a] === null) { waiting.push(a); continue; }
        const sek = Math.min(target[a] - hold[a], cashFree);
        if (sek < minTrade) continue;
        trades.push({ asset: a, side: "köp", units: sek * (1 - fee) / px[a], priceSek: px[a], sek, feeSek: sek * fee });
        cashFree -= sek;
      }
    }
    for (const t of trades) {
      t.sek = round(t.sek, 2); t.feeSek = round(t.feeSek, 2); t.priceSek = round(t.priceSek, 2);
      t.units = round(t.units, 8);
    }

    const word = WORDS[mode];
    let plain = `${red} av 10 lampor är röda. `;
    if (trades.length) plain += `Jag vill ${trades.map((t) => `${t.side}a ${NAMES[t.asset]} för ${num(t.sek)} kr`).join(" och ")}.`;
    else if (mode !== current) plain += `Jag byter läge till ${word}, men handlar inget.`;
    else plain += `Jag ${word.toLowerCase()} och ändrar inget.`;
    if (mode === "PARKERA" && current === "PARKERA" && red < r.parkeraAtRed) {
      plain += ` Jag vilar kvar tills det är ${r.wakeAtRed} eller färre röda, så att jag inte hoppar fram och tillbaka.`;
    }
    if (waiting.length) plain += ` Jag väntar på pris för ${list(waiting.map((a) => NAMES[a]))}.`;
    for (const a of wantedMissing) plain += ` ${cap(NAMES[a])} finns inte på din börs, så den delen ligger kvar som kontanter.`;
    return { ready: true, red, mode, currentMode: current, trades, valueSek: round(total, 2), plain, missing };
  }

  // ---------- Genomför ----------
  // Skriver förslaget in i användarens Walter (som apply i Python, utan K4). Returnerar journalposten.
  function apply(user, prop, date) {
    const pf = user.portfolio, pos = pf.positions || (pf.positions = {});
    const facts = [];
    user.trades = user.trades || [];
    for (const t of prop.trades) {
      const a = t.asset, p = pos[a] || (pos[a] = { units: 0, costSek: 0, since: date });
      if (t.side === "köp") {
        if (!p.units) p.since = date;
        p.units += t.units;
        p.costSek += t.sek; // omkostnad inkl. avgift
        pf.holdings.CASH -= t.sek;
      } else {
        const part = Math.min(1, t.units / p.units);
        const cost = p.costSek * part; // genomsnittsmetoden
        p.units = part < 1 ? round(p.units - t.units, 8) : 0;
        p.costSek = part < 1 ? round(p.costSek - cost, 2) : 0;
        pf.holdings.CASH += t.sek - t.feeSek;
      }
      p.units = round(p.units, 8); p.costSek = round(p.costSek, 2);
      facts.push(`${cap(t.side)}: ${num(t.units, 8)} ${a} à ${num(t.priceSek)} kr = ${num(t.sek, 2)} kr, avgift ${num(t.feeSek, 2)} kr`);
      user.trades.push({ date, asset: a, side: t.side, units: t.units, priceSek: t.priceSek, sek: t.sek, feeSek: t.feeSek });
    }
    pf.holdings.CASH = round(pf.holdings.CASH, 2);
    const px = {};
    for (const t of prop.trades) px[t.asset] = t.priceSek;
    for (const a of ASSETS) {
      if (a in px) pf.holdings[a] = round(((pos[a] || {}).units || 0) * px[a], 2);
    }
    pf.value = round(sum(pf.holdings), 2);
    pf.peak = Math.max(pf.peak, pf.value);
    if (prop.trades.length && !pf.firstTrade) pf.firstTrade = date;
    const note = [...new Set(prop.trades.map((t) => t.side))].sort().join("/") || "läge";
    const hist = pf.history || (pf.history = []);
    if (hist.length && hist[hist.length - 1].date === date && !hist[hist.length - 1].flow) hist.pop();
    hist.push({ date, value: pf.value, cash: pf.holdings.CASH, note });

    user.mode = prop.mode;
    facts.push(`${prop.red}/10 röda lampor → ${WORDS[prop.mode]}`);
    facts.push(`Kontant ${num(pf.holdings.CASH)} kr av ${num(pf.value)} kr`);
    const done = prop.trades.map((t) => `${t.side === "köp" ? "köpte" : "sålde"} ${NAMES[t.asset]} för ${num(t.sek)} kr`);
    const plain = (done.length ? `Jag ${done.join(" och ")}. ` : "") +
      `${prop.red} av 10 lampor var röda, så läget är ${WORDS[prop.mode]}. ${num(pf.holdings.CASH)} kr ligger som kontanter.`;
    const entry = { date, mode: prop.mode, red: prop.red, plain, facts,
      trades: prop.trades.map((t) => ({ asset: t.asset, side: t.side, sek: t.sek })) };
    (user.journal || (user.journal = [])).unshift(entry);
    return entry;
  }

  // ---------- Nivåer ----------
  // Som app.js: marknadsvinst över insättningarna (insättningar låser aldrig upp), dagar räknas från startDate
  // till loggradens datum (aldrig webbläsarens klocka).
  function levelFor(user, row, rules, levels) {
    const pf = user.portfolio;
    const value = valuation(pf, row.px || {}).total;
    const peak = Math.max(pf.peak || 0, value);
    const dd = peak > 0 ? (peak - value) / peak * 100 : 0;
    const flows = (pf.history || []).reduce((t, h) => t + (h.flow || 0), 0);
    const deposits = flows > 0 ? flows : pf.start;
    const gain = value - deposits, pct = deposits > 0 ? gain / deposits * 100 : 0;
    const days = Math.floor((Date.parse(row.date + "T00:00:00Z") - Date.parse(user.startDate + "T00:00:00Z")) / 864e5) + 1;
    const green = LAMPS - row.red;
    const lv3 = levels && levels["3"];
    if (lv3 && gain > 0 && pct >= lv3.gainPct && dd < lv3.maxDd) return 3;
    const e = rules.unlock.early, n = rules.unlock.normal;
    const early = days >= e.days && pct >= e.gainPct && dd < e.maxDd && green >= e.minGreen;
    const normal = days >= n.days && pct >= n.gainPct && dd < n.maxDd;
    return gain > 0 && (early || normal) ? 2 : 1;
  }

  const UNLOCK_TEXT = {
    2: "nu får jag köpa ethereum också, när bitcoin går bra och högst ett fåtal lampor är röda.",
    3: "nu får jag köpa guld som skydd när oron på marknaden är hög, även när jag vilar."
  };

  // ---------- Ikapp ----------
  // Spelar upp varje loggrad efter user.lastDay i datumordning. Bara dagar som finns i loggen räknas –
  // en dag utan rad hittas aldrig på. En rad som inte är klar ger ingen affär och inget lägesbyte.
  function catchUp(user, log, rules, levels, exchange) {
    const events = [];
    const rows = (log || []).filter((r) => r && typeof r.date === "string" && (!user.lastDay || r.date > user.lastDay))
      .slice().sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
    let prev = null;
    for (const row of rows) {
      if (row.date === prev) continue;
      prev = row.date;
      user.lastDay = row.date;
      if (!row.ready) continue;
      const pf = user.portfolio;
      const v = valuation(pf, row.px || {});
      Object.assign(pf.holdings, v.hold);
      pf.value = v.total;
      pf.peak = Math.max(pf.peak || 0, pf.value);

      const lv = Math.max(user.level || 1, levelFor(user, row, rules, levels));
      if (lv > (user.level || 1)) {
        const entry = { date: row.date, mode: user.mode, red: row.red,
          plain: `Level ${lv} är upplåst: ${UNLOCK_TEXT[lv]}`,
          facts: [`Level ${user.level || 1} → ${lv}`, `Värde ${num(pf.value)} kr, toppen ${num(pf.peak)} kr`] };
        user.level = lv;
        (user.journal || (user.journal = [])).unshift(entry);
        events.push(entry);
      }

      const prop = propose(user, row, rules, exchange);
      if (prop.trades.length || prop.mode !== user.mode) {
        events.push(apply(user, prop, row.date));
      } else {
        // Ingen affär: dagens värde sparas ändå (en riktig loggdag), så att historiken stämmer.
        const hist = pf.history || (pf.history = []);
        if (hist.length && hist[hist.length - 1].date === row.date && !hist[hist.length - 1].flow) hist.pop();
        hist.push({ date: row.date, value: pf.value, cash: pf.holdings.CASH, note: "dag" });
      }
    }
    return { user, events };
  }

  // ---------- Sammanfattning ----------
  function summary(events) {
    if (!events || !events.length) return "";
    const trades = [];
    for (const e of events) for (const t of e.trades || []) trades.push(t);
    const unlocked = events.filter((e) => /^Level \d är upplåst/.test(e.plain)).map((e) => e.plain.slice(0, 7));
    let s;
    if (trades.length) {
      const what = trades.map((t) => `${t.side === "köp" ? "köpte" : "sålde"} ${NAMES[t.asset]} för ${num(t.sek)} kr`);
      s = `Medan du var borta gjorde jag ${trades.length} ${trades.length === 1 ? "affär" : "affärer"}: ${list(what)}.`;
    } else {
      s = `Medan du var borta handlade jag inget. Läget är nu ${WORDS[events[events.length - 1].mode]}.`;
    }
    if (unlocked.length) s += ` ${list(unlocked)} är upplåst.`;
    return s;
  }

  root.WalterEngine = { suggestMode, propose, apply, levelFor, catchUp, summary, round, num, WORDS, NAMES };
})(typeof window !== "undefined" ? window : this);
