// W-Cipher-sidan: hämtar ljus direkt från börsens öppna flöde, räknar W-Cipher
// (js/wcipher.js) och ritar med TradingView Lightweight Charts. Uppdaterar var 15:e sekund.
(function () {
  "use strict";

  const LC = window.LightweightCharts;
  const W = window.WCipher;
  const REFRESH_MS = 15000;
  const $ = id => document.getElementById(id);

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

  // ---------- Inställningar som sparas i webbläsaren ----------
  const S = Object.assign({ ex: "binance", pair: "BTC/USDT", tf: "1D", view: "walter", nums: false },
    (() => { try { return JSON.parse(localStorage.getItem("walterCipher")) || {}; } catch (e) { return {}; } })());
  const save = () => { try { localStorage.setItem("walterCipher", JSON.stringify(S)); } catch (e) {} };

  // ---------- Hjälpare ----------
  const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const dark = () => document.documentElement.dataset.theme === "dark";
  const intraday = () => S.tf === "15m" || S.tf === "1h" || S.tf === "4h";
  function decimals(v) { return v >= 1000 ? 0 : v >= 10 ? 2 : v >= 1 ? 3 : v >= 0.01 ? 5 : 8; }
  function fmt(v, d) {
    return v.toLocaleString("sv-SE", { minimumFractionDigits: d, maximumFractionDigits: d }).replace("-", "−");
  }
  function when(t) {
    const d = new Date(t * 1000);
    const opt = intraday()
      ? { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }
      : { day: "numeric", month: "short", year: S.tf === "1W" ? "2-digit" : undefined };
    return d.toLocaleString("sv-SE", opt).replace(".", "");
  }
  function quoteSign(pair) {
    const q = pair.split("/")[1];
    return q === "USD" || STABLE.includes(q) ? "$" : "";
  }

  // ---------- Graf ----------
  let chart, candles, ribbon = [], wt1S, wt2S, vwapS, mfiS, kS, dS, candleMarks, waveMarks, divSeries = [], zoneLines = [];
  const fixed = () => ({ priceRange: { minValue: -100, maxValue: 100 } });

  function buildChart() {
    chart = LC.createChart($("chart"), {
      autoSize: true,
      layout: { background: { type: "solid", color: "transparent" }, fontFamily: "JetBrains Mono, monospace", fontSize: 10, attributionLogo: false,
        panes: { enableResize: false } },
      grid: { vertLines: { visible: false }, horzLines: { visible: true } },
      rightPriceScale: { borderVisible: false },
      timeScale: { borderVisible: false, rightOffset: 4 },
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
    const panes = chart.panes();
    if (panes[1]) panes[1].setHeight(Math.round($("chart").clientHeight * 0.4));
  }

  function applyTheme() {
    const muted = css("--muted"), line = css("--line");
    chart.applyOptions({
      layout: { textColor: muted, panes: { separatorColor: line, separatorHoverColor: line } },
      grid: { horzLines: { color: line } },
      crosshair: { vertLine: { color: muted, labelBackgroundColor: css("--seg-bg") }, horzLine: { color: muted, labelBackgroundColor: css("--seg-bg") } }
    });
    zoneLines.forEach((l, i) => l.applyOptions({ color: i === 1 ? line : muted }));
  }

  // ---------- Rita ----------
  let bars = null, result = null, firstDraw = true;

  function draw() {
    if (!bars) return;
    const cipher = S.view === "cipher";
    const r = result = W.compute(bars);
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
    priceMarks.sort((a, b) => a.time - b.time);
    candleMarks.setMarkers(priceMarks);

    chart.applyOptions({ timeScale: { timeVisible: intraday() } });
    if (firstDraw) { chart.timeScale().setVisibleLogicalRange({ from: bars.length - from - 120, to: bars.length - from + 4 }); firstDraw = false; }

    renderSide(r, d);
    renderLegend(cipher);
  }

  // ---------- Text till höger ----------
  function walterMode() {
    const st = window.WALTER_STATE;
    if (!st || !st.mode) return null;
    return st.mode === "PARKERA" ? "VILAR" : String(st.mode).toUpperCase();
  }

  function renderSide(r, d) {
    const L = r.latest;
    const last = bars[bars.length - 1];
    $("price").textContent = S.pair + "  " + quoteSign(S.pair) + fmt(last.close, d);
    $("oscNow").textContent = "VÅG " + fmt(L.wt1, 1) + " · SNITT " + fmt(L.wt2, 1) + " · FLÖDE " + fmt(L.mfi, 1) + " · RSI " + fmt(L.rsi, 0);

    // Cipher säger: senaste stora signal inom 3 staplar, annars vågens riktning.
    const fresh = r.signals.filter(s => s.big && s.i >= bars.length - 3).pop();
    const cs = $("cipherSays");
    const csDot = cs.querySelector(".dot"), csTxt = cs.querySelector("span");
    if (fresh) {
      csTxt.textContent = fresh.name.toUpperCase();
      csDot.className = "dot " + (fresh.kind === "guld" ? "gold" : fresh.side);
    } else {
      csTxt.textContent = L.dir === "up" ? "INGEN SIGNAL · UPPÅT" : "INGEN SIGNAL · NEDÅT";
      csDot.className = "dot";
    }

    const wm = walterMode();
    $("walterSays").textContent = wm || "VÄNTAR PÅ DATA";
    const resting = wm === "VILAR";
    let hy;
    if (fresh && fresh.side === "buy" && resting) hy = "Walter vilar, men ciphern visar " + fresh.name.toLowerCase() + ". Vill du gå in gör du det på egen hand, vid sidan av Walters plan.";
    else if (fresh && fresh.side === "sell") hy = "Ciphern visar " + fresh.name.toLowerCase() + ". Har du köpt på egen hand kan det vara läge att se över det.";
    else if (fresh) hy = "Ciphern visar " + fresh.name.toLowerCase() + ". Walters läge ändras bara av lamporna och journalen.";
    else hy = resting ? "Båda är lugna. Walter vilar och ciphern har ingen stark signal just nu." : "Ciphern har ingen stark signal just nu.";
    $("hybrid").textContent = hy;

    const zone = { bottom: "i botten", top: "på toppen", middle: "i mitten" }[L.zone];
    const dir = L.dir === "up" ? "uppåt" : "nedåt";
    $("readHead").textContent = "Vågen pekar " + dir;
    $("readDot").className = "dot " + (L.zone === "bottom" && L.dir === "up" ? "buy" : L.zone === "top" && L.dir === "down" ? "sell" : "wait");
    const lastBig = r.signals.filter(s => s.big).pop();
    $("readText").textContent = "Vågen ligger " + zone + " och pekar " + dir + ". Priset ligger " + (L.aboveBand ? "över" : "under") + " sitt trendband. "
      + (L.zone === "middle" ? "Inget starkt tecken just nu, så Walter väntar. "
        : L.zone === "bottom" ? "Det kan vara tidigt i en vändning uppåt, men det är ett tecken, inte ett köpbeslut. "
        : "Det har gått fort uppåt. Walter köper inte i toppen. ")
      + (lastBig ? "Senaste starka signal: " + lastBig.name.toLowerCase() + " " + when(lastBig.time) + "." : "");

    const P = W.PARAMS;
    const rows = [
      ["Vågen (WaveTrend)", P.chan + " · " + P.avg + " · " + P.ma + ", hlc3"],
      ["Starka zoner", "±" + P.zone + ", guld under −" + P.deep],
      ["Pengaflöde (MFI)", P.mfiLen + " · ×" + P.mfiMult],
      ["Trendband (EMA)", P.ribbon[0] + "–" + P.ribbon[P.ribbon.length - 1] + ", 8 linjer"],
      ["Divergenser", "vanliga, +" + P.divTop + " / " + P.divBottom],
      ["Stoch RSI", P.stochLen + " · " + P.stochK + " · " + P.stochD],
      ["Våg nu", fmt(L.wt1, 1) + " / " + fmt(L.wt2, 1)],
      ["RSI nu", fmt(L.rsi, 1)]
    ];
    $("readNums").innerHTML = rows.map(([a, b]) => `<div><dt>${a}</dt><dd>${b}</dd></div>`).join("");

    const cipher = S.view === "cipher";
    const list = r.signals.filter(s => cipher || s.big).slice(-12).reverse();
    $("signals").innerHTML = list.length
      ? list.map(s => `<li><i class="dot ${s.big ? (s.kind === "guld" ? "gold" : s.side) : "small"}"></i>
          <span class="txt"><span class="nm">${s.name}</span><span class="ex">${s.text}</span></span>
          <span class="when">${when(s.time)}</span></li>`).join("")
      : `<li class="empty">Inga starka signaler i den här perioden.</li>`;
  }

  function renderLegend(cipher) {
    const items = cipher
      ? [["sw", "--c-wt1", "Vågen"], ["sw", "--c-wt2", "Vågens snitt"], ["sw", "--c-vwap", "VWAP"], ["sw", "--c-mfi-up", "Pengar in"], ["sw", "--c-mfi-down", "Pengar ut"],
         ["sw", "--c-k", "Stoch RSI"], ["dt", "--green", "Köp"], ["dt", "--red", "Sälj"], ["dt", "--gold", "Guld"]]
      : [["sw", "--c-band", "Trendband"], ["sw", "--c-wave", "Vågen"], ["sw", "--c-mfi", "Pengaflöde"], ["dt", "--green", "Köpsignal"], ["dt", "--red", "Säljsignal"], ["dt", "--gold", "Guldsignal"]];
    $("legend").innerHTML = items.map(([k, v, t]) => `<li><span class="${k}" style="background:var(${v})"></span>${t}</li>`).join("")
      + `<li><span class="sw" style="border-top:1px dashed var(--muted);height:0"></span>Starka zoner ±60</li>`;
  }

  // ---------- Hämta ----------
  let loading = 0;
  async function load(reset) {
    const my = ++loading;
    if (reset) { firstDraw = true; setLive("HÄMTAR…", ""); }
    try {
      const b = await fetchBars(S.ex, S.pair, S.tf);
      if (my !== loading) return;
      bars = b; draw();
      const t = new Date().toLocaleTimeString("sv-SE");
      setLive("LIVE · " + $("ex").selectedOptions[0].text.toUpperCase() + " · " + t, "on");
      $("status").textContent = "";
    } catch (e) {
      if (my !== loading) return;
      setLive("KUNDE INTE HÄMTA", "err");
      $("status").textContent = S.pair + ": " + e.message;
      if (reset) {
        bars = null; $("price").textContent = S.pair + "  –";
        chart.panes().forEach(p => p.getSeries().forEach(s => s.setData([])));
      }
    }
  }
  function setLive(text, cls) { $("liveText").textContent = text; $("live").className = "live " + cls; }

  // ---------- Kontroller ----------
  function syncControls() {
    $("ex").value = S.ex; $("pair").value = S.pair;
    document.querySelectorAll("#tf button").forEach(b => {
      b.setAttribute("aria-pressed", String(b.dataset.tf === S.tf));
      b.disabled = EX[S.ex].tf[b.dataset.tf] == null;
      b.title = b.disabled ? "Finns inte på den här börsen" : "";
    });
    document.querySelectorAll("#view button").forEach(b => b.setAttribute("aria-pressed", String(b.dataset.view === S.view)));
    $("nums").setAttribute("aria-pressed", String(S.nums));
    $("readHuman").hidden = S.nums; $("readNums").hidden = !S.nums;
    $("readTitle").textContent = S.nums ? "WALTERS INSTÄLLNINGAR" : "WALTER LÄSER GRAFEN";
    const isDark = dark();
    $("theme").setAttribute("aria-label", isDark ? "Byt till ljust läge" : "Byt till mörkt läge");
  }
  function normPair(v) {
    const p = v.trim().toUpperCase().replace(/[-_ ]/, "/");
    return /^[A-Z0-9]{2,10}\/[A-Z0-9]{2,10}$/.test(p) ? p : null;
  }

  $("ex").addEventListener("change", e => {
    S.ex = e.target.value;
    // Byt USD/USDT så att paret finns på börsen.
    const [b, q] = S.pair.split("/"), want = EX[S.ex].quote;
    if ((q === "USD" && want === "USDT") || (STABLE.includes(q) && want === "USD")) S.pair = b + "/" + want;
    if (EX[S.ex].tf[S.tf] == null) S.tf = "1D";
    save(); syncControls(); load(true);
  });
  $("controls").addEventListener("submit", e => { e.preventDefault(); $("pair").blur(); });
  $("pair").addEventListener("change", e => {
    const p = normPair(e.target.value);
    if (!p) { $("status").textContent = "Skriv paret som BTC/USDT"; return; }
    S.pair = p; save(); syncControls(); load(true);
  });
  $("tf").addEventListener("click", e => {
    const b = e.target.closest("button"); if (!b || b.disabled) return;
    S.tf = b.dataset.tf; save(); syncControls(); load(true);
  });
  $("view").addEventListener("click", e => {
    const b = e.target.closest("button"); if (!b) return;
    S.view = b.dataset.view; save(); syncControls(); draw();
  });
  $("nums").addEventListener("click", () => { S.nums = !S.nums; save(); syncControls(); });
  $("theme").addEventListener("click", () => {
    const d = !dark();
    if (d) document.documentElement.dataset.theme = "dark"; else delete document.documentElement.dataset.theme;
    try { localStorage.setItem("walterDark", d ? "1" : "0"); } catch (e) {}
    syncControls(); applyTheme(); draw();
  });

  // ---------- Start ----------
  if (!LC || !W) { setLive("GRAFEN KUNDE INTE LADDAS", "err"); return; }
  buildChart(); applyTheme(); syncControls(); load(true);
  setInterval(() => { if (!document.hidden) load(false); }, REFRESH_MS);
})();
