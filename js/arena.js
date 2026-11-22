// Arenan (Pro-sidan): du mot Walter. Ställningen, ditt drag, kapplöpningen, säsongen och din kassa.
// All räkning ligger i js/manual.js; den här filen ritar och kopplar knapparna. Kassan sparas bara i webbläsaren.
// mount(c) -> {render, show, marks, onMarks}. c = värden och formatterare från js/app.js.
(function () {
  "use strict";

  const MONTHS = ["januari", "februari", "mars", "april", "maj", "juni", "juli", "augusti", "september", "oktober", "november", "december"];
  const ORD = ["första", "andra", "tredje", "fjärde", "femte", "sjätte", "sjunde", "åttonde", "nionde", "tionde", "elfte", "tolfte"];
  const $ = (id) => document.getElementById(id);

  function mount(c) {
    const { S, pf, fx, kr, kr2, pct, nf, esc, day, store, own, fee, today, apDay, journalTrades, market } = c;
    const MAN = window.WalterManual, KEY = own("manual");
    let side = "köp", amountTxt = "", msg = "", marksCb = null;

    const load = () => { const p = store.get(KEY, null); return MAN.validPot(p) ? p : null; };
    const save = (p) => store.set(KEY, p);
    const price = () => {
      const px = fx().btcSek, d = market.btc && market.btc.asOf;
      return { px, day: d, fresh: px > 0 && !!d && (Date.now() - new Date(d + "T12:00:00")) / 864e5 <= 2 };
    };
    const log = () => (window.WALTER_MARKET && window.WALTER_MARKET.log) || [];
    const sign = (v, d = 1) => (Math.abs(v) < 0.05 ? nf(d).format(0) : (v > 0 ? "+" : "−") + nf(d).format(Math.abs(v)));
    const num = (t) => Number(String(t).replace(/[\s ]|kr/gi, "").replace(",", "."));

    // Walters stopp: dagspriserna sedan förra besöket, sedan dagens pris
    function runStops(pot, P) {
      const rows = log().map((r) => ({ date: r.date, px: r.px && r.px.BTC })).filter((r) => r.px > 0);
      const hit = MAN.checkStop(pot, rows, fee);
      if (!hit && P.fresh) MAN.checkLive(pot, P.px, fee, today);
      const last = pot.trades[pot.trades.length - 1];
      if (last && last.why === "stopp" && !pot.stopSeen) {
        msg = last.side === "stäng"
          ? `Walter stängde din blankning ${day(last.date)}: priset steg 10 % från botten.`
          : `Walter sålde din bitcoin ${day(last.date)}: priset föll 10 % från toppen.`;
        pot.stopSeen = true;
      }
      if (last && last.why !== "stopp") pot.stopSeen = false;
      save(pot);
    }

    // Båda kurvorna från samma startdag, och ställningen i procent
    function standing(pot, P) {
      const rows = log().map((r) => ({ date: r.date, px: r.px && r.px.BTC })).filter((r) => r.px > 0);
      if (P.fresh) {
        const i = rows.findIndex((r) => r.date === today);
        if (i >= 0) rows[i] = { date: today, px: P.px }; else rows.push({ date: today, px: P.px });
      }
      const flows = (pf.history || []).filter((h) => h.flow).map((h) => ({ date: h.date, flow: h.flow }));
      const du = MAN.potCurve(pot, rows);
      const wa = MAN.walterCurve(journalTrades(S.journal).reverse(), flows, log().filter((r) => r.px), pot.since);
      const mine = (MAN.value(pot, P.px, today) / pot.startSek - 1) * 100;
      const w = pot.walter;
      const his = wa.length > 1 ? wa[wa.length - 1].pct : w && w.value > 0 ? (c.marketGain - w.gain) / w.value * 100 : 0;
      return { du, wa, mine, his, lead: mine - his, value: MAN.value(pot, P.px, today) };
    }

    // ---------- Ställningen ----------
    function drawDuel(pot, st) {
      const el = $("ar-duel");
      if (!pot) {
        el.innerHTML = `
          <div class="ar-side"><span class="ar-lab ar-du">D U</span><strong class="ar-big ar-du">0,0<small>%</small></strong><span class="ar-sub">Starta din kassa</span></div>
          <div class="ar-lead"><span class="ar-lab">REDO?</span><span class="ar-leadn">VS</span></div>
          <div class="ar-side r"><span class="ar-lab ar-wa">W A L T E R</span><strong class="ar-big ar-wa">0,0<small>%</small></strong><span class="ar-sub">autopilot</span></div>
          <div class="ar-rail" aria-hidden="true"><i style="left:50%"></i></div>`;
        return;
      }
      const lead = st.lead, tied = Math.abs(lead) < 0.05;
      const pos = 50 - Math.max(-1, Math.min(1, lead / 20)) * 42;
      el.innerHTML = `
        <div class="ar-side"><span class="ar-lab ar-du">D U</span><strong class="ar-big ar-du" data-who="du" data-v="${st.mine}">${sign(st.mine)}<small>%</small></strong><span class="ar-sub num">${kr(st.value)}</span></div>
        <div class="ar-lead"><span class="ar-lab" id="ar-leadlab">${tied ? "LIKA" : lead > 0 ? "DU LEDER" : "WALTER LEDER"}</span><span class="ar-leadn num" id="ar-leadnum">${tied ? "0,0" : "+" + nf(1).format(Math.abs(lead))}</span><span class="ar-unit" id="ar-when">procentenheter</span></div>
        <div class="ar-side r"><span class="ar-lab ar-wa">W A L T E R</span><strong class="ar-big ar-wa" data-who="wa" data-v="${st.his}">${sign(st.his)}<small>%</small></strong><span class="ar-sub">autopilot</span></div>
        <div class="ar-rail" role="img" aria-label="${tied ? "Ni står lika" : lead > 0 ? "Du leder över Walter" : "Walter leder över dig"}"><i id="ar-dot" class="${lead < 0 ? "wa" : ""}" style="left:${pos.toFixed(1)}%"></i></div>`;
    }

    // ---------- Rörelse: siffrorna, tidsmaskinen och pulsen när du handlar ----------
    const calm = () => !window.matchMedia || window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const setBig = (who, v) => { const e = document.querySelector(`[data-who="${who}"]`); if (e) e.firstChild.nodeValue = sign(v); };
    const railPos = (lead) => 50 - Math.max(-1, Math.min(1, lead / 20)) * 42;
    function showStanding(du, wa, when) {
      const lead = du - wa, tied = Math.abs(lead) < 0.05, dot = $("ar-dot");
      setBig("du", du); setBig("wa", wa);
      if (!$("ar-leadnum")) return;
      $("ar-leadlab").textContent = tied ? "LIKA" : lead > 0 ? "DU LEDER" : "WALTER LEDER";
      $("ar-leadnum").textContent = tied ? "0,0" : "+" + nf(1).format(Math.abs(lead));
      $("ar-when").textContent = when || "procentenheter";
      dot.style.left = `${railPos(lead).toFixed(1)}%`;
      dot.classList.toggle("wa", lead < 0);
    }
    let played = false;
    function intro(st) {
      if (played || !st || $("view-pro").hidden) return;
      played = true;
      if (calm()) return;
      const end = performance.now() + 1100, t0 = end - 1100;
      const frame = (now) => {
        if (scrubbing) return; // du drar i kurvan: den dagen du står på gäller, introt slutar
        const k = Math.min(1, (now - t0) / 1100), e = 1 - Math.pow(1 - k, 3);
        showStanding(st.mine * e, st.his * e);
        if (k < 1) requestAnimationFrame(frame);
      };
      requestAnimationFrame(frame);
      const plot = document.querySelector(".ar-plot svg");
      if (plot) plot.classList.add("ar-wipe");
    }
    let scrubbing = false;
    function pulse() {
      if (calm()) return;
      const e = $("ar-duel");
      e.classList.remove("ar-hit"); void e.offsetWidth; e.classList.add("ar-hit");
    }

    // ---------- Ditt drag ----------
    function preview(pot, P) {
      if (!$("ar-amt")) return;
      const sek = num($("ar-amt").value) || 0;
      amountTxt = $("ar-amt").value;
      const f = sek * fee, stopAt = side === "blanka" ? P.px * (1 + MAN.STOP) : (pot.peakPx || P.px) * (1 - MAN.STOP);
      const risk = side === "sälj" ? 0 : sek * MAN.STOP + f * 2;
      $("ar-fee").textContent = kr2(f);
      $("ar-stop").textContent = side === "sälj" ? "–" : kr(stopAt);
      $("ar-risk").textContent = side === "sälj" ? "0 kr" : kr(risk);
      const verb = { "köp": "KÖP", "sälj": "SÄLJ", "blanka": "BLANKA" }[side];
      $("ar-go").textContent = sek >= 1 ? `${verb} FÖR ${kr(sek).toUpperCase()}` : `${verb}: SKRIV EN SUMMA`;
    }

    function walterLine(pot, st) {
      if (!pot) return "Visa vad du går för. Jag håller min kurs.";
      const next = `Jag håller kursen och justerar på ${apDay}.`;
      return Math.abs(st.lead) < 0.05 ? `Vi står lika. ${next}` : st.lead > 0 ? `Du leder. ${next}` : `Jag leder. ${next}`;
    }

    function drawTicket(pot, P, st) {
      const el = $("manual");
      if (!pot) {
        el.innerHTML = `
          <span class="ar-lab">DIN KASSA</span>
          <p class="ar-hint">Välj en låtsassumma och utmana Walter. Hans pengar rörs aldrig.</p>
          <label class="ar-field"><span class="ar-lab">STARTBELOPP I KRONOR</span>
            <input class="ar-amt num" id="man-start" type="text" inputmode="numeric" autocomplete="off" value="10 000"></label>
          <button type="button" class="ar-go" id="man-go">STARTA DUELLEN</button>
          <p class="ar-msg" id="ar-msg" role="status"></p>
          <div class="ar-says"><i></i><p>${esc(walterLine(null))}<span class="ar-lab">WALTER</span></p></div>`;
        $("man-go").onclick = () => {
          const sek = Math.round(num($("man-start").value));
          if (!(sek >= 100 && sek <= 1e8)) { $("ar-msg").textContent = "Skriv ett belopp mellan 100 kr och 100 000 000 kr."; return; }
          save(MAN.create(sek, today, { value: pf.value, gain: c.marketGain }));
          render();
        };
        return;
      }
      if (pot.short) {
        const v = MAN.shortValue(pot, P.px, today), gain = v - pot.short.sek;
        el.innerHTML = `
          <div class="ar-row"><span class="ar-lab">DIN BLANKNING</span><span class="num ar-small">${kr(pot.cash)} ledigt</span></div>
          <strong class="ar-pos num">${gain < 0 ? "−" : "+"}${kr(Math.abs(gain))}</strong>
          <p class="ar-hint">Du tjänar om priset faller. Blankat från ${kr(pot.short.px)}.</p>
          <dl class="ar-sum"><div><dt>Värde nu</dt><dd class="num">${kr(v)}</dd></div>
            <div><dt>Walter stänger över</dt><dd class="num">${kr(MAN.stopPx(pot))}</dd></div>
            <div><dt>Kostnad per dag</dt><dd class="num">${nf(2).format(MAN.FUNDING_DAY * 100)} %</dd></div></dl>
          ${P.fresh ? '<button type="button" class="ar-go" id="man-cover">STÄNG BLANKNING</button>' : '<button type="button" class="ar-go" id="ar-refresh">HÄMTA FÄRSKT PRIS</button>'}
          <p class="ar-msg" id="ar-msg" role="status">${esc(msg)}</p>
          <div class="ar-says"><i></i><p>${esc(walterLine(pot, st))}<span class="ar-lab">WALTER</span></p></div>`;
        if ($("man-cover")) $("man-cover").onclick = () => {
          MAN.cover(pot, P.px, fee, today);
          const g = pot.trades[pot.trades.length - 1].gainSek;
          msg = `Blankningen stängd: ${g < 0 ? "−" : "+"}${kr(Math.abs(g))} efter avgifter.`;
          save(pot); render();
        };
        if ($("ar-refresh")) $("ar-refresh").onclick = () => $("btn-refresh").click();
        return;
      }
      const hint = { "köp": "Du tjänar om priset stiger.", "sälj": pot.units ? `Du äger bitcoin för ${kr(pot.units * P.px)}.` : "Du äger ingen bitcoin att sälja.", "blanka": "Du tjänar om priset faller." }[side];
      el.innerHTML = `
        <div class="ar-row"><span class="ar-lab">DITT DRAG</span><span class="num ar-small">${kr(pot.cash)} ledigt</span></div>
        <div class="ar-seg" role="group" aria-label="Typ av affär">
          ${["köp", "sälj", "blanka"].map((s) => `<button type="button" data-side="${s}" aria-pressed="${s === side}">${s === "köp" ? "KÖP" : s === "sälj" ? "SÄLJ" : "BLANKA"}</button>`).join("")}
        </div>
        <p class="ar-hint">${esc(hint)}</p>
        <label class="ar-field"><span class="ar-lab">SUMMA I KRONOR</span>
          <input class="ar-amt num" id="ar-amt" type="text" inputmode="numeric" autocomplete="off" placeholder="0" value="${esc(amountTxt)}"></label>
        <div class="ar-pre" role="group" aria-label="Andel">
          ${[[.25, "25 %"], [.5, "50 %"], [.75, "75 %"], [1, "ALLT"]].map(([p, t]) => `<button type="button" data-p="${p}">${t}</button>`).join("")}
        </div>
        <dl class="ar-sum"><div><dt>Avgift</dt><dd class="num" id="ar-fee"></dd></div>
          <div><dt>Walter stoppar vid</dt><dd class="num" id="ar-stop"></dd></div>
          <div><dt>Risk om stoppet tas</dt><dd class="num" id="ar-risk"></dd></div></dl>
        ${P.fresh ? '<button type="button" class="ar-go" id="ar-go"></button>' : '<button type="button" class="ar-go" id="ar-refresh">HÄMTA FÄRSKT PRIS</button>'}
        <p class="ar-msg" id="ar-msg" role="status">${esc(msg || (P.fresh ? `Pris ${kr(P.px)} (${day(P.day)}).` : "Priset är inte färskt, så du kan inte handla just nu."))}</p>
        <div class="ar-says"><i></i><p>${esc(walterLine(pot, st))}<span class="ar-lab">WALTER</span></p></div>`;
      if (!P.fresh) $("ar-refresh").onclick = () => $("btn-refresh").click();
      el.querySelectorAll("[data-side]").forEach((b) => { b.onclick = () => { side = b.dataset.side; amountTxt = $("ar-amt").value; msg = ""; drawTicket(pot, P, st); }; });
      el.querySelectorAll("[data-p]").forEach((b) => {
        b.onclick = () => {
          const base = side === "sälj" ? pot.units * P.px : pot.cash, p = +b.dataset.p;
          $("ar-amt").value = nf(0).format(p === 1 ? Math.floor(base) : Math.round(base * p));
          if (P.fresh) preview(pot, P);
        };
      });
      if (!P.fresh) return;
      $("ar-amt").oninput = () => preview(pot, P);
      $("ar-go").onclick = () => place(pot, P);
      preview(pot, P);
    }

    function place(pot, P) {
      const sek = num($("ar-amt").value), say = (t) => { $("ar-msg").textContent = t; };
      if (!(sek >= 1)) { say("Skriv en summa först."); return; }
      if (side === "köp") {
        if (!MAN.buy(pot, sek, P.px, fee, today)) { say(`Du har ${kr(pot.cash)} ledigt.`); return; }
        msg = `Köpte bitcoin för ${kr(sek)}.`;
      } else if (side === "sälj") {
        if (!pot.units) { say("Du äger ingen bitcoin att sälja."); return; }
        const all = sek >= Math.floor(pot.units * P.px);
        MAN.sell(pot, all ? Infinity : sek, P.px, fee, today);
        msg = all ? "Sålde all bitcoin." : `Sålde bitcoin för ${kr(sek)}.`;
      } else {
        if (pot.units && pot.units * P.px < 1) MAN.sell(pot, Infinity, P.px, fee, today); // en rest under 1 kr ska inte stoppa
        if (pot.units) { say(`Sälj din bitcoin (${kr(pot.units * P.px)}) först.`); return; }
        if (!MAN.short(pot, sek, P.px, fee, today)) { say(`Du har ${kr(pot.cash)} ledigt.`); return; }
        msg = `Blankade bitcoin för ${kr(sek)}.`;
      }
      amountTxt = "";
      save(pot);
      render();
      pulse();
    }

    // ---------- Kapplöpningen ----------
    function drawRace(pot, st) {
      const el = $("ar-race");
      const head = `<div class="ar-row"><span class="ar-lab ar-ink">KAPPLÖPNINGEN</span>
        <span class="ar-key"><span><i class="du"></i>Du</span><span><i class="wa"></i>Walter</span></span></div>`;
      const w = new Map(((st && st.wa) || []).map((p) => [p.date, p.pct]));
      const pts = st ? st.du.filter((p) => w.has(p.date)).map((p) => ({ date: p.date, du: p.pct, wa: w.get(p.date) })) : [];
      if (pts.length < 2) {
        el.innerHTML = head + `<p class="ar-empty">${pot ? "Kurvorna ritas när ni har tävlat i minst två dagar." : "Starta kassan, så börjar kapplöpningen här."}</p>`;
        return;
      }
      const W = Math.max(280, el.clientWidth - 44), H = W < 520 ? 190 : 230, R = 70, T = 12, B = 24;
      const vals = pts.flatMap((p) => [p.du, p.wa]).concat(0), hi = Math.max(...vals) + 1, lo = Math.min(...vals) - 1;
      const X = (i) => (i * (W - R)) / (pts.length - 1), Y = (v) => T + ((hi - v) / (hi - lo)) * (H - T - B);
      const line = (k) => pts.map((p, i) => `${X(i).toFixed(1)},${Y(p[k]).toFixed(1)}`).join(" ");
      const gap = `M${pts.map((p, i) => `${X(i).toFixed(1)} ${Y(p.du).toFixed(1)}`).join("L")}L` +
        pts.map((p, i) => `${X(i).toFixed(1)} ${Y(p.wa).toFixed(1)}`).reverse().join("L") + "Z";
      const e = pts[pts.length - 1], ex = X(pts.length - 1);
      let yD = Y(e.du) + 5, yW = Y(e.wa) + 5;
      if (Math.abs(yD - yW) < 16) { if (yD <= yW) yW = yD + 16; else yD = yW + 16; }
      el.innerHTML = head + `
        <div class="ar-plot"><svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="Du ${esc(sign(e.du))} procent, Walter ${esc(sign(e.wa))} procent sedan ${esc(day(pts[0].date))}">
          <line class="ar-zero" x1="0" x2="${ex}" y1="${Y(0).toFixed(1)}" y2="${Y(0).toFixed(1)}"></line>
          <text class="ar-tick" x="${ex}" y="${(Y(0) - 6).toFixed(1)}" text-anchor="end">START 0 %</text>
          <defs><linearGradient id="ar-gapf" x1="0" y1="0" x2="1" y2="0"><stop offset="0" stop-color="var(--du)" stop-opacity="0"></stop><stop offset="1" stop-color="var(--du)" stop-opacity=".3"></stop></linearGradient></defs>
          <path d="${gap}" fill="url(#ar-gapf)"></path>
          ${[3, 6, 9, 12].map((d, i) => `<polyline class="ar-echo wa" style="opacity:${(.26 - i * .05).toFixed(2)}" transform="translate(0 ${d})" points="${line("wa")}"></polyline><polyline class="ar-echo du" style="opacity:${(.3 - i * .06).toFixed(2)}" transform="translate(0 ${-d})" points="${line("du")}"></polyline>`).join("")}
          <polyline class="ar-lwa" points="${line("wa")}"></polyline>
          <polyline class="ar-ldu" points="${line("du")}"></polyline>
          <circle class="ar-ring wa" cx="${ex}" cy="${Y(e.wa).toFixed(1)}" r="5"></circle><circle class="ar-ring du" cx="${ex}" cy="${Y(e.du).toFixed(1)}" r="5"></circle>
          <circle class="ar-dwa" cx="${ex}" cy="${Y(e.wa).toFixed(1)}" r="5"></circle><circle class="ar-ddu" cx="${ex}" cy="${Y(e.du).toFixed(1)}" r="5"></circle>
          <circle class="ar-dwa" id="ar-sw" r="5" hidden></circle><circle class="ar-ddu" id="ar-sd" r="5" hidden></circle>
          <text class="ar-end" x="${ex + 11}" y="${yD.toFixed(1)}">${esc(sign(e.du))} %</text><text class="ar-end" x="${ex + 11}" y="${yW.toFixed(1)}">${esc(sign(e.wa))} %</text>
          <text class="ar-tick" x="0" y="${H - 5}">${esc(day(pts[0].date))}</text><text class="ar-tick" x="${ex}" y="${H - 5}" text-anchor="end">${esc(day(e.date))}</text>
          <line class="ar-cross" id="ar-cross" y1="${T}" y2="${H - B}" hidden></line>
        </svg><div class="ar-tip" id="ar-tip" hidden></div></div>
        <p class="ar-scrub">Dra över kurvan för att spola tillbaka ställningen.</p>
        ${statRow(pot)}`;
      const plot = el.querySelector(".ar-plot"), cross = $("ar-cross"), tip = $("ar-tip"), sd = $("ar-sd"), sw = $("ar-sw");
      plot.onpointermove = (ev) => {
        const r = plot.getBoundingClientRect(), i = Math.max(0, Math.min(pts.length - 1, Math.round(((ev.clientX - r.left) / (W - R)) * (pts.length - 1))));
        const p = pts[i], x = X(i);
        scrubbing = true;
        showStanding(p.du, p.wa, day(p.date));
        [[sd, p.du], [sw, p.wa]].forEach(([c, v]) => { c.removeAttribute("hidden"); c.setAttribute("cx", x); c.setAttribute("cy", Y(v).toFixed(1)); });
        cross.removeAttribute("hidden"); cross.setAttribute("x1", x); cross.setAttribute("x2", x);
        tip.hidden = false;
        tip.textContent = `${day(p.date)} · Du ${sign(p.du)} % · Walter ${sign(p.wa)} %`;
        tip.style.left = `${Math.max(0, Math.min(W - tip.offsetWidth, x - tip.offsetWidth / 2))}px`;
      };
      // Släpp: tillbaka till ställningen just nu
      plot.onpointerleave = plot.onpointercancel = () => {
        scrubbing = false;
        [cross, sd, sw].forEach((n) => n.setAttribute("hidden", ""));
        tip.hidden = true;
        if (st) showStanding(st.mine, st.his);
      };
    }

    function statRow(pot) {
      const done = pot.trades.filter((t) => t.side === "sälj" || t.side === "stäng"), wins = done.filter((t) => t.gainSek > 0);
      const fees = pot.trades.reduce((a, t) => a + t.feeSek, 0);
      return `<dl class="ar-stats"><div><dt>Affärer</dt><dd class="num">${pot.trades.length}</dd></div>
        <div><dt>Träff</dt><dd class="num">${done.length ? nf(0).format((wins.length / done.length) * 100) + " %" : "–"}</dd></div>
        <div><dt>Resultat, avslutat</dt><dd class="num">${(() => { const g = done.reduce((a, t) => a + t.gainSek, 0); return (g < 0 ? "−" : "+") + kr(Math.abs(g)); })()}</dd></div>
        <div><dt>Dina avgifter</dt><dd class="num">${kr(fees)}</dd></div></dl>`;
    }

    // ---------- Säsongen ----------
    function drawSeason(pot, st) {
      const el = $("ar-season");
      if (!pot) {
        el.innerHTML = `<div class="ar-row"><span class="ar-lab ar-ink">SÄSONGEN</span></div><p class="ar-empty">Varje månad är en runda. Bäst resultat efter avgifter vinner.</p>`;
        return;
      }
      const list = MAN.rounds(st.du, st.wa, pot.trades, today).slice(0, 12);
      const done = list.filter((r) => !r.live), d = done.filter((r) => r.winner === "du").length, w = done.filter((r) => r.winner === "walter").length;
      const cur = list.find((r) => r.live), mNow = +today.slice(5, 7) - 1, idx = cur ? list.indexOf(cur) : list.length;
      const y = +today.slice(0, 4), left = new Date(y, mNow + 1, 0).getDate() - +today.slice(8, 10);
      const line = !cur || cur.winner === null ? `${MONTHS[mNow][0].toUpperCase() + MONTHS[mNow].slice(1)} är helt öppen.`
        : cur.winner === "du" ? `Vinner du ${MONTHS[mNow]} tar du ${ORD[Math.min(idx, 11)]} rundan.` : `Walter leder ${MONTHS[mNow]}. Du har ${left} ${left === 1 ? "dag" : "dagar"} på dig.`;
      const seg = Array.from({ length: 12 }, (_, i) => { const r = list[i]; return `<i class="${r ? (r.live ? "live" : r.winner || "tie") : ""}"></i>`; }).join("");
      const b = MAN.badges(list);
      el.innerHTML = `
        <div class="ar-row"><span class="ar-lab ar-ink">SÄSONG 1</span><span class="num ar-small">Runda ${Math.min(idx + 1, 12)} av 12 · ${left} ${left === 1 ? "dag" : "dagar"} kvar</span></div>
        <div class="ar-score"><strong class="ar-du num">${d}</strong><span>–</span><strong class="ar-wa num">${w}</strong><p>${esc(line)}</p></div>
        <div class="ar-segs" role="img" aria-label="${d} rundor till dig, ${w} till Walter">${seg}</div>
        <ul class="ar-badges">${b.map((x) => `<li class="${x.won ? "won" : x.live ? "live" : ""}"><b>${esc(x.name)}</b><span>${x.won ? "Upplåst" : x.live ? "På väg" : x.progress ? esc(x.progress) : "Låst"}</span></li>`).join("")}</ul>`;
    }

    // ---------- Din kassa (kopia, avsluta) ----------
    function drawKassa(pot) {
      const el = $("ar-kassa");
      const build = (document.querySelector('meta[name="walter-build"]') || {}).content || "okänd";
      el.innerHTML = `
        <p class="small">Kassan finns bara i den här webbläsaren. Spara en kopia ibland, eller flytta den till en annan enhet.</p>
        <div class="ar-tools">
          ${pot ? '<button type="button" class="btn" id="ar-export">SPARA KOPIA</button>' : ""}
          <button type="button" class="btn" id="ar-import">LÄS IN KOPIA</button>
          <input type="file" id="ar-file" accept=".json,application/json" hidden>
          ${pot ? '<button type="button" class="btn" id="man-end">AVSLUTA DUELLEN</button>' : ""}
        </div>
        <p class="small msg" id="ar-kmsg" role="status"></p>
        <p class="small">Version ${esc(build)}</p>`;
      if (pot) {
        $("ar-export").onclick = () => {
          const a = document.createElement("a"), url = URL.createObjectURL(new Blob([MAN.exportText(pot)], { type: "application/json" }));
          a.href = url; a.download = `walter-kassa-${today}.json`; a.click();
          setTimeout(() => URL.revokeObjectURL(url), 1000);
          $("ar-kmsg").textContent = "Kopian är sparad.";
        };
        $("man-end").onclick = () => {
          if ($("man-end").dataset.sure !== "1") { $("man-end").dataset.sure = "1"; $("man-end").textContent = "SÄKER? TRYCK IGEN"; return; }
          try { localStorage.removeItem(KEY); } catch (e) { /* lagring blockerad */ }
          msg = ""; render();
        };
      }
      $("ar-import").onclick = () => $("ar-file").click();
      $("ar-file").onchange = async (ev) => {
        const file = ev.target.files && ev.target.files[0];
        if (!file) return;
        const p = file.size < 2e6 ? MAN.parsePot(await file.text()) : null;
        ev.target.value = "";
        if (!p) { $("ar-kmsg").textContent = "Det där är ingen kopia av en Walter-kassa."; return; }
        if (load() && !confirm("Ersätta din nuvarande kassa med kopian?")) return;
        save(p); msg = "Kopian är inläst."; render();
      };
    }

    function render() {
      const pot = load(), P = price();
      if (pot) runStops(pot, P);
      const st = pot ? standing(pot, P) : null;
      drawDuel(pot, st);
      drawTicket(pot, P, st);
      drawRace(pot, st);
      drawSeason(pot, st);
      drawKassa(pot);
      msg = "";
      if (marksCb) marksCb();
      intro(st);
    }

    const api = {
      render,
      // Kapplöpningen mäter sin bredd, så den ritas om när Pro visas och när fönstret ändras
      show() { const pot = load(), P = price(), st = pot ? standing(pot, P) : null; drawRace(pot, st); intro(st); },
      marks() { const p = load(); return p ? p.trades.map((t) => ({ date: t.date, side: t.side })) : []; },
      onMarks(fn) { marksCb = fn; }
    };
    let timer;
    window.addEventListener("resize", () => { clearTimeout(timer); timer = setTimeout(() => { if (!$("view-pro").hidden) api.show(); }, 150); });
    render();
    return api;
  }

  window.WalterArena = { mount };
})();
