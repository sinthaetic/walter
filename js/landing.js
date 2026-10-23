// Landningssidan (steg 9). boot.js anropar WalterLanding.show(market, onEnter) när man inte gått in i den här fliken.
// Lamporna bakom glaset är Walters riktiga lampor just nu (market.now.lamps). Okänt = "väntar" (dämpad), aldrig påhittat.
// Temat är appens: data-theme på <html> och localStorage "walterDark", så valet följer med in och ut.
(function () {
  "use strict";

  const MODE_WORD = { OFFENSIV: "KÖPER", NORMAL: "KÖPER LITE", AVVAKTAR: "AVVAKTAR", PARKERA: "VILAR" };
  const reduce = () => window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const isDark = () => document.documentElement.dataset.theme === "dark";

  let root = null, raf = 0, clockTimer = 0, glitchTimer = 0, glitchOff = 0, offResize = null;

  const appParts = () => document.querySelectorAll("body > header, body > main, body > footer");

  function setText(el, lines) {
    el.textContent = "";
    lines.forEach((t, i) => { if (i) el.appendChild(document.createElement("br")); el.appendChild(document.createTextNode(t)); });
  }

  function syncThemeMeta() {
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = isDark() ? "#0A1216" : "#D7E0E3";
    const btn = root && root.querySelector(".l-theme");
    if (btn) btn.setAttribute("aria-label", isDark() ? "Byt till ljust läge" : "Byt till mörkt läge");
    // Appens egen knapp (om appen redan ritats) ska säga samma sak
    const appBtn = document.getElementById("theme");
    if (appBtn) appBtn.setAttribute("aria-label", isDark() ? "Byt till ljust läge" : "Byt till mörkt läge");
  }

  // Labbet: lampor och avläsningar från marknadsfilen
  function fillLab(market) {
    const now = (market && market.now) || {};
    const lamps = Array.isArray(now.lamps) ? now.lamps : [];
    const n = lamps.length || 10;
    const box = root.querySelector(".lab .lamps");
    box.textContent = "";
    for (let i = 0; i < n; i++) {
      const s = lamps[i] ? lamps[i].status : null;
      const el = document.createElement("i");
      el.className = s === "red" ? "r" : s === "green" ? "g" : "w";
      box.appendChild(el);
    }
    const red = lamps.filter((l) => l.status === "red").length;
    const green = lamps.filter((l) => l.status === "green").length;
    const wait = n - red - green;
    const btc = now.px && typeof now.px.BTC === "number" ? Math.round(now.px.BTC).toLocaleString("sv-SE") + " KR" : "VÄNTAR";
    setText(root.querySelector(".r1"), ["LÄGE", MODE_WORD[now.mode] || "VÄNTAR"]);
    setText(root.querySelector(".r2"), ["BTC", btc]);
    setText(root.querySelector(".r3"), ["LAMPOR", lamps.length ? `${green} GRÖNA · ${red} RÖDA` + (wait ? ` · ${wait} VÄNTAR` : "") : "VÄNTAR PÅ DATA"]);
    setText(root.querySelector(".r4"), ["DATA", now.date || "VÄNTAR"]);
    root.querySelector("#landing-signals").textContent = `LÄSER ${n} SIGNALER`;
  }

  function setupWord() {
    const w = root.querySelector(".word");
    const text = w.getAttribute("aria-label") || "WALTER";
    w.textContent = "";
    [...text].forEach((c, i) => {
      const s = document.createElement("span");
      s.textContent = c;
      s.setAttribute("aria-hidden", "true");
      s.style.animationDelay = (0.4 + i * 0.14) + "s";
      w.appendChild(s);
    });
  }

  function wave() {
    const pts = [];
    for (let x = 0; x <= 2000; x += 10) {
      const t = x / 1000 * Math.PI * 2;
      pts.push(`${x} ${(100 - 38 * Math.sin(t) - 22 * Math.sin(3 * t + 1) - 10 * Math.sin(7 * t + 2)).toFixed(1)}`);
    }
    root.querySelector(".chart path").setAttribute("d", "M" + pts.join(" L"));
  }

  function show(market, onEnter) {
    // Idempotent: en andra show() städar först bort timers, rAF och lyssnare från den förra
    hide();
    root = document.getElementById("landing");
    if (!root) { if (onEnter) onEnter(); return; }
    const still = reduce();
    document.documentElement.classList.add("landing-on");
    // Appen bakom landningen går inte att nå med tangentbord eller skärmläsare
    appParts().forEach((el) => { el.inert = true; });
    root.hidden = false;
    root.classList.remove("leaving");
    fillLab(market);
    setupWord();
    wave();
    syncThemeMeta();

    // Klocka
    const clock = root.querySelector("#landing-clock");
    const tick = () => { clock.textContent = new Date().toLocaleTimeString("sv-SE"); };
    tick(); clockTimer = setInterval(tick, 1000);

    // Logon glitchar ibland (3,5–9,5 s)
    const logo = root.querySelector(".logo");
    const glitch = () => {
      logo.classList.add("glitch");
      glitchOff = setTimeout(() => logo.classList.remove("glitch"), 430);
      glitchTimer = setTimeout(glitch, 3500 + Math.random() * 6000);
    };
    if (!still) glitchTimer = setTimeout(glitch, 2600);

    // Musen (eller fingret) torkar en liten klar fläck i rutan
    const pane = root.querySelector(".pane"), frost = root.querySelector(".frost");
    let tx = -999, ty = -999, cx = -999, cy = -999;
    pane.onpointermove = (e) => {
      const r = pane.getBoundingClientRect();
      tx = e.clientX - r.left; ty = e.clientY - r.top;
      if (cx < -900 || still) { cx = tx; cy = ty; }
      if (still) { frost.style.setProperty("--mx", cx + "px"); frost.style.setProperty("--my", cy + "px"); }
    };
    pane.onpointerleave = () => { tx = ty = cx = cy = -999; frost.style.setProperty("--mx", "-999px"); frost.style.setProperty("--my", "-999px"); };

    // Mjuk rörlig bakgrund: stora suddiga ljusfläckar som driver
    const cv = root.querySelector("canvas.fluid"), ctx = cv.getContext("2d");
    let W = 0, H = 0;
    const blobs = [0, 1, 2, 3, 4].map((i) => ({
      p: Math.random() * 6.28, s: 0.00012 + Math.random() * 0.00012, r: 0.45 + Math.random() * 0.3,
      c: ["--blob1", "--blob2", "--blob3", "--blob1", "--blob2"][i], a: [0.32, 0.3, 0.12, 0.22, 0.2][i]
    }));
    // Färgerna läses en gång och på nytt när temat byts, inte varje bildruta
    let colors = null;
    const readColors = () => {
      const css = getComputedStyle(root);
      colors = { bg: css.getPropertyValue("--bg-solid").trim() || "#D7E0E3", dark: isDark() };
      ["--blob1", "--blob2", "--blob3"].forEach((k) => { colors[k] = css.getPropertyValue(k).trim(); });
    };
    readColors();
    const draw = (t) => {
      ctx.globalCompositeOperation = "source-over";
      ctx.fillStyle = colors.bg;
      ctx.fillRect(0, 0, W, H);
      ctx.globalCompositeOperation = colors.dark ? "lighter" : "source-over";
      blobs.forEach((b, i) => {
        const x = W * (0.5 + 0.38 * Math.sin(t * b.s + b.p + i)), y = H * (0.5 + 0.34 * Math.cos(t * b.s * 1.3 + b.p * 2));
        const g = ctx.createRadialGradient(x, y, 0, x, y, Math.max(W, H) * b.r);
        const rgb = colors[b.c];
        g.addColorStop(0, `rgba(${rgb},${b.a})`); g.addColorStop(1, `rgba(${rgb},0)`);
        ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
      });
      ctx.globalCompositeOperation = "source-over";
    };
    const loop = (t) => {
      if (tx > -900) {
        cx += (tx - cx) * 0.08; cy += (ty - cy) * 0.08;
        frost.style.setProperty("--mx", cx + "px"); frost.style.setProperty("--my", cy + "px");
      }
      draw(t);
      raf = requestAnimationFrame(loop);
    };
    const size = () => { W = cv.width = Math.max(1, Math.round(window.innerWidth * 0.5)); H = cv.height = Math.max(1, Math.round(window.innerHeight * 0.5)); if (still) draw(0); };
    size();
    window.addEventListener("resize", size);
    offResize = () => window.removeEventListener("resize", size);
    if (still) draw(0); else raf = requestAnimationFrame(loop);

    // Ljust är standard. Samma nyckel som appen (walterDark), så valet följer med in
    root.querySelector(".l-theme").onclick = () => {
      const dark = !isDark();
      if (dark) document.documentElement.dataset.theme = "dark"; else delete document.documentElement.dataset.theme;
      try { localStorage.setItem("walterDark", dark ? "1" : "0"); } catch (e) { /* lagring blockerad */ }
      syncThemeMeta();
      readColors();
      if (still) draw(0);
    };

    // GÅ IN: kom ihåg för fliken, tona ut (600 ms, ingen toning med reduced motion), fortsätt in
    const cta = root.querySelector(".cta");
    cta.onclick = () => {
      cta.disabled = true;
      try { window.sessionStorage.setItem("walterEntered", "1"); } catch (e) { /* lagring blockerad */ }
      try { if (onEnter) onEnter(); } catch (e) { /* appen säger själv vad som gick fel; landningen ska ändå gå undan */ }
      if (reduce()) { hide(); return; }
      root.classList.add("leaving");
      setTimeout(hide, 600);
    };
    if (!still) cta.focus({ preventScroll: true });
  }

  // Dölj och stoppa allt som rör sig (canvas, klocka, glitch)
  function hide() {
    if (raf) cancelAnimationFrame(raf);
    raf = 0;
    clearInterval(clockTimer); clearTimeout(glitchTimer); clearTimeout(glitchOff);
    if (offResize) { offResize(); offResize = null; }
    document.documentElement.classList.remove("landing-on");
    appParts().forEach((p) => { p.inert = false; });
    const el = root || document.getElementById("landing");
    if (el) {
      const pane = el.querySelector(".pane");
      if (pane) { pane.onpointermove = null; pane.onpointerleave = null; }
      const frost = el.querySelector(".frost");
      if (frost) { frost.style.removeProperty("--mx"); frost.style.removeProperty("--my"); }
      el.hidden = true; el.classList.remove("leaving");
      const logo = el.querySelector(".logo");
      if (logo) logo.classList.remove("glitch");
      const c = el.querySelector(".cta");
      if (c) c.disabled = false;
    }
  }

  window.WalterLanding = { show, hide };
})();
