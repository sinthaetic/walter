// W-Cipher-sidan: kontroller, text och signaler runt grafen. Själva grafen (börser, hämtning, ritning)
// ligger i js/cipher-chart.js och delas med översikten. Uppdaterar var 15:e sekund.
(function () {
  "use strict";

  const LC = window.LightweightCharts;
  const W = window.WCipher;
  const CC = window.WalterCipherChart; // grafen: js/cipher-chart.js (delas med översikten)
  const EX = CC.EX, STABLE = CC.STABLE;
  const REFRESH_MS = 15000;
  const $ = id => document.getElementById(id);

  // ---------- Inställningar som sparas i webbläsaren ----------
  const S = Object.assign({ ex: "binance", pair: "BTC/USDT", tf: "1D", view: "walter", nums: false },
    (() => { try { return JSON.parse(localStorage.getItem("walterCipher")) || {}; } catch (e) { return {}; } })());
  const save = () => { try { localStorage.setItem("walterCipher", JSON.stringify(S)); } catch (e) {} };

  // ---------- Hjälpare ----------
  const dark = () => document.documentElement.dataset.theme === "dark";
  const intraday = () => S.tf === "15m" || S.tf === "1h" || S.tf === "4h";
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

  // ---------- Graf (js/cipher-chart.js) ----------
  let graph = null, bars = null, firstDraw = true;

  function draw() {
    if (!bars) return;
    const out = graph.setBars(bars, S.tf, firstDraw);
    firstDraw = false;
    renderSide(out.result, out.decimals);
    $("legend").innerHTML = CC.legendHTML(S.view);
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

  // ---------- Hämta ----------
  let loading = 0;
  async function load(reset) {
    const my = ++loading;
    if (reset) { firstDraw = true; setLive("HÄMTAR…", ""); }
    try {
      const b = await CC.fetchBars(S.ex, S.pair, S.tf);
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
        graph.clear();
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
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = isDark ? "#0A1216" : "#D7E0E3";
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
    S.view = b.dataset.view; save(); syncControls(); graph.setView(S.view); draw();
  });
  $("nums").addEventListener("click", () => { S.nums = !S.nums; save(); syncControls(); });
  $("theme").addEventListener("click", () => {
    const d = !dark();
    if (d) document.documentElement.dataset.theme = "dark"; else delete document.documentElement.dataset.theme;
    try { localStorage.setItem("walterDark", d ? "1" : "0"); } catch (e) {}
    syncControls(); graph.applyTheme(); draw();
  });

  // ---------- Start ----------
  // Menyn börjar alltid till vänster, som på översikten (Safari kan annars minnas en sidledsrullning)
  const navStart = () => document.querySelectorAll(".nav").forEach(n => { n.scrollLeft = 0; });
  navStart(); window.addEventListener("pageshow", navStart);
  CC.mountCopy($("wc-copy"));
  if (!LC || !W || !CC) { setLive("GRAFEN KUNDE INTE LADDAS", "err"); return; }
  graph = CC.mount($("chart"), { view: S.view }); syncControls(); load(true);
  setInterval(() => { if (!document.hidden) load(false); }, REFRESH_MS);
})();
