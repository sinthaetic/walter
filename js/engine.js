// Walters trade-motor i webbläsaren. Samma matte och avrundning som fetcher/walter_paper.py
// (Python är facit, se tests/fixtures/engine-cases.json). Inga DOM-anrop.
// Handlar automatiskt för användarens paper-Walter och spelar upp missade dagar från den publika loggen.
(function (root) {
  "use strict";

  const ASSETS = ["BTC", "ETH", "GOLD"];
  const NAMES = { BTC: "bitcoin", ETH: "ethereum", GOLD: "guld" };
  const WORDS = { PARKERA: "Vilar", AVVAKTAR: "Avvaktar", NORMAL: "Köper lite", OFFENSIV: "Köper" };
  // Autopiloten: lamporna säger hur marknaden mår, inte vad Walter gör
  const MOODS = { PARKERA: "mycket orolig", AVVAKTAR: "orolig", NORMAL: "blandad", OFFENSIV: "lugn" };
  const LAMPS = 10;

  // Pythons round(): närmaste decimal på flyttalets exakta värde, exakt lika avstånd → jämn siffra.
  // toFixed räknar på det exakta värdet men väljer uppåt vid exakt lika; därför avgörs "exakt lika"
  // från den långa decimalutvecklingen (0,015 är egentligen 0,01499… och är inget lika-fall).
  function round(x, d) {
    if (!isFinite(x)) return x;
    const s = Math.abs(x);
    const [i, frac] = s.toFixed(Math.min(100, d + 40)).split(".");
    let r;
    if (/^50*$/.test(frac.slice(d))) {
      const head = i + "." + frac.slice(0, d);
      r = Number((i + frac.slice(0, d)).slice(-1)) % 2 === 0 ? Number(head) : Number(s.toFixed(d));
    } else r = Number(s.toFixed(d));
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

  // ---------- Autopiloten ----------
  // Som propose_autopilot i Python: fasta andelar (rules.caps), koll på beslutsdagen (rules.decision.weekday,
  // loggradens svenska datum), band rules.decision.bandPp. Lamporna räknas bara för läget (väderrapporten).
  const WEEKDAYS = { "måndag": 0, "tisdag": 1, "onsdag": 2, "torsdag": 3, "fredag": 4, "lördag": 5, "söndag": 6,
    monday: 0, tuesday: 1, wednesday: 2, thursday: 3, friday: 4, saturday: 5, sunday: 6 };
  const DAY_WORDS = ["måndag", "tisdag", "onsdag", "torsdag", "fredag", "lördag", "söndag"];
  const MONTHS = ["jan", "feb", "mars", "apr", "maj", "juni", "juli", "aug", "sep", "okt", "nov", "dec"];
  const strategyOf = (rules) => (rules && rules.strategy) || "autopilot";
  const ms = (iso) => Date.parse(iso + "T00:00:00Z");
  const weekday = (iso) => (new Date(ms(iso)).getUTCDay() + 6) % 7; // måndag = 0, som Python
  function decision(rules) {
    const d = rules.decision || {};
    return { wd: WEEKDAYS[String(d.weekday == null ? "söndag" : d.weekday).toLowerCase()],
      bandPp: d.bandPp == null ? 5 : d.bandPp };
  }
  function nextCheck(iso, rules) {
    const n = ((decision(rules).wd - weekday(iso)) % 7 + 7) % 7 || 7;
    return new Date(ms(iso) + n * 864e5).toISOString().slice(0, 10);
  }
  function dayText(iso) {
    const d = new Date(ms(iso));
    return `${DAY_WORDS[weekday(iso)]} ${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`;
  }
  function weightsFor(rules, exchange, glide) {
    const caps = rules.caps || {}, w = {}, missing = [];
    const g = glide == null ? 1 : glide;
    for (const a of ASSETS) {
      w[a] = Number(caps[a] || 0) * g;
      if (!exchange.assets || exchange.assets[a] !== true) { missing.push(a); w[a] = 0; }
    }
    return { w, missing };
  }

  // ---------- Målläge (som glide_factor i Python) ----------
  // Från 24 månader före målets datum skalas andelarna med f = dagar kvar / 730,5 (0..1, 4 decimaler).
  const GLIDE_DAYS = 730.5;
  const isIso = (v) => typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v) && !isNaN(ms(v)) &&
    new Date(ms(v)).toISOString().slice(0, 10) === v;
  function glideFactor(goal, iso) {
    if (!goal || typeof goal !== "object" || !isIso(goal.date)) return 1;
    const days = Math.round((ms(goal.date) - ms(iso)) / 864e5);
    return round(Math.min(1, Math.max(0, days / GLIDE_DAYS)), 4);
  }

  // ---------- Månadssparande (som savings_plan / savings_due / savings_trades i Python) ----------
  const SAVINGS_NOTE = "månadssparande";
  function savingsPlan(s) {
    if (!s || typeof s !== "object") return null;
    const amt = s.monthlySek, d = s.day === undefined ? 25 : s.day; // saknas = 25, null = av (som Python)
    if (typeof amt !== "number" || !isFinite(amt) || amt <= 0) return null;
    if (!Number.isInteger(d) || d < 1 || d > 28) return null;
    return { each: amt, day: d };
  }
  function savingsDue(s, history, iso) {
    const plan = savingsPlan(s);
    if (!plan) return [];
    const since = isIso(s.since) ? s.since : null;
    let done = "";
    for (const h of history || []) if (h && h.note === SAVINGS_NOTE && typeof h.month === "string" && h.month > done) done = h.month;
    let y = Number((since || iso).slice(0, 4)), m = Number((since || iso).slice(5, 7));
    const ty = Number(iso.slice(0, 4)), tm = Number(iso.slice(5, 7)), out = [];
    while (y < ty || (y === ty && m <= tm)) {
      const key = `${String(y).padStart(4, "0")}-${String(m).padStart(2, "0")}`;
      const when = `${key}-${String(plan.day).padStart(2, "0")}`;
      if (when <= iso && (since === null || when >= since) && key > done) out.push(key);
      if (m === 12) { y += 1; m = 1; } else m += 1;
    }
    return out;
  }
  function savingsTrades(px, hold, total, w, rules, fee, deposit) {
    const free = Math.min(deposit, hold.CASH - rules.minCash * total);
    const minTrade = rules.paper.minTradePct / 100 * deposit;
    const gaps = {}, waiting = [];
    for (const a of ASSETS) {
      const gap = w[a] * total - hold[a];
      if (w[a] > 0 && gap > 0) { if (px[a] === null) waiting.push(a); else gaps[a] = gap; }
    }
    let g = 0;
    for (const a of ASSETS) if (a in gaps) g += gaps[a];
    if (free <= 0 || g <= 0) return { trades: [], waiting };
    const scale = Math.min(1, free / g), trades = [];
    for (const a of ASSETS) {
      if (!(a in gaps)) continue;
      const sek = gaps[a] * scale;
      if (sek < minTrade) continue;
      trades.push({ asset: a, side: "köp", units: sek * (1 - fee) / px[a], priceSek: px[a], sek, feeSek: sek * fee });
    }
    return { trades, waiting };
  }
  function savingsText(sav, past) {
    const months = sav.months.map((k) => MONTHS[Number(k.slice(5, 7)) - 1]);
    let s = `Månadssparande: ${num(sav.sek)} kr in` + (sav.months.length > 1 ? ` (${list(months)}).` : ".");
    const buys = sav.trades.map((t) => `${NAMES[t.asset]} för ${num(t.sek)} kr`);
    if (buys.length) s += ` Jag ${past ? "köpte" : "köper"} ${list(buys)}.`;
    else if (!sav.waiting.length) s += " Pengarna ligger som kontanter tills vidare.";
    if (sav.waiting.length) s += ` Jag väntar på pris för ${list(sav.waiting.map((a) => NAMES[a]))}, så den delen ligger som kontanter.`;
    return s;
  }
  // Nästa sparandedag (för översikten): i dag om något ska in, annars nästa sparandedag efter i dag. null = av.
  function nextSavings(s, history, iso) {
    const plan = savingsPlan(s);
    if (!plan) return null;
    if (savingsDue(s, history, iso).length) return iso;
    let y = Number(iso.slice(0, 4)), m = Number(iso.slice(5, 7));
    for (let i = 0; i < 3; i++) {
      const when = `${y}-${String(m).padStart(2, "0")}-${String(plan.day).padStart(2, "0")}`;
      if (when > iso && (!isIso(s.since) || when >= s.since)) return when;
      if (m === 12) { y += 1; m = 1; } else m += 1;
    }
    return null;
  }

  function rebalanceTrades(pf, px, hold, total, w, rules, fee, sellAll) {
    const band = Math.max(rules.paper.minTradePct, decision(rules).bandPp) / 100 * total;
    const minTrade = rules.paper.minTradePct / 100 * total;
    let cashFree = hold.CASH - rules.minCash * total;
    const pos = pf.positions || {}, trades = [], waiting = [];
    for (const a of ASSETS) {
      const target = w[a] * total;
      if (hold[a] > target + (sellAll && target === 0 ? 0 : band)) {
        if (px[a] === null) { waiting.push(a); continue; }
        const units = target === 0 ? pos[a].units : (hold[a] - target) / px[a];
        const gross = units * px[a];
        trades.push({ asset: a, side: "sälj", units, priceSek: px[a], sek: gross, feeSek: gross * fee });
        cashFree += gross * (1 - fee);
      }
    }
    for (const a of ASSETS) {
      const target = w[a] * total;
      if (target > hold[a] + band) {
        if (px[a] === null) { waiting.push(a); continue; }
        const sek = Math.min(target - hold[a], cashFree);
        if (sek < minTrade) continue;
        trades.push({ asset: a, side: "köp", units: sek * (1 - fee) / px[a], priceSek: px[a], sek, feeSek: sek * fee });
        cashFree -= sek;
      }
    }
    return { trades, waiting };
  }
  // Som last_check / is_due i Python: senaste kollen = nyaste journalpost med check, annars första affären.
  function lastCheck(journal, pf) {
    for (const e of journal || []) if (e && e.check) return e.date;
    return pf.firstTrade || null;
  }
  // Beslutsdag? Första affären: alltid. Annars beslutsveckodagen, eller första dagen efter en missad beslutsdag.
  function isDue(iso, rules, pf, journal) {
    if (!pf.firstTrade) return { due: true, first: true, catchUp: false };
    const wd = decision(rules).wd, lc = lastCheck(journal, pf);
    if (lc === iso) return { due: false, first: false, catchUp: false };
    if (weekday(iso) === wd) return { due: true, first: false, catchUp: false };
    const lastDd = new Date(ms(iso) - ((weekday(iso) - wd + 7) % 7) * 864e5).toISOString().slice(0, 10);
    const missed = lc === null || lc < lastDd;
    return { due: missed, first: false, catchUp: missed };
  }
  // Har raden pris för allt autopiloten ska äga? (Då räcker raden, även om alla lampor inte är klara.)
  function pricesFor(row, rules, exchange) {
    const { w } = weightsFor(rules, exchange);
    const want = ASSETS.filter((a) => w[a] > 0);
    return !!row && want.length > 0 && want.every((a) => row.px && row.px[a]);
  }
  function autopilotPlain(trades, hold, total, w, first, due, iso, rules, waiting, wantedMissing, catchUp, checkedToday) {
    const wd = decision(rules).wd;
    const nxt = `Nästa koll ${dayText(nextCheck(iso, rules))}.`;
    const todayWord = DAY_WORDS[weekday(iso)];
    const head = first ? "Första dagen" : catchUp ? `${cap(todayWord)} (${DAY_WORDS[wd]}ens koll)` : cap(todayWord);
    let s;
    if (!due) s = checkedToday ? `Dagens koll är gjord. ${nxt}` : `Jag handlar bara på ${DAY_WORDS[wd]}ar. ${nxt}`;
    else if (trades.length) {
      let parts = [];
      const fresh = [];
      for (const t of trades) {
        const a = t.asset, share = total ? round(hold[a] / total * 100, 0) : 0, pct = round(w[a] * 100, 0);
        if (t.side === "sälj") parts.push(`${NAMES[a]} har vuxit till ${share} % – jag säljer för ${num(t.sek)} kr, tillbaka till ${pct} %.`);
        else if (hold[a] <= 0 || share === 0) fresh.push(`${NAMES[a]} för ${num(t.sek)} kr (${pct} %)`);
        else parts.push(`${NAMES[a]} ligger på ${share} % – jag köper för ${num(t.sek)} kr, tillbaka till ${pct} %.`);
      }
      if (fresh.length) parts.push(`jag köper ${list(fresh)}.`);
      parts = [parts[0]].concat(parts.slice(1).map(cap));
      s = `${head}: ${parts.join(" ")} ${nxt}`;
    } else if (first) s = "Jag börjar så fort jag har priserna.";
    else if (waiting.length) {
      s = `${head}: jag väntar på pris för ${list(waiting.map((a) => NAMES[a]))}. Jag försöker igen i morgon.`;
      waiting = [];
    } else s = `${head}: allt ligger inom marginalen. Jag rör ingenting. ${nxt}`;
    if (waiting.length) s += ` Jag väntar på pris för ${list(waiting.map((a) => NAMES[a]))}.`;
    for (const a of wantedMissing) s += ` ${cap(NAMES[a])} finns inte på din börs, så den delen ligger kvar som kontanter.`;
    return s;
  }
  function proposeAutopilot(user, row, rules, exchange) {
    const r = rules, pf = user.portfolio, current = user.mode;
    // Lamporna är bara vädret: är raden inte klar står läget kvar, men autopiloten handlar på priserna.
    const red = row.ready ? row.red : null, mode = row.ready ? suggestMode(red, current, r) : current;
    const px = {};
    for (const a of ASSETS) px[a] = (row.px && row.px[a]) || null;
    // Målläget: andelarna krymper mot kontanter de sista 24 månaderna före målets datum
    const glide = glideFactor(user.goal, row.date);
    const { w, missing } = weightsFor(r, exchange, glide);
    const wanted = ASSETS.filter((a) => Number((r.caps || {})[a] || 0) > 0 && !missing.includes(a));
    if (wanted.length && wanted.every((a) => px[a] === null)) {
      return { ready: false, strategy: "autopilot", red, mode: current, currentMode: current, trades: [], valueSek: null,
        missing, waiting: [], plain: "Jag väntar på priser innan jag gör något." };
    }
    const { hold, total } = valuation(pf, px);
    const journal = user.journal || [];
    const { due, first, catchUp } = isDue(row.date, r, pf, journal);
    const fee = (exchange.takerPct + exchange.slippagePct + (exchange.quote !== "SEK" ? exchange.fxPct : 0)) / 100;
    // Månadssparandet: in som kontanter, köp direkt med bara de nya pengarna, sedan söndagens vanliga koll.
    const months = savingsDue(user.savings, pf.history, row.date);
    let sav = null, sTrades = [], hold2 = hold, total2 = total;
    if (months.length) {
      const each = savingsPlan(user.savings).each, dep = each * months.length;
      hold2 = Object.assign({}, hold, { CASH: hold.CASH + dep });
      total2 = total + dep;
      const st = savingsTrades(px, hold2, total2, w, r, fee, dep);
      sTrades = st.trades;
      for (const t of sTrades) { hold2[t.asset] += t.units * px[t.asset]; hold2.CASH -= t.sek; }
      total2 = sum(hold2);
      sav = { months, eachSek: each, sek: dep, valueBefore: round(total, 2), trades: sTrades, waiting: st.waiting };
    }
    const { trades, waiting } = due ? rebalanceTrades(pf, px, hold2, total2, w, r, fee, glide === 0) : { trades: [], waiting: [] };
    for (const t of sTrades.concat(trades)) {
      t.sek = round(t.sek, 2); t.feeSek = round(t.feeSek, 2); t.priceSek = round(t.priceSek, 2);
      t.units = round(t.units, 8);
    }
    const wantedMissing = missing.filter((a) => ((r.caps || {})[a] || 0) > 0);
    let plain = autopilotPlain(trades, hold2, total2, w, first, due, row.date, r, waiting, wantedMissing,
      catchUp, lastCheck(journal, pf) === row.date && !first);
    const plainAuto = plain;
    if (sav) plain = savingsText(sav, false) + " " + (due ? plain : `Nästa koll ${dayText(nextCheck(row.date, r))}.`);
    return { ready: true, strategy: "autopilot", red, mode, currentMode: current, trades: sTrades.concat(trades), valueSek: round(total, 2),
      plain, plainAuto, missing, waiting, decisionDay: due, check: due && !waiting.length,
      needsApproval: trades.length > 0 || !!sav || mode !== current || (due && (!catchUp || !waiting.length)), nextCheck: nextCheck(row.date, r), weights: w,
      glide, savings: sav };
  }

  // ---------- Förslag ----------
  function propose(user, row, rules, exchange) {
    // Autopiloten behöver bara priserna; lamp-strategin väntar på en klar rad (alla tio lampor).
    if (row && strategyOf(rules) === "autopilot") return proposeAutopilot(user, row, rules, exchange);
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
    return { ready: true, red, mode, currentMode: current, trades, valueSek: round(total, 2), plain, missing, waiting };
  }

  // ---------- Genomför ----------
  // Skriver förslaget in i användarens Walter (som apply i Python, utan K4). Returnerar journalposten.
  function apply(user, prop, date) {
    const pf = user.portfolio, pos = pf.positions || (pf.positions = {});
    const facts = [];
    user.trades = user.trades || [];
    const hist = pf.history || (pf.history = []);
    const sav = prop.savings || null;
    if (sav) { // månadssparandet: en historikrad med flow per månad, före affärerna
      if (hist.length && hist[hist.length - 1].date === date && !hist[hist.length - 1].flow) hist.pop();
      let cash = pf.holdings.CASH;
      sav.months.forEach((mth, i) => {
        cash = round(cash + sav.eachSek, 2);
        hist.push({ date, value: round(sav.valueBefore + sav.eachSek * (i + 1), 2), cash, flow: sav.eachSek, note: SAVINGS_NOTE, month: mth });
        facts.push(`Månadssparande ${mth}: +${num(sav.eachSek)} kr (låtsasinsättning)`);
      });
      pf.holdings.CASH = cash;
    }
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
    if (hist.length && hist[hist.length - 1].date === date && !hist[hist.length - 1].flow) hist.pop();
    hist.push({ date, value: pf.value, cash: pf.holdings.CASH, note });

    user.mode = prop.mode;
    const auto = prop.strategy === "autopilot";
    if (prop.red != null) facts.push(auto ? `Marknaden ${MOODS[prop.mode]}: ${prop.red}/10 varningar` : `${prop.red}/10 röda lampor → ${WORDS[prop.mode]}`);
    if (auto) facts.push("Autopilot: " + ASSETS.map((a) => `${a} ${round(prop.weights[a] * 100, 0)} %`).join(" · "));
    if (auto && prop.glide != null && prop.glide < 1) facts.push(`Målläge: ${round(prop.glide * 100, 0)} % av vanliga andelar`);
    facts.push(`Kontant ${num(pf.holdings.CASH)} kr av ${num(pf.value)} kr`);
    const rest = sav ? prop.trades.slice(sav.trades.length) : prop.trades;
    // "köpte bitcoin för 350 kr, ethereum för 200 kr och guld för 200 kr" – ett verb per sida
    const done = [["sälj", "sålde"], ["köp", "köpte"]].filter(([s]) => rest.some((t) => t.side === s))
      .map(([s, verb]) => verb + " " + list(rest.filter((t) => t.side === s).map((t) => `${NAMES[t.asset]} för ${num(t.sek)} kr`)));
    const waitText = (prop.waiting || []).length ? ` Jag väntar på pris för ${list(prop.waiting.map((a) => NAMES[a]))}, så den delen rör jag inte än.` : "";
    const plain = auto
      ? (sav ? savingsText(sav, true) + " " : "") +
        (done.length ? `Jag ${done.join(" och ")}. Autopiloten justerade andelarna. ` : prop.decisionDay ? `${prop.plainAuto != null ? prop.plainAuto : prop.plain} ` : "") +
        (prop.red != null ? `Marknaden är ${MOODS[prop.mode]} (${prop.red} av 10 varningar) – det ändrar inte vad jag gör. ` : "") +
        `${num(pf.holdings.CASH)} kr ligger som kontanter.` + (done.length ? waitText : "")
      : (done.length ? `Jag ${done.join(" och ")}. ` : "") +
        `${prop.red} av 10 lampor var röda, så läget är ${WORDS[prop.mode]}. ${num(pf.holdings.CASH)} kr ligger som kontanter.` + waitText;
    const entry = { date, mode: prop.mode, red: prop.red, plain, facts,
      trades: prop.trades.map((t) => ({ asset: t.asset, side: t.side, sek: t.sek })) };
    if (auto && prop.check) entry.check = true; // autopilotens koll är gjord i dag (se isDue)
    if (sav) entry.savings = { sek: sav.sek, months: sav.months.slice() };
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
    // Kontrakt: varje insättning (även startbeloppet och påfyllningar) är en historikrad med `flow`.
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
    // En rad per datum (en klar rad vinner över en halvfärdig), bara efter lastDay och från startDate.
    const byDate = {};
    for (const r of log || []) {
      if (!r || typeof r.date !== "string") continue;
      if (user.lastDay && r.date <= user.lastDay) continue;
      if (user.startDate && r.date < user.startDate) continue;
      if (!byDate[r.date] || (r.ready && !byDate[r.date].ready)) byDate[r.date] = r;
    }
    // Loggens nyaste dag kan fortfarande bli klar (hämtaren skriver om dagens rad), så en halvfärdig
    // nyaste rad flyttar aldrig lastDay – då spelas dagen upp när den väl är klar.
    const newest = (log || []).reduce((m, r) => (r && typeof r.date === "string" && r.date > m ? r.date : m), "");
    for (const date of Object.keys(byDate).sort()) {
      const row = byDate[date];
      // Autopiloten handlar på priserna: en rad med pris för allt den ska äga räcker, även om lamporna inte är klara.
      const auto = strategyOf(rules) === "autopilot";
      if (!row.ready && !(auto && pricesFor(row, rules, exchange))) {
        if (row.date < newest) user.lastDay = row.date;
        continue;
      }
      user.lastDay = row.date;
      const pf = user.portfolio;
      const v = valuation(pf, row.px || {});
      Object.assign(pf.holdings, v.hold);
      pf.value = v.total;
      pf.peak = Math.max(pf.peak || 0, pf.value);

      // Autopiloten har inga Levels: allt köps från dag 1, så ingen upplåsning räknas.
      const lv = auto ? (user.level || 1) : Math.max(user.level || 1, levelFor(user, row, rules, levels));
      if (lv > (user.level || 1)) {
        const entry = { date: row.date, mode: user.mode, red: row.red,
          plain: `Level ${lv} är upplåst: ${UNLOCK_TEXT[lv]}`,
          facts: [`Level ${user.level || 1} → ${lv}`, `Värde ${num(pf.value)} kr, toppen ${num(pf.peak)} kr`] };
        user.level = lv;
        (user.journal || (user.journal = [])).unshift(entry);
        events.push(entry);
      }

      const prop = propose(user, row, rules, exchange);
      if (prop.trades.length || prop.mode !== user.mode || (auto && prop.needsApproval)) {
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
    const saved = events.reduce((t, e) => t + ((e.savings && e.savings.sek) || 0), 0);
    if (saved > 0) s += ` Månadssparandet satte in ${num(saved)} kr (låtsaspengar).`;
    return s;
  }

  root.WalterEngine = { suggestMode, propose, apply, levelFor, catchUp, summary, round, num, WORDS, MOODS, NAMES,
    strategyOf, nextCheck, dayText, glideFactor, savingsPlan, savingsDue, nextSavings, SAVINGS_NOTE };
})(typeof window !== "undefined" ? window : this);
