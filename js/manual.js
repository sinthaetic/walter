// Min egen handel: en egen låtsaskassa i bitcoin bredvid Walter (bara i webbläsaren: walter.manual / walter.user.manual).
// Köp och sälj till Walters pris och avgift. Walters söndagskoll rör den aldrig.
// Släpande stopp: allt säljs när priset fallit STOP (10 %) från högsta priset sedan köpet. checkStop går igenom
// Walters dagspriser (market.js log) sedan förra kollen, så att stoppet gäller även de dagar sidan var stängd.
// Inga beroenden; ritas av js/app.js.
(function (root) {
  "use strict";

  const STOP = 0.10;
  const r2 = (v) => Math.round(v * 100) / 100;

  // walter = Walters läge när kassan startades ({value, gain}), för jämförelsen "Walter samma tid"
  function create(startSek, date, walter) {
    return { startSek, cash: startSek, units: 0, costSek: 0, peakPx: null, checked: date, since: date, walter, trades: [] };
  }

  function buy(pot, sek, px, fee, date) {
    if (!(sek >= 1) || sek > pot.cash + 0.005 || !(px > 0)) return false;
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

  // rows = [{date, px}] äldst först. Returnerar raden där stoppet slog till, annars null.
  function checkStop(pot, rows, fee) {
    for (const r of rows) {
      if (!(r.date > pot.checked) || !(r.px > 0)) continue;
      pot.checked = r.date;
      if (!pot.units) continue;
      pot.peakPx = Math.max(pot.peakPx || 0, r.px);
      if (r.px <= pot.peakPx * (1 - STOP)) { sell(pot, Infinity, r.px, fee, r.date, "stopp"); return r; }
    }
    return null;
  }

  const value = (pot, px) => pot.cash + pot.units * (px || 0);
  const stopPx = (pot) => (pot.units && pot.peakPx ? pot.peakPx * (1 - STOP) : null);

  root.WalterManual = { STOP, create, buy, sell, checkStop, value, stopPx };
})(typeof window !== "undefined" ? window : this);
