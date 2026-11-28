// W-Cipher – Walters oscillator. Egen kod, skriven från öppna formler
// (LazyBears WaveTrend, RSI, Stoch RSI, EMA). Inspirerad av VuManChu Cipher A/B,
// ingen kod kopierad. Samma parametrar finns i tradingview/w-cipher.pine.
(function (root) {
  "use strict";

  // Walters parametrar (docs/ROADMAP.md, steg 5).
  const PARAMS = {
    chan: 9, avg: 12, ma: 3,          // vågen (WaveTrend), källa hlc3
    zone: 60, deep: 75,               // starka zoner ±60, djup zon −75 (guldsignal)
    divTop: 45, divBottom: -65,       // divergenser räknas bara ovan/under dessa
    mfiLen: 60, mfiMult: 150, mfiY: 2.5,
    rsiLen: 14, rsiLow: 30,
    stochLen: 14, stochK: 3, stochD: 3,
    ribbon: [5, 11, 15, 18, 21, 24, 28, 34],
    warmup: 60                        // första staplarna är osäkra, visas inte
  };

  function ema(xs, n) {
    const k = 2 / (n + 1), out = new Array(xs.length);
    for (let i = 0; i < xs.length; i++) out[i] = i === 0 ? xs[0] : xs[i] * k + out[i - 1] * (1 - k);
    return out;
  }
  function sma(xs, n) {
    const out = new Array(xs.length); let s = 0;
    for (let i = 0; i < xs.length; i++) {
      s += xs[i]; if (i >= n) s -= xs[i - n];
      out[i] = s / Math.min(i + 1, n);
    }
    return out;
  }
  function rma(xs, n) {
    const out = new Array(xs.length);
    for (let i = 0; i < xs.length; i++) out[i] = i === 0 ? xs[0] : (out[i - 1] * (n - 1) + xs[i]) / n;
    return out;
  }
  function rsi(c, n) {
    const up = [0], dn = [0];
    for (let i = 1; i < c.length; i++) { const d = c[i] - c[i - 1]; up.push(Math.max(d, 0)); dn.push(Math.max(-d, 0)); }
    const u = rma(up, n), d = rma(dn, n);
    return u.map((x, i) => (d[i] === 0 ? 100 : 100 - 100 / (1 + x / d[i])));
  }
  function stoch(xs, n) {
    return xs.map((x, i) => {
      let lo = Infinity, hi = -Infinity;
      for (let j = Math.max(0, i - n + 1); j <= i; j++) { lo = Math.min(lo, xs[j]); hi = Math.max(hi, xs[j]); }
      return hi === lo ? 50 : ((x - lo) / (hi - lo)) * 100;
    });
  }
  const crossUp = (a, b, i) => a[i - 1] < b[i - 1] && a[i] >= b[i];
  const crossDown = (a, b, i) => a[i - 1] > b[i - 1] && a[i] <= b[i];

  // Signalerna, med namn och förklaring för en vanlig människa.
  const KINDS = {
    kop:        { side: "buy",  big: true,  name: "Köpsignal",              text: "Vågen vänder upp från botten (under −60)." },
    salj:       { side: "sell", big: true,  name: "Säljsignal",             text: "Vågen vänder ned från toppen (över +60)." },
    guld:       { side: "buy",  big: true,  name: "Guldsignal",             text: "Vänder upp från djup botten (−75) och RSI under 30. Ovanlig." },
    liten_upp:  { side: "buy",  big: false, name: "Liten vändning uppåt",   text: "Mitt i spannet. Säger inte så mycket." },
    liten_ned:  { side: "sell", big: false, name: "Liten vändning nedåt",   text: "Mitt i spannet. Säger inte så mycket." },
    div_upp:    { side: "buy",  big: true,  name: "Divergens uppåt",        text: "Priset gör ny botten men vågen inte. Säljarna tröttnar." },
    div_ned:    { side: "sell", big: true,  name: "Divergens nedåt",        text: "Priset gör ny topp men vågen inte. Köparna tröttnar." },
    trend_upp:  { side: "buy",  big: false, name: "Trendbandet vänder upp", text: "Korta snittet går över det långa (Cipher A)." },
    trend_ned:  { side: "sell", big: false, name: "Trendbandet vänder ned", text: "Långa snittet går över det korta (Cipher A)." },
    blod:       { side: "sell", big: true,  name: "Blodsignal",             text: "Vågen och trendbandet vänder ned samtidigt (Cipher A)." }
  };

  // bars: [{time, open, high, low, close}], äldst först.
  function compute(bars, p) {
    p = p || PARAMS;
    const n = bars.length;
    const O = bars.map(b => b.open), H = bars.map(b => b.high), L = bars.map(b => b.low), C = bars.map(b => b.close);

    // Heikin-Ashi
    const ha = new Array(n);
    for (let i = 0; i < n; i++) {
      const hc = (O[i] + H[i] + L[i] + C[i]) / 4;
      const ho = i === 0 ? (O[0] + C[0]) / 2 : (ha[i - 1].open + ha[i - 1].close) / 2;
      ha[i] = { time: bars[i].time, open: ho, close: hc, high: Math.max(H[i], ho, hc), low: Math.min(L[i], ho, hc) };
    }

    // Cipher B: vågen, pengaflöde, RSI, Stoch RSI
    const ap = bars.map((b, i) => (H[i] + L[i] + C[i]) / 3);
    const esa = ema(ap, p.chan);
    const d = ema(ap.map((a, i) => Math.abs(a - esa[i])), p.chan);
    const wt1 = ema(ap.map((a, i) => (a - esa[i]) / (0.015 * d[i] || 1)), p.avg);
    const wt2 = sma(wt1, p.ma);
    const vwap = wt1.map((v, i) => v - wt2[i]);
    const mfi = sma(bars.map((b, i) => ((C[i] - O[i]) / ((H[i] - L[i]) || 1)) * p.mfiMult), p.mfiLen).map(v => v - p.mfiY);
    const r = rsi(C, p.rsiLen);
    const k = sma(stoch(r, p.stochLen), p.stochK);
    const dd = sma(k, p.stochD);

    // Cipher A: trendband
    const ribbon = p.ribbon.map(len => ema(C, len));
    const e1 = ribbon[0], e2 = ribbon[1], e8 = ribbon[7];

    const signals = [], divergences = [];
    const add = (i, kind) => signals.push(Object.assign({ i, time: bars[i].time, kind }, KINDS[kind]));
    let lastTop = -1, lastBottom = -1;
    for (let i = Math.max(4, p.warmup); i < n; i++) {
      const up = crossUp(wt1, wt2, i), dn = crossDown(wt1, wt2, i);
      if (up) add(i, wt2[i] <= -p.deep && r[i] < p.rsiLow ? "guld" : wt2[i] <= -p.zone ? "kop" : "liten_upp");
      if (dn) add(i, wt2[i] >= p.zone ? "salj" : "liten_ned");
      if (crossUp(e2, e8, i)) add(i, "trend_upp");
      if (crossUp(e8, e2, i)) add(i, "trend_ned");
      if (dn && wt2[i] > 0 && crossDown(e1, e2, i)) add(i, "blod");

      // Fraktaler på vågen: topp/botten två staplar bakåt, så ingen titt in i framtiden.
      const f = i - 2;
      const top = wt2[i - 4] < wt2[f] && wt2[i - 3] < wt2[f] && wt2[f] > wt2[i - 1] && wt2[f] > wt2[i];
      const bottom = wt2[i - 4] > wt2[f] && wt2[i - 3] > wt2[f] && wt2[f] < wt2[i - 1] && wt2[f] < wt2[i];
      if (top) {
        if (lastTop >= 0 && wt2[f] >= p.divTop && wt2[f] < wt2[lastTop] && H[f] > H[lastTop]) {
          divergences.push({ side: "sell", from: lastTop, to: f });
          add(i, "div_ned");
        }
        lastTop = f;
      }
      if (bottom) {
        if (lastBottom >= 0 && wt2[f] <= p.divBottom && wt2[f] > wt2[lastBottom] && L[f] < L[lastBottom]) {
          divergences.push({ side: "buy", from: lastBottom, to: f });
          add(i, "div_upp");
        }
        lastBottom = f;
      }
    }

    const last = n - 1;
    const latest = {
      wt1: wt1[last], wt2: wt2[last], mfi: mfi[last], rsi: r[last], stochK: k[last],
      dir: wt1[last] >= wt2[last] ? "up" : "down",
      zone: wt2[last] <= -p.zone ? "bottom" : wt2[last] >= p.zone ? "top" : "middle",
      aboveBand: C[last] >= e8[last],
      close: C[last]
    };
    return { params: p, ha, wt1, wt2, vwap, mfi, rsi: r, stochK: k, stochD: dd, ribbon, signals, divergences, latest };
  }

  const WCipher = { PARAMS, KINDS, compute, ema, sma, rsi };
  if (typeof module !== "undefined" && module.exports) module.exports = WCipher;
  else root.WCipher = WCipher;
})(this);
