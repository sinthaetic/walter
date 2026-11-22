// Min egen handel: en egen låtsaskassa i bitcoin bredvid Walter (bara i webbläsaren: walter.manual / walter.user.manual).
// Köp och sälj till Walters pris och avgift. Walters söndagskoll rör den aldrig.
// Släpande stopp: allt säljs när priset fallit STOP (10 %) från högsta priset sedan köpet. checkStop går igenom
// Walters dagspriser (market.js log) sedan förra kollen, så att stoppet gäller även de dagar sidan var stängd.
// Blankning (på låtsas, 1x): en position i taget och aldrig samtidigt som ett köp. Tjänar när priset faller, kostar
// FUNDING_DAY per dag, stängs av stoppet när priset stigit STOP från lägsta priset. Kan aldrig förlora mer än insatsen.
// Inga beroenden; ritas av js/app.js.
(function (root) {
  "use strict";

  const STOP = 0.10;
  const FUNDING_DAY = 0.0003; // 0,01 % per 8 timmar, samma som historiktestet (backtest/wcipher_run.py)
  const r2 = (v) => Math.round(v * 100) / 100;
  const r4 = (v) => Math.round(v * 1e4) / 1e4; // kurvorna: så att slutet avrundas likadant som ställningen

  // walter = Walters läge när kassan startades ({value, gain}), för jämförelsen "Walter samma tid"
  function create(startSek, date, walter) {
    return { startSek, cash: startSek, units: 0, costSek: 0, peakPx: null, checked: date, since: date, walter, trades: [] };
  }

  function buy(pot, sek, px, fee, date) {
    if (pot.short || !(sek >= 1) || sek > pot.cash + 0.005 || !(px > 0)) return false;
    const units = sek * (1 - fee) / px;
    pot.cash = r2(pot.cash - sek);
    pot.units += units;
    pot.costSek = r2(pot.costSek + sek); // omkostnad inkl. avgift (genomsnittsmetoden)
    pot.peakPx = Math.max(pot.peakPx || 0, px);
    pot.trades.push({ date, side: "köp", sek: r2(sek), units, px, feeSek: r2(sek * fee) });
    return true;
  }

  // sek = hur mycket bitcoin (i kronor, före avgift) som säljs; mer än innehavet = allt
  function sell(pot, sek, px, fee, date, why) {
    if (!(px > 0) || !(pot.units > 0) || !(sek >= 1)) return false;
    const part = Math.min(1, sek / (pot.units * px));
    const units = pot.units * part, gross = units * px, cost = pot.costSek * part;
    pot.cash = r2(pot.cash + gross * (1 - fee));
    pot.units = part >= 1 ? 0 : pot.units - units;
    pot.costSek = part >= 1 ? 0 : r2(pot.costSek - cost);
    if (!pot.units) pot.peakPx = null;
    pot.trades.push({ date, side: "sälj", sek: r2(gross), units, px, feeSek: r2(gross * fee), gainSek: r2(gross * (1 - fee) - cost), why: why || null });
    return true;
  }

  function short(pot, sek, px, fee, date) {
    if (pot.short || pot.units > 0 || !(sek >= 1) || sek > pot.cash + 0.005 || !(px > 0)) return false;
    const margin = sek * (1 - fee);
    pot.cash = r2(pot.cash - sek);
    pot.short = { sek: r2(sek), margin, units: margin / px, px, lowPx: px, since: date };
    pot.trades.push({ date, side: "blanka", sek: r2(sek), units: margin / px, px, feeSek: r2(sek * fee) });
    return true;
  }

  const days = (a, b) => (a && b ? Math.max(0, Math.round((Date.parse(b) - Date.parse(a)) / 864e5)) : 0);
  const funding = (s, date) => s.units * s.px * FUNDING_DAY * days(s.since, date);
  // Vad blankningen är värd nu: insatsen + (ingångspris − pris) − finansiering. Aldrig under noll.
  const shortValue = (pot, px, date) => {
    const s = pot.short;
    return s ? Math.max(0, s.margin + (s.px - (px || s.px)) * s.units - funding(s, date)) : 0;
  };

  function cover(pot, px, fee, date, why) {
    const s = pot.short;
    if (!s || !(px > 0)) return false;
    const before = Math.max(0, s.margin + (s.px - px) * s.units);
    const after = shortValue(pot, px, date), closeFee = Math.min(after, s.units * px * fee), back = after - closeFee;
    pot.cash = r2(pot.cash + back);
    pot.short = null;
    pot.trades.push({ date, side: "stäng", sek: r2(s.units * px), units: s.units, px,
      feeSek: r2(before - after + closeFee), gainSek: r2(back - s.sek), why: why || null });
    return true;
  }

  // Dagens pris mot stoppet (dagspriserna går genom checkStop). true = stoppet slog till.
  function checkLive(pot, px, fee, date) {
    if (!(px > 0)) return false;
    if (pot.short) {
      if (px >= pot.short.lowPx * (1 + STOP)) return cover(pot, px, fee, date, "stopp");
      pot.short.lowPx = Math.min(pot.short.lowPx, px);
    } else if (pot.units) {
      if (px <= pot.peakPx * (1 - STOP)) return sell(pot, Infinity, px, fee, date, "stopp");
      pot.peakPx = Math.max(pot.peakPx || 0, px);
    }
    return false;
  }

  // rows = [{date, px}] äldst först. Returnerar raden där stoppet slog till, annars null.
  function checkStop(pot, rows, fee) {
    for (const r of rows) {
      if (!(r.date > pot.checked) || !(r.px > 0)) continue;
      pot.checked = r.date;
      if (pot.short) {
        pot.short.lowPx = Math.min(pot.short.lowPx, r.px);
        if (r.px >= pot.short.lowPx * (1 + STOP)) { cover(pot, r.px, fee, r.date, "stopp"); return r; }
        continue;
      }
      if (!pot.units) continue;
      pot.peakPx = Math.max(pot.peakPx || 0, r.px);
      if (r.px <= pot.peakPx * (1 - STOP)) { sell(pot, Infinity, r.px, fee, r.date, "stopp"); return r; }
    }
    return null;
  }

  const value = (pot, px, date) => pot.cash + pot.units * (px || 0) + shortValue(pot, px, date);
  const stopPx = (pot) => (pot.short ? pot.short.lowPx * (1 + STOP) : pot.units && pot.peakPx ? pot.peakPx * (1 - STOP) : null);

  // ---------- Arenan: kurvor, månadsrundor, märken och kopia (rena funktioner) ----------
  const fin = (v) => typeof v === "number" && Number.isFinite(v);
  const isDay = (v) => typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v);
  const SIDES = ["köp", "sälj", "blanka", "stäng"];
  const tradeOk = (t) => !!t && isDay(t.date) && SIDES.includes(t.side) && [t.sek, t.units, t.px, t.feeSek].every(fin) &&
    (t.gainSek === undefined || fin(t.gainSek)) && (t.why === undefined || t.why === null || t.why === "stopp");
  const shortOk = (s) => s === undefined || s === null || (typeof s === "object" && [s.sek, s.margin, s.units, s.px, s.lowPx].every(fin) &&
    s.units > 0 && s.px > 0 && s.lowPx > 0 && isDay(s.since));
  function validPot(p) {
    return !!p && typeof p === "object" && !Array.isArray(p) && fin(p.startSek) && p.startSek > 0 && fin(p.cash) && p.cash >= 0 &&
      fin(p.units) && p.units >= 0 && fin(p.costSek) && (p.peakPx === null || p.peakPx === undefined || fin(p.peakPx)) &&
      isDay(p.checked) && isDay(p.since) && Array.isArray(p.trades) && p.trades.every(tradeOk) && shortOk(p.short) &&
      (p.walter === undefined || p.walter === null || (typeof p.walter === "object" && fin(p.walter.value) && fin(p.walter.gain)));
  }
  const exportText = (pot) => JSON.stringify({ walterManual: 1, pot }, null, 2);
  function parsePot(text) {
    let o;
    try { o = JSON.parse(text); } catch (e) { return null; }
    return o && o.walterManual === 1 && validPot(o.pot) ? o.pot : null;
  }

  // Din kassas värde dag för dag: dina affärer spelas upp mot dagspriserna. rows = [{date, px}] äldst först.
  function potCurve(pot, rows) {
    let cash = pot.startSek, units = 0, s = null, k = 0;
    const out = [], tr = pot.trades;
    for (const r of rows) {
      if (r.date < pot.since || !(r.px > 0)) continue;
      for (; k < tr.length && tr[k].date <= r.date; k++) {
        const t = tr[k];
        if (t.side === "köp") { cash -= t.sek; units += t.units; }
        else if (t.side === "sälj") { cash += t.sek - t.feeSek; units = Math.max(0, units - t.units); }
        else if (t.side === "blanka") { cash -= t.sek; s = { sek: t.sek, margin: t.sek - t.feeSek, units: t.units, px: t.px, since: t.date }; }
        else if (s) { cash += s.sek + (t.gainSek || 0); s = null; }
      }
      const held = s ? Math.max(0, s.margin + (s.px - r.px) * s.units - funding(s, r.date)) : 0;
      const value = cash + units * r.px + held;
      out.push({ date: r.date, pct: r4((value / pot.startSek - 1) * 100) });
    }
    return out;
  }

  // Walters avkastning från dagen "since": hans affärer och insättningar spelas upp mot dagspriserna.
  // Insättningar räknas bort, så att bara marknaden syns. rows = [{date, px: {BTC, ETH, GOLD}}].
  function walterCurve(trades, flows, rows, since) {
    const hold = {}, last = {}, out = [];
    let cash = 0, k = 0, f = 0, prev = null, index = 100;
    for (const r of rows) {
      Object.assign(last, Object.fromEntries(Object.entries(r.px || {}).filter(([, v]) => v > 0)));
      let inflow = 0;
      for (; f < flows.length && flows[f].date <= r.date; f++) { cash += flows[f].flow; inflow += flows[f].flow; }
      for (; k < trades.length && trades[k].date <= r.date; k++) {
        const t = trades[k];
        if (t.side === "köp") { cash -= t.sek; hold[t.asset] = (hold[t.asset] || 0) + t.units; }
        else { cash += t.sek - t.feeSek; hold[t.asset] = Math.max(0, (hold[t.asset] || 0) - t.units); }
      }
      const value = cash + Object.entries(hold).reduce((a, [x, u]) => a + u * (last[x] || 0), 0);
      if (r.date < since) { prev = value; continue; }
      if (!out.length) { out.push({ date: r.date, pct: 0 }); prev = value; continue; }
      if (prev > 0) index *= (value - inflow) / prev;
      prev = value;
      out.push({ date: r.date, pct: r4(index - 100) });
    }
    return out;
  }

  // En runda per kalendermånad. Bara resultatet räknas, aldrig antalet affärer. Månaden "today" pågår.
  function rounds(du, wa, trades, today) {
    const w = new Map(wa.map((p) => [p.date, p.pct])), both = du.filter((p) => w.has(p.date));
    const months = [...new Set(both.map((p) => p.date.slice(0, 7)))];
    let baseD = 100, baseW = 100;
    return months.map((month) => {
      const days = both.filter((p) => p.date.slice(0, 7) === month), end = days[days.length - 1];
      const endD = 100 + end.pct, endW = 100 + w.get(end.date);
      const d = r2((endD / baseD - 1) * 100), x = r2((endW / baseW - 1) * 100);
      baseD = endD; baseW = endW;
      return { month, du: d, walter: x, winner: d > x ? "du" : x > d ? "walter" : null, live: month === today.slice(0, 7),
        trades: trades.filter((t) => t.date.slice(0, 7) === month).length };
    });
  }

  // Märken: bara avslutade rundor låser upp. "live" = du är på väg just nu.
  function badges(list) {
    const done = list.filter((r) => !r.live), now = list.find((r) => r.live);
    let run = 0, best = 0;
    done.forEach((r) => { run = r.winner === "du" ? run + 1 : 0; best = Math.max(best, run); });
    const crash = (r) => r.winner === "du" && r.walter <= -5, still = (r) => r.winner === "du" && r.trades === 0;
    return [
      { id: "ras", name: "Slog Walter i ett ras", won: done.some(crash), live: !!now && crash(now) },
      { id: "tre", name: "Tre rundor i rad", won: best >= 3, live: false, progress: `${Math.min(3, run)} / 3` },
      { id: "still", name: "Vann utan att handla", won: done.some(still), live: !!now && still(now) }
    ];
  }

  root.WalterManual = { STOP, FUNDING_DAY, create, buy, sell, short, cover, shortValue, checkStop, checkLive, value, stopPx,
    validPot, exportText, parsePot, potCurve, walterCurve, rounds, badges };
})(typeof window !== "undefined" ? window : this);
