// Uppstart: avgör vem som tittar och startar appen (js/app.js) med ett WALTER_STATE-objekt.
// 1) data/state.js finns (bara lokalt) → ägaren. 2) walter.ownerKey finns → dekryptera data/owner.enc → ägaren.
// 3) Landningen om man inte gått in i den här fliken. 4) GÅ IN → användarens Walter (räknas ikapp) eller introt.
(function () {
  "use strict";

  const U = window.WalterUser;
  const OWNER_KEY = "walter.ownerKey";
  const ls = {
    get(k) { try { return window.localStorage.getItem(k); } catch (e) { return null; } },
    del(k) { try { window.localStorage.removeItem(k); } catch (e) { /* lagring blockerad */ } }
  };
  const entered = () => { try { return window.sessionStorage.getItem("walterEntered") === "1"; } catch (e) { return false; } };

  // Ett kort besked överst på sidan (vanliga ord, ingen siffervägg)
  function note(text) {
    const main = document.querySelector("main.page");
    if (!main) return;
    const box = document.createElement("div");
    box.className = "panel boot-note";
    box.setAttribute("role", "status");
    const p = document.createElement("p");
    p.className = "plain";
    p.textContent = text;
    box.appendChild(p);
    main.insertBefore(box, main.firstChild);
  }
  // Inget att visa än: dölj översikten och säg varför
  function placeholder(text) {
    document.querySelectorAll("[data-page]").forEach((s) => { s.hidden = true; });
    note(text);
  }

  const start = (S, ctx) => window.WalterApp.start(S, Object.assign({ exchange: null, catchUpText: "", storageOk: U.storageOk() }, ctx));
  const exchangeOf = (id) => (window.WALTER_EXCHANGES || []).find((x) => x.id === id) || null;

  // Användarens Walter: spela upp missade loggdagar, spara, visa
  function startUser(user) {
    const market = window.WALTER_MARKET;
    if (!market || !market.now) { placeholder("Walter väntar på marknadsdata. Försök igen om en stund."); return; }
    const now = market.now;
    const exchange = exchangeOf(user.exchangeId);
    let catchUpText = "";
    if (exchange && now.rules) {
      const levels = now.levels || U.LEVELS;
      const res = window.WalterEngine.catchUp(user, market.log || [], now.rules, levels, exchange);
      catchUpText = window.WalterEngine.summary(res.events);
      U.save(user);
    }
    start(U.toState(user, market), { who: "user", exchange, catchUpText });
  }

  function enter() {
    const user = U.load();
    if (user) { startUser(user); return; }
    if (typeof WalterIntro !== "undefined") {
      WalterIntro.start((u) => { U.save(u); startUser(u); });
      return;
    }
    placeholder("Walter förbereds…");
  }

  async function boot() {
    if (window.WALTER_STATE) { start(window.WALTER_STATE, { who: "owner-local" }); return; }

    const key = ls.get(OWNER_KEY);
    if (key) {
      let env = null;
      try {
        const res = await fetch("data/owner.enc", { cache: "no-store" });
        if (res.ok) env = await res.json();
      } catch (e) { env = null; }
      if (env) {
        try {
          const o = await window.WalterVault.decrypt(env, key);
          start(Object.assign({}, o.state, o.notis ? { notis: o.notis } : {}), { who: "owner" });
          return;
        } catch (e) {
          ls.del(OWNER_KEY);
          note("Koden stämde inte. Du ser den vanliga appen.");
        }
      } else {
        // Nätet eller filen svarar inte: koden kan vara rätt, så den sparas kvar till nästa gång.
        note("Jag når inte ägarfilen just nu. Du ser den vanliga appen.");
      }
    }

    if (!entered() && typeof WalterLanding !== "undefined") { WalterLanding.show(window.WALTER_MARKET, enter); return; }
    enter();
  }

  boot();
})();
