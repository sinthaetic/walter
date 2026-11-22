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

  root.WalterManual = { STOP, FUNDING_DAY, create, buy, sell, short, cover, shortValue, checkStop, checkLive, value, stopPx };
})(typeof window !== "undefined" ? window : this);
