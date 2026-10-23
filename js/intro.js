// Introt (steg 9): efter GÅ IN möter en ny besökare Walter (tre korta rutor), väljer summa och börs och får sin egen Walter.
// boot.js anropar WalterIntro.start(onDone). Introt skapar och sparar användaren, döljer sig och ger tillbaka användaren.
// Temat är appens (data-theme på <html>, localStorage "walterDark"), glaset är landningens (css/landing.css).
(function () {
  "use strict";

  const MIN = 100, MAX = 100000000;
  const CARDS = [
    "Jag är Walter. Jag läser marknaden varje dag – tio signaler, alltid samma regler.",
    "Jag förvaltar åt dig: köper när läget är bra, vilar när det stormar. Aldrig mer än 75 % investerat.",
    "Jag rör inga riktiga pengar. Det kan jag inte än. Vi börjar med låtsaspengar, tills du är redo."
  ];
  const NO_STORAGE = "Din webbläsare låter mig inte spara. Allt försvinner när du stänger fliken.";
  const COUNTRY = { AT: "Österrike", IE: "Irland", LU: "Luxemburg", MT: "Malta", SE: "Sverige" };

  // Bara siffror, mellanslag och "kr". Allt annat (komma, e, minus, ord) ger null.
  function parseAmount(text) {
    if (typeof text !== "string") return null;
    const m = /^[\s ]*(\d[\d\s ]*?)[\s ]*(?:kr)?[\s ]*$/i.exec(text);
    if (!m) return null;
    const n = Number(m[1].replace(/[\s ]/g, ""));
    return Number.isFinite(n) && n >= MIN && n <= MAX ? n : null;
  }
  // Börsens två rader i listan: tillståndslandet och avgiften
  function exMeta(x) {
    const c = x && x.licence ? x.licence.country : "";
    return [`Tillstånd: ${COUNTRY[c] || c}`, `Avgift ${x.takerPct.toLocaleString("sv-SE", { maximumFractionDigits: 2 })} %`];
  }
  if (typeof document === "undefined") { window.WalterIntro = { parseAmount, exMeta }; return; }

  const reduce = () => window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const isDark = () => document.documentElement.dataset.theme === "dark";
  const appParts = () => document.querySelectorAll("body > header, body > main, body > footer");
  const sv = (n, max) => n.toLocaleString("sv-SE", { maximumFractionDigits: max });
  const NB = " ";

  function el(tag, cls, text) {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  }

  let root = null, onDone = null, step = 0, amount = null, exchangeId = null;

  function syncTheme() {
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = isDark() ? "#0A1216" : "#D7E0E3";
    const label = isDark() ? "Byt till ljust läge" : "Byt till mörkt läge";
    const b = root && root.querySelector(".l-theme");
    if (b) b.setAttribute("aria-label", label);
    const app = document.getElementById("theme");
    if (app) app.setAttribute("aria-label", label);
  }

  function dots() {
    const box = root.querySelector(".steps");
    box.textContent = "";
    for (let i = 0; i < 5; i++) box.appendChild(el("i", i === step ? "on" : ""));
    box.setAttribute("aria-label", `Steg ${step + 1} av 5`);
  }

  function heading(text) {
    const h = el("h2", "i-head", text);
    h.tabIndex = -1;
    return h;
  }
  function button(text, cls, fn) {
    const b = el("button", cls, text);
    b.type = "button";
    b.onclick = fn;
    return b;
  }

  function render() {
    const body = root.querySelector(".i-body");
    body.textContent = "";
    dots();
    if (step < 3) {
      const h = heading(CARDS[step]);
      h.classList.add("card-text");
      body.appendChild(h);
      const row = el("div", "i-actions");
      row.appendChild(button("Hoppa över", "i-btn ghost", () => go(3)));
      row.appendChild(button(step === 2 ? "Kom igång" : "Vidare", "i-btn", () => go(step + 1)));
      body.appendChild(row);
    } else if (step === 3) renderAmount(body);
    else renderExchange(body);
    const head = body.querySelector(".i-head");
    if (head) head.focus({ preventScroll: true });
  }

  function go(n) { step = n; render(); }

  function renderAmount(body) {
    body.appendChild(heading("Hur mycket låtsaspengar vill du börja med?"));
    const wrap = el("div", "i-field");
    const label = el("label", "i-label", "Belopp i kronor");
    label.htmlFor = "intro-amount";
    const input = el("input", "i-input");
    input.id = "intro-amount"; input.type = "text"; input.inputMode = "numeric"; input.autocomplete = "off";
    input.spellcheck = false; input.placeholder = "10 000";
    input.setAttribute("aria-describedby", "intro-hint");
    if (amount !== null) input.value = sv(amount, 0);
    const hint = el("p", "i-hint");
    hint.id = "intro-hint";
    wrap.append(label, input, hint);
    body.appendChild(wrap);
    const row = el("div", "i-actions");
    const next = button("Fortsätt", "i-btn", () => { if (amount !== null) go(4); });
    next.disabled = true;
    row.appendChild(next);
    body.appendChild(row);
    const update = () => {
      amount = parseAmount(input.value);
      next.disabled = amount === null;
      hint.textContent = amount !== null ? `${sv(amount, 0)}${NB}kr i låtsaspengar.` :
        `Mellan ${sv(MIN, 0)} och ${sv(MAX, 0)}${NB}kr. Bara siffror.`;
    };
    input.addEventListener("input", update);
    input.addEventListener("keydown", (e) => { if (e.key === "Enter" && amount !== null) { e.preventDefault(); go(4); } });
    update();
  }

  function renderExchange(body) {
    body.appendChild(heading("Var vill du handla?"));
    const list = el("div", "i-list");
    list.setAttribute("role", "radiogroup");
    list.setAttribute("aria-label", "Börs");
    const start = button("Starta Walter", "i-btn", finish);
    start.disabled = exchangeId === null;
    (window.WALTER_EXCHANGES || []).forEach((x) => {
      const lab = el("label", "i-ex");
      const r = el("input");
      r.type = "radio"; r.name = "intro-ex"; r.value = x.id; r.checked = x.id === exchangeId;
      r.onchange = () => { exchangeId = x.id; start.disabled = false; };
      const txt = el("span", "i-ex-txt");
      txt.appendChild(el("span", "i-ex-name", x.name));
      // Land och avgift på var sin rad, så att en smal skärm aldrig bryter mitt i
      const meta = el("span", "i-ex-meta");
      exMeta(x).forEach((t) => meta.appendChild(el("span", "", t)));
      txt.appendChild(meta);
      if (x.assets && x.assets.ETH === false) txt.appendChild(el("span", "i-ex-miss", "Ether finns inte här"));
      if (x.assets && x.assets.GOLD === false) txt.appendChild(el("span", "i-ex-miss", "Guld finns inte här"));
      lab.append(r, txt);
      list.appendChild(lab);
    });
    body.appendChild(list);
    if (!window.WalterUser.storageOk()) {
      const w = el("p", "i-warn", NO_STORAGE);
      w.setAttribute("role", "status");
      body.appendChild(w);
    }
    const row = el("div", "i-actions");
    row.appendChild(button("Tillbaka", "i-btn ghost", () => go(3)));
    row.appendChild(start);
    body.appendChild(row);
  }

  function finish() {
    if (amount === null || exchangeId === null) return;
    const m = window.WALTER_MARKET;
    const day = (m && m.now && m.now.date) || window.WalterUser.today();
    const user = window.WalterUser.create(amount, exchangeId, day);
    window.WalterUser.save(user); // false = lagring blockerad; varningen står redan ovanför knappen
    hide();
    if (onDone) onDone(user);
    // Fokus till appens rubrik (läget), så att tangentbord och skärmläsare inte blir kvar på <body>
    const h = document.querySelector("main .mode-name") || document.querySelector("main");
    if (h) { h.tabIndex = -1; h.focus({ preventScroll: true }); }
  }

  function hide() {
    document.documentElement.classList.remove("intro-on");
    appParts().forEach((p) => { p.inert = false; });
    const r = root || document.getElementById("intro");
    if (r) r.hidden = true;
  }

  function start(done) {
    root = document.getElementById("intro");
    if (!root) return;
    onDone = done; step = 0; amount = null; exchangeId = null;
    document.documentElement.classList.add("intro-on");
    appParts().forEach((p) => { p.inert = true; });
    root.hidden = false;
    root.querySelector(".l-theme").onclick = () => {
      const dark = !isDark();
      if (dark) document.documentElement.dataset.theme = "dark"; else delete document.documentElement.dataset.theme;
      try { localStorage.setItem("walterDark", dark ? "1" : "0"); } catch (e) { /* lagring blockerad */ }
      syncTheme();
    };
    syncTheme();
    render();
  }

  window.WalterIntro = { start, parseAmount, exMeta };
})();
