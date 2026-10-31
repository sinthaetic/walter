// W-Cipher-grafen som modul: samma ritning på cipher.html (js/cipher-app.js) och på översikten (js/app.js).
// Hämtar ljus från börsens öppna flöde, räknar W-Cipher (js/wcipher.js) och ritar med Lightweight Charts.
// Färgerna läses från CSS-variablerna (css/cipher-chart.css), så ljust/mörkt följer sidan.
//
// API – window.WalterCipherChart:
//   EX, STABLE                         börserna (symbolformat, tidsramar, adress, tolkning) och stabila valutor
//   fetchBars(exId, pair, tf)          -> Promise<[{time, open, high, low, close}]>  (tf: 15m 1h 4h 1D 1W)
//   loadChartLib()                     -> Promise: laddar Lightweight Charts utan att blockera sidan (om det inte redan finns)
//   decimals(v)                        antal decimaler för ett pris
//   mount(el, opts) -> handle          ritar i el. opts: {view: "walter"|"cipher", wavePane: 0.4 (andel av höjden),
//                                      pulsePane: 64 (px för WALTERS LAMPOR), wheel: true (mushjulet zoomar/flyttar grafen;
//                                      false = hjulet rullar sidan). Lodrät fingerdragning rullar alltid sidan.}
//     handle.setBars(bars, tf, reset)  ritar; reset = visa de senaste ~120 staplarna. -> {result, decimals} | null
//     handle.setView(view)             "walter" eller "cipher" (ritar inte; anropa redraw)
//     handle.setExtras({pulse, trades}) Walters lampor [[datum, röda]] (bara DAG/VECKA) och affärer från tradeMarks()
//     handle.applyTheme()              efter byte ljust/mörkt (ritar inte om; anropa setView/redraw)
//     handle.redraw(), handle.clear(), handle.chart
//     handle.onDestroy(fn), handle.destroy()   städning (observers, timers) + tar bort grafen
//   legendHTML(view, extras)           <li>-rader till förklaringen (class="wc-legend")
//   Rena hjälpare (testas i tests/js/cipher-chart.test.js):
//   mergePulse(pulse, log)             -> [[datum, röda]] sorterad; market.js-loggens rader vinner (nyare dagar)
//   tradeMarks(journal)                -> [{date, side: "buy"|"sell"|"check"}] äldst först
//   alignTime(date, bars, tf)          -> stapelns time för ett svenskt datum, eller null
//   pulseBars(pulse, bars, tf, from)   -> [{time, value: 5 − röda}] för staplarna från index from
//   mountCopy(el)                      knappen "Kopiera till TradingView" med tre steg (tradingview/*.pine)
(function () {
  "use strict";

  // ---------- Börser ----------
  // Varje börs: symbolformat, tidsramar (null = finns inte), adress och tolkning till {time, open, high, low, close}.
  const EX = {
    binance: {
      quote: "USDT", sym: (b, q) => b + q,
      tf: { "15m": "15m", "1h": "1h", "4h": "4h", "1D": "1d", "1W": "1w" },
      url: (s, t) => `https://api.binance.com/api/v3/klines?symbol=${s}&interval=${t}&limit=1000`,
      parse: j => {
        if (!Array.isArray(j)) throw new Error(j.msg || "okänt svar");
        return j.map(k => ({ time: k[0] / 1000, open: +k[1], high: +k[2], low: +k[3], close: +k[4] }));
      }
    },
    coinbase: {
      quote: "USD", sym: (b, q) => b + "-" + q,
      tf: { "15m": 900, "1h": 3600, "4h": null, "1D": 86400, "1W": null },
      url: (s, t) => `https://api.exchange.coinbase.com/products/${s}/candles?granularity=${t}`,
      parse: j => {
        if (!Array.isArray(j)) throw new Error(j.message || "okänt svar");
        return j.map(k => ({ time: k[0], low: +k[1], high: +k[2], open: +k[3], close: +k[4] })).reverse();
      }
    },
    kraken: {
      quote: "USD", sym: (b, q) => b + q,
      tf: { "15m": 15, "1h": 60, "4h": 240, "1D": 1440, "1W": 10080 },
      url: (s, t) => `https://api.kraken.com/0/public/OHLC?pair=${s}&interval=${t}`,
      parse: j => {
        if (j.error && j.error.length) throw new Error(j.error.join(", "));
        const key = Object.keys(j.result).find(k => k !== "last");
        return j.result[key].map(k => ({ time: k[0], open: +k[1], high: +k[2], low: +k[3], close: +k[4] }));
      }
    },
    bybit: {
      quote: "USDT", sym: (b, q) => b + q,
      tf: { "15m": "15", "1h": "60", "4h": "240", "1D": "D", "1W": "W" },
      url: (s, t) => `https://api.bybit.com/v5/market/kline?category=spot&symbol=${s}&interval=${t}&limit=1000`,
      parse: j => {
        if (j.retCode !== 0) throw new Error(j.retMsg || "okänt svar");
        return j.result.list.map(k => ({ time: k[0] / 1000, open: +k[1], high: +k[2], low: +k[3], close: +k[4] })).reverse();
      }
    },
    okx: {
      quote: "USDT", sym: (b, q) => b + "-" + q,
      tf: { "15m": "15m", "1h": "1H", "4h": "4H", "1D": "1Dutc", "1W": "1Wutc" },
      url: (s, t) => `https://www.okx.com/api/v5/market/candles?instId=${s}&bar=${t}&limit=300`,
      parse: j => {
        if (j.code !== "0") throw new Error(j.msg || "okänt svar");
        return j.data.map(k => ({ time: k[0] / 1000, open: +k[1], high: +k[2], low: +k[3], close: +k[4] })).reverse();
      }
    }
  };
  const STABLE = ["USDT", "USDC"];

  async function fetchBars(exId, pair, tf) {
    const ex = EX[exId];
    const [base, quote] = pair.split("/");
    const t = ex.tf[tf];
    if (t == null) throw new Error("tidsramen finns inte på den här börsen");
    const res = await fetch(ex.url(ex.sym(base, quote), t));
    let j;
    try { j = await res.json(); } catch (e) { throw new Error("börsen svarade " + res.status); }
    const bars = ex.parse(j).filter(b => isFinite(b.close));
    if (bars.length < 80) throw new Error("för lite historik (" + bars.length + " ljus)");
    return bars;
  }

  // Lightweight Charts utan blockerande skripttagg (översikten). Samma version och integrity som cipher.html.
  const LC_SRC = "https://unpkg.com/lightweight-charts@5.0.0/dist/lightweight-charts.standalone.production.js";
  const LC_SRI = "sha384-/z0wnnyAhUnLX5YRrxljPlJlhJPGIOuhRU9kt785gf9AUeh8YsG8O6oxSE2sTS9m";
  let lcPromise = null;
  function loadChartLib() {
    if (window.LightweightCharts) return Promise.resolve(window.LightweightCharts);
    if (!lcPromise) {
      lcPromise = new Promise((resolve, reject) => {
        const sc = document.createElement("script");
        sc.src = LC_SRC; sc.integrity = LC_SRI; sc.crossOrigin = "anonymous"; sc.async = true;
        sc.onload = () => (window.LightweightCharts ? resolve(window.LightweightCharts) : reject(new Error("ingen graf")));
        sc.onerror = () => { lcPromise = null; reject(new Error("grafen kunde inte laddas")); };
        document.head.appendChild(sc);
      });
    }
    return lcPromise;
  }

  function decimals(v) { return v >= 1000 ? 0 : v >= 10 ? 2 : v >= 1 ? 3 : v >= 0.01 ? 5 : 8; }
  // Tidsaxeln: korta svenska datum utan punkt ("3 sep", "okt", "2026"), så att fler ryms och inget kapas till "uli"
  const MON = ["jan", "feb", "mar", "apr", "maj", "jun", "jul", "aug", "sep", "okt", "nov", "dec"];
  const two = n => String(n).padStart(2, "0");
  function tickMark(t, type) {
    const d = new Date((typeof t === "number" ? t : 0) * 1000);
    if (type === 0) return String(d.getUTCFullYear());
    if (type === 1) return MON[d.getUTCMonth()];
    if (type === 2) return d.getUTCDate() + " " + MON[d.getUTCMonth()];
    return two(d.getUTCHours()) + ":" + two(d.getUTCMinutes());
  }
  const isIntraday = tf => tf === "15m" || tf === "1h" || tf === "4h";
  const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  // ---------- Rena hjälpare: Walters lampor och affärer ----------
  const DAY = 86400;
  const utcDay = iso => Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10)) / 1000;
  const isoOf = t => new Date(t * 1000).toISOString().slice(0, 10);

  // Historiken (data/pulse.js) + market.js-loggen. Loggen är nyare och vinner samma dag; rader utan röda hoppas över.
  function mergePulse(pulse, log) {
    const m = new Map();
    (pulse || []).forEach(r => { if (r && Number.isFinite(r[1])) m.set(String(r[0]).slice(0, 10), r[1]); });
    (log || []).forEach(r => { if (r && r.date && r.ready !== false && Number.isFinite(r.red)) m.set(String(r.date).slice(0, 10), r.red); });
    return [...m.entries()].sort((a, b) => (a[0] < b[0] ? -1 : a[0] > b[0] ? 1 : 0));
  }

  // Journalposter med affärer -> markörer. Appens poster har trades [{side}], Pythons har faktarader ("Köp: …", "Sälj: …").
  // En autopilot-koll utan affär (check: true) blir en liten markör.
  function tradeMarks(journal) {
    const out = [], seen = new Set();
    const add = (date, side) => { const k = date + side; if (!seen.has(k)) { seen.add(k); out.push({ date, side }); } };
    (journal || []).forEach(e => {
      if (!e || !e.date) return;
      const date = String(e.date).slice(0, 10);
      let sides = [];
      if (Array.isArray(e.trades) && e.trades.length) {
        sides = e.trades.map(t => (t.side === "köp" ? "buy" : t.side === "sälj" ? "sell" : null));
      } else {
        sides = (e.facts || []).map(f => (/^\s*köp(t)?\s*:/i.test(f) ? "buy" : /^\s*(sälj|sålt|såld)\s*:/i.test(f) ? "sell" : null));
      }
      sides = sides.filter(Boolean);
      if (sides.length) sides.forEach(s => add(date, s));
      else if (e.check) add(date, "check");
    });
    return out.sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
  }

  // Ett datum till en stapel: DAG = samma dag, 4 TIM (och kortare) = dagens första stapel, VECKA = veckan som innehåller dagen.
  function alignTime(date, bars, tf) {
    if (!bars || !bars.length) return null;
    const t0 = utcDay(date);
    if (tf === "1W") {
      for (let i = bars.length - 1; i >= 0; i--) {
        if (bars[i].time <= t0) return t0 - bars[i].time < 7 * DAY ? bars[i].time : null;
      }
      return null;
    }
    for (const b of bars) {
      if (b.time >= t0 + DAY) return null;
      if (b.time >= t0) return b.time;
    }
    return null;
  }

  // Lamporna som stapelvärden: 5 − röda (över noll = lugnt, under = oro). VECKA: veckans sista dag.
  // Senaste värdet högst 4 dagar gammalt, annars ingen punkt (gammal data räknas aldrig som färsk).
  function pulseBars(pulse, bars, tf, from) {
    const out = [];
    if (!pulse || !pulse.length || !bars) return out;
    const dates = pulse.map(r => r[0]);
    let j = -1;
    for (let i = from || 0; i < bars.length; i++) {
      const key = isoOf(bars[i].time + (tf === "1W" ? 6 * DAY : 0));
      while (j + 1 < dates.length && dates[j + 1] <= key) j++;
      if (j < 0) continue;
      if ((utcDay(key) - utcDay(dates[j])) / DAY > 4) continue;
      out.push({ time: bars[i].time, value: 5 - pulse[j][1] });
    }
    return out;
  }

  // ---------- Grafen ----------
  function mount(el, opts) {
    const LC = window.LightweightCharts, W = window.WCipher;
    const o = Object.assign({ view: "walter", wavePane: 0.4, pulsePane: 64, wheel: true }, opts);
    let view = o.view, tf = "1D", bars = null, firstDraw = true, extras = { pulse: null, trades: null };
    let chart, candles, ribbon = [], wt1S, wt2S, vwapS, mfiS, kS, dS, candleMarks, waveMarks, divSeries = [], zoneLines = [];
    let pulseS = null, pulseLine = null, allMarks = [], marksQueued = false;
    // Tiden för stapeln en etikettbredd in från vänsterkanten: allt till vänster om den skulle kapas av kanten
    function leftEdgeTime(px) {
      if (!bars || !chart) return -Infinity;
      const ts = chart.timeScale(), r = ts.getVisibleLogicalRange();
      if (!r) return -Infinity;
      const n = Math.ceil((px || 22) / Math.max(1, ts.options().barSpacing));
      const i = W.PARAMS.warmup + Math.max(0, Math.ceil(r.from)) + n;
      return bars[Math.min(i, bars.length - 1)].time;
    }
    const fixed = () => ({ priceRange: { minValue: -100, maxValue: 100 } });
    const fixedPulse = () => ({ priceRange: { minValue: -5, maxValue: 5 } });

    chart = LC.createChart(el, {
      autoSize: true,
      layout: { background: { type: "solid", color: "transparent" }, fontFamily: "JetBrains Mono, monospace", fontSize: 11, attributionLogo: false,
        panes: { enableResize: false } },
      grid: { vertLines: { visible: false }, horzLines: { visible: true } },
      rightPriceScale: { borderVisible: false },
      // Korta datum, tätare (max 6 tecken), och ingen etikett som kapas i vänsterkanten ("uli")
      timeScale: { borderVisible: false, rightOffset: 4, tickMarkMaxCharacterLength: 6,
        tickMarkFormatter: (t, type) => (typeof t === "number" && t < leftEdgeTime() ? "" : tickMark(t, type)) },
      // Ingen scrollfälla: lodrät fingerdragning rullar sidan, och mushjulet bara när o.wheel (cipher.html på dator)
      handleScroll: { mouseWheel: o.wheel, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
      handleScale: { mouseWheel: o.wheel, pinch: true, axisPressedMouseMove: true, axisDoubleClickReset: true },
      crosshair: { mode: 0 },
      localization: { locale: "sv-SE" }
    });
    ribbon = W.PARAMS.ribbon.map(() => chart.addSeries(LC.LineSeries, { lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false }, 0));
    candles = chart.addSeries(LC.CandlestickSeries, { priceLineVisible: true }, 0);
    const osc = { priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, autoscaleInfoProvider: fixed,
      priceFormat: { type: "price", precision: 0, minMove: 1 } };
    mfiS = chart.addSeries(LC.BaselineSeries, Object.assign({ baseValue: { type: "price", price: 0 }, lineWidth: 1 }, osc), 1);
    wt1S = chart.addSeries(LC.BaselineSeries, Object.assign({ baseValue: { type: "price", price: 0 }, lineWidth: 1 }, osc), 1);
    vwapS = chart.addSeries(LC.BaselineSeries, Object.assign({ baseValue: { type: "price", price: 0 }, lineWidth: 1 }, osc), 1);
    wt2S = chart.addSeries(LC.LineSeries, Object.assign({ lineWidth: 1 }, osc), 1);
    kS = chart.addSeries(LC.LineSeries, Object.assign({ lineWidth: 1 }, osc), 1);
    dS = chart.addSeries(LC.LineSeries, Object.assign({ lineWidth: 1 }, osc), 1);
    candleMarks = LC.createSeriesMarkers(candles, []);
    waveMarks = LC.createSeriesMarkers(wt2S, []);
    zoneLines = [60, 0, -60].map(p => wt2S.createPriceLine({ price: p, lineWidth: 1, lineStyle: p ? 2 : 0, axisLabelVisible: true, title: "" }));
    // Rutornas höjder. setHeight räknar om de andra rutorna utifrån höjderna vid senaste ritningen, så två anrop i
    // samma bildruta påverkar varandra (vågen kunde tryckas ihop till några pixlar). Därför en ruta per bildruta,
    // några varv, tills höjderna stämmer.
    let sizing = 0;
    const sizePanes = () => {
      if (!el.clientHeight) return; // dold ruta: görs när den syns
      const my = ++sizing, want = [null, Math.round(el.clientHeight * o.wavePane), o.pulsePane];
      let n = 0;
      const step = () => {
        if (my !== sizing || !el.clientHeight) return;
        const panes = chart.panes(), i = 1 + (n % 2);
        if (panes[i] && Math.abs(panes[i].getHeight() - want[i]) > 2) panes[i].setHeight(want[i]);
        if (pulseS) placeLabel(); // rubriken WALTERS LAMPOR följer med rutan
        if (++n < 8) requestAnimationFrame(() => requestAnimationFrame(step));
      };
      step();
    };
    sizePanes();

    function applyTheme() {
      const muted = css("--muted"), line = css("--line");
      chart.applyOptions({
        layout: { textColor: muted, panes: { separatorColor: line, separatorHoverColor: line } },
        grid: { horzLines: { color: line } },
        crosshair: { vertLine: { color: muted, labelBackgroundColor: css("--seg-bg") }, horzLine: { color: muted, labelBackgroundColor: css("--seg-bg") } }
      });
      zoneLines.forEach((l, i) => l.applyOptions({ color: i === 1 ? line : muted }));
      if (pulseLine) pulseLine.applyOptions({ color: line });
    }

    // WALTERS LAMPOR: egen liten ruta under vågen, samma stil som pengaflödet. Bara dagsdata (DAG/VECKA).
    function drawPulse(from) {
      const pts = extras.pulse && !isIntraday(tf) ? pulseBars(extras.pulse, bars, tf, from) : [];
      if (!pts.length) {
        if (pulseS) { chart.removeSeries(pulseS); pulseS = null; pulseLine = null; }
        placeLabel();
        return;
      }
      if (!pulseS) {
        pulseS = chart.addSeries(LC.BaselineSeries, { baseValue: { type: "price", price: 0 }, lineWidth: 1, priceLineVisible: false,
          lastValueVisible: false, crosshairMarkerVisible: false, autoscaleInfoProvider: fixedPulse,
          priceFormat: { type: "price", precision: 0, minMove: 1 } }, 2);
        pulseLine = pulseS.createPriceLine({ price: 0, lineWidth: 1, lineStyle: 0, axisLabelVisible: false, title: "", color: css("--line") });
        sizePanes();
      }
      const up = css("--c-mfi-up"), down = css("--c-mfi-down");
      pulseS.applyOptions({ topFillColor1: up, topFillColor2: up, topLineColor: css("--green"),
        bottomFillColor1: down, bottomFillColor2: down, bottomLineColor: css("--red") });
      pulseS.setData(pts);
      requestAnimationFrame(placeLabel);
    }

    // Rubriken WALTERS LAMPOR överst i lamprutan (Lightweight Charts har inga rubriker i rutorna)
    let pulseLabel = null;
    function placeLabel() {
      const pane = pulseS && chart.panes()[2];
      let pe = null;
      try { pe = pane && pane.getHTMLElement && pane.getHTMLElement(); } catch (e) { pe = null; } // rutan inte ritad än
      if (!pe) { if (pulseLabel) pulseLabel.hidden = true; return; }
      if (!pulseLabel) {
        pulseLabel = document.createElement("span");
        pulseLabel.className = "wc-pane-label";
        pulseLabel.textContent = "WALTERS LAMPOR";
        if (getComputedStyle(el).position === "static") el.style.position = "relative";
        el.appendChild(pulseLabel);
      }
      pulseLabel.hidden = false;
      pulseLabel.style.top = Math.round(pe.getBoundingClientRect().top - el.getBoundingClientRect().top + 4) + "px";
    }
    // Monterad medan rutan var dold (annan flik, höjd 0): ge rutorna rätt höjd och rita om när den syns.
    let wasHidden = el.clientHeight === 0;
    const ro = window.ResizeObserver ? new ResizeObserver(() => {
      if (wasHidden && el.clientHeight > 0) {
        wasHidden = false;
        // efter grafens egen storleksändring (den lyssnar också på rutan)
        requestAnimationFrame(() => { sizePanes(); firstDraw = true; draw(); });
      }
      else if (el.clientHeight === 0) wasHidden = true;
      // Grafens egen storlek sätts asynkront (autoSize): rutornas höjder sätts om när den är känd, annars kan vågen
      // tryckas ihop till några pixlar
      else requestAnimationFrame(sizePanes);
      if (pulseS) requestAnimationFrame(placeLabel);
    }) : null;
    if (ro) ro.observe(el);
    const cleanups = [];

    function draw() {
      if (!bars) return null;
      const cipher = view === "cipher";
      const r = W.compute(bars);
      const from = W.PARAMS.warmup;
      const green = css("--green"), red = css("--red"), gold = css("--gold"), teal = css("--teal"), muted = css("--muted"), ink = css("--ink");
      const d = decimals(bars[bars.length - 1].close);
      const pf = { type: "price", precision: d, minMove: Math.pow(10, -d) };

      candles.applyOptions(cipher
        ? { upColor: green, downColor: red, wickUpColor: green, wickDownColor: red, borderVisible: false, priceFormat: pf }
        : { upColor: css("--c-up"), downColor: "rgba(0,0,0,0)", borderVisible: true, borderUpColor: css("--c-up"), borderDownColor: css("--c-down"),
            wickUpColor: css("--c-up"), wickDownColor: css("--c-down"), priceFormat: pf });
      candles.setData(r.ha.slice(from));

      const longIdx = W.PARAMS.ribbon.length - 1;
      ribbon.forEach((s, k) => {
        s.applyOptions({ priceFormat: pf, visible: cipher || k === 0 || k === longIdx });
        s.setData(r.ribbon[k].slice(from).map((v, j) => {
          const i = j + from;
          const up = r.ribbon[1][i] >= r.ribbon[longIdx][i];
          return { time: bars[i].time, value: v, color: cipher ? (up ? css("--c-mfi-up") : css("--c-mfi-down")) : css("--c-band") };
        }));
      });

      const series = (arr) => arr.slice(from).map((v, j) => ({ time: bars[j + from].time, value: v }));
      mfiS.applyOptions(cipher
        ? { topFillColor1: css("--c-mfi-up"), topFillColor2: css("--c-mfi-up"), topLineColor: "rgba(0,0,0,0)",
            bottomFillColor1: css("--c-mfi-down"), bottomFillColor2: css("--c-mfi-down"), bottomLineColor: "rgba(0,0,0,0)" }
        : { topFillColor1: css("--c-mfi"), topFillColor2: css("--c-mfi"), topLineColor: "rgba(0,0,0,0)",
            bottomFillColor1: css("--c-mfi"), bottomFillColor2: css("--c-mfi"), bottomLineColor: "rgba(0,0,0,0)" });
      mfiS.setData(series(r.mfi));
      const w1 = cipher ? css("--c-wt1") : css("--c-wave");
      wt1S.applyOptions({ topFillColor1: w1, topFillColor2: w1, bottomFillColor1: w1, bottomFillColor2: w1,
        topLineColor: cipher ? w1 : teal, bottomLineColor: cipher ? w1 : teal });
      wt1S.setData(series(r.wt1));
      const vw = css("--c-vwap");
      vwapS.applyOptions({ visible: cipher, topFillColor1: vw, topFillColor2: vw, bottomFillColor1: vw, bottomFillColor2: vw, topLineColor: vw, bottomLineColor: vw });
      vwapS.setData(series(r.vwap));
      wt2S.applyOptions({ color: cipher ? css("--c-wt2") : ink, lineWidth: cipher ? 2 : 1 });
      wt2S.setData(series(r.wt2));
      kS.applyOptions({ visible: cipher, color: css("--c-k") }); kS.setData(series(r.stochK));
      dS.applyOptions({ visible: cipher, color: css("--c-d") }); dS.setData(series(r.stochD));

      // Divergenslinjer på vågen (bara Cipher-läget)
      divSeries.forEach(s => chart.removeSeries(s)); divSeries = [];
      if (cipher) {
        r.divergences.slice(-12).forEach(dv => {
          const s = chart.addSeries(LC.LineSeries, { color: dv.side === "buy" ? green : red, lineWidth: 2, priceLineVisible: false,
            lastValueVisible: false, crosshairMarkerVisible: false, autoscaleInfoProvider: fixed }, 1);
          s.setData([{ time: bars[dv.from].time, value: r.wt2[dv.from] }, { time: bars[dv.to].time, value: r.wt2[dv.to] }]);
          divSeries.push(s);
        });
      }

      // Markörer
      const colorOf = s => s.kind === "guld" ? gold : s.side === "buy" ? green : red;
      const shown = r.signals.filter(s => cipher || s.kind === "kop" || s.kind === "salj" || s.kind === "guld");
      waveMarks.setMarkers(shown.filter(s => !s.kind.startsWith("trend") && s.kind !== "blod" && !s.kind.startsWith("div")).map(s => ({
        time: s.time, position: "inBar", shape: "circle", color: s.big ? colorOf(s) : muted, size: s.big ? 1.4 : 0.5
      })));
      const priceMarks = [];
      shown.forEach(s => {
        if (s.kind === "kop" || s.kind === "guld") priceMarks.push({ time: s.time, position: "belowBar", shape: "arrowUp", color: colorOf(s), text: cipher ? (s.kind === "guld" ? "GULD" : "KÖP") : "" });
        else if (s.kind === "salj") priceMarks.push({ time: s.time, position: "aboveBar", shape: "arrowDown", color: red, text: cipher ? "SÄLJ" : "" });
        else if (s.kind === "blod") priceMarks.push({ time: s.time, position: "aboveBar", shape: "square", color: red, text: "BLOD" });
        else if (s.kind === "trend_upp") priceMarks.push({ time: s.time, position: "belowBar", shape: "circle", color: green, size: 0.6 });
        else if (s.kind === "trend_ned") priceMarks.push({ time: s.time, position: "aboveBar", shape: "circle", color: red, size: 0.6 });
        else if (s.kind === "div_upp") priceMarks.push({ time: s.time, position: "belowBar", shape: "circle", color: green, text: "DIV" });
        else if (s.kind === "div_ned") priceMarks.push({ time: s.time, position: "aboveBar", shape: "circle", color: red, text: "DIV" });
      });
      // Walters egna affärer: samma pilar som köp/sälj, men i Walters teal och med W
      if (extras.trades && extras.trades.length) {
        const visible = bars.slice(from);
        extras.trades.forEach(t => {
          const time = alignTime(t.date, visible, tf);
          if (time == null) return;
          if (t.side === "buy") priceMarks.push({ time, position: "belowBar", shape: "arrowUp", color: teal, text: "W KÖPTE" });
          else if (t.side === "sell") priceMarks.push({ time, position: "aboveBar", shape: "arrowDown", color: teal, text: "W SÅLDE" });
          else priceMarks.push({ time, position: "belowBar", shape: "circle", color: teal, size: 0.5 });
        });
      }
      priceMarks.sort((a, b) => a.time - b.time);
      // Etiketter som krockar: samma text på samma sida inom 3 staplar visas en gång (formen står kvar)
      const idx = new Map(bars.map((b, i) => [b.time, i]));
      const lastAt = {};
      priceMarks.forEach(m => {
        if (!m.text) return;
        const k = m.position + m.text, i = idx.get(m.time);
        if (lastAt[k] != null && i - lastAt[k] <= 3) m.text = "";
        else lastAt[k] = i;
      });
      allMarks = priceMarks;
      applyMarks();

      drawPulse(from);

      chart.applyOptions({ timeScale: { timeVisible: isIntraday(tf) } });
      if (firstDraw) { chart.timeScale().setVisibleLogicalRange({ from: bars.length - from - 120, to: bars.length - from + 4 }); firstDraw = false; }
      return { result: r, decimals: d };
    }

    // Etiketter längst till vänster i bild kapas av grafens kant ("ÖP"): där visas bara pilen, utan text.
    function applyMarks() {
      marksQueued = false;
      if (!bars) { candleMarks.setMarkers([]); return; }
      const cut = leftEdgeTime(26);
      candleMarks.setMarkers(allMarks.map(m => (m.text && m.time < cut ? Object.assign({}, m, { text: "" }) : m)));
    }
    chart.timeScale().subscribeVisibleLogicalRangeChange(() => {
      if (!marksQueued && allMarks.length) { marksQueued = true; requestAnimationFrame(applyMarks); }
    });

    applyTheme();
    return {
      chart,
      setBars(b, t, reset) {
        bars = b; if (t) tf = t; if (reset) { firstDraw = true; requestAnimationFrame(sizePanes); }
        return draw();
      },
      setView(v) { view = v; },
      setExtras(x) { extras = Object.assign({ pulse: null, trades: null }, x); return draw(); },
      applyTheme,
      redraw: draw,
      reset() { firstDraw = true; },
      clear() {
        bars = null;
        chart.panes().forEach(p => p.getSeries().forEach(s => s.setData([])));
      },
      onDestroy(fn) { cleanups.push(fn); },
      destroy() {
        cleanups.splice(0).forEach(fn => { try { fn(); } catch (e) { /* städning */ } });
        if (ro) ro.disconnect();
        if (pulseLabel) pulseLabel.remove();
        chart.remove();
      }
    };
  }

  function legendHTML(view, extras) {
    const items = view === "cipher"
      ? [["sw", "--c-wt1", "Vågen"], ["sw", "--c-wt2", "Vågens snitt"], ["sw", "--c-vwap", "VWAP"], ["sw", "--c-mfi-up", "Pengar in"], ["sw", "--c-mfi-down", "Pengar ut"],
         ["sw", "--c-k", "Stoch RSI"], ["dt", "--green", "Köp"], ["dt", "--red", "Sälj"], ["dt", "--gold", "Guld"]]
      : [["sw", "--c-band", "Trendband"], ["sw", "--c-wave", "Vågen"], ["sw", "--c-mfi", "Pengaflöde"], ["dt", "--green", "Köpsignal"], ["dt", "--red", "Säljsignal"], ["dt", "--gold", "Guldsignal"]];
    if (extras && extras.trades) items.push(["dt", "--teal", "W = Walters affär"]);
    if (extras && extras.pulse) items.push(["sw", "--c-mfi-up", "Lamporna lugna"], ["sw", "--c-mfi-down", "Lamporna oroliga"]);
    return items.map(([k, v, t]) => `<li><span class="${k}" style="background:var(${v})"></span>${t}</li>`).join("")
      + `<li><span class="sw" style="border-top:1px dashed var(--muted);height:0"></span>Starka zoner ±60</li>`;
  }

  // ---------- Kopiera till TradingView ----------
  const PINE = { "W-Cipher B": "tradingview/w-cipher.pine", "W-Cipher A": "tradingview/w-cipher-a.pine" };
  const BACKTEST_URL = "https://github.com/sinthaetic/walter/blob/main/docs/BACKTEST.md";

  async function copyText(text) {
    try {
      if (navigator.clipboard && window.isSecureContext) { await navigator.clipboard.writeText(text); return true; }
    } catch (e) { /* faller tillbaka */ }
    const ta = document.createElement("textarea");
    ta.value = text; ta.setAttribute("readonly", ""); ta.style.cssText = "position:fixed;top:0;left:0;opacity:0;font-size:16px"; // 16 px: ingen zoom i Safari
    document.body.appendChild(ta); ta.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch (e) { ok = false; }
    ta.remove();
    return ok;
  }

  function mountCopy(el) {
    el.classList.add("wc-copy");
    el.innerHTML = `
      <div class="wc-copy-row">
        <button type="button" class="wc-copy-btn" data-pine="W-Cipher B">KOPIERA TILL TRADINGVIEW</button>
        <button type="button" class="wc-copy-alt" data-pine="W-Cipher A">ELLER W-CIPHER A</button>
        <span class="wc-copy-msg" role="status" aria-live="polite"></span>
      </div>
      <ol class="wc-steps" hidden>
        <li>Öppna TradingView → Pine Editor.</li>
        <li>Klistra in.</li>
        <li>Add to chart.</li>
      </ol>
      <p class="wc-honest">W-Cipher är en indikator att läsa marknaden med. I Walters historiktest tjänade signalerna inte pengar som regler – se <a href="${BACKTEST_URL}" target="_blank" rel="noopener">BACKTEST</a>.</p>`;
    const msg = el.querySelector(".wc-copy-msg"), steps = el.querySelector(".wc-steps");
    // Skripten hämtas vid första klicket. Safari kräver att kopieringen startar i klicket: då skrivs en
    // ClipboardItem med ett löfte om texten, annars väntar vi på texten och kopierar (med textarea som reserv).
    const texts = {};
    const get = name => texts[name] || (texts[name] = fetch(PINE[name], { cache: "no-cache" })
      .then(r => { if (!r.ok) throw new Error(String(r.status)); return r.text(); })
      .catch(err => { delete texts[name]; throw err; }));
    el.addEventListener("click", async (e) => {
      const b = e.target.closest("button[data-pine]");
      if (!b) return;
      const name = b.dataset.pine;
      const text = get(name);
      let ok = false;
      try {
        if (window.ClipboardItem && navigator.clipboard && navigator.clipboard.write && window.isSecureContext) {
          await navigator.clipboard.write([new ClipboardItem({ "text/plain": text.then(t => new Blob([t], { type: "text/plain" })) })]);
          ok = true;
        }
      } catch (err) { ok = false; }
      if (!ok) {
        try { ok = await copyText(await text); } catch (err) { ok = false; }
      }
      steps.hidden = !ok;
      if (ok) msg.textContent = "Kopierat: " + name;
      else msg.innerHTML = `Kunde inte kopiera. <a href="${PINE[name]}" target="_blank" rel="noopener">Öppna ${name}</a> och kopiera själv.`;
    });
  }

  window.WalterCipherChart = { EX, STABLE, fetchBars, loadChartLib, decimals, mount, legendHTML, mergePulse, tradeMarks, alignTime, pulseBars, mountCopy };
})();
