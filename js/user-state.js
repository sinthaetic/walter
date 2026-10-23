// Användarens Walter i webbläsaren: lagring (bara den här webbläsaren, nyckel walter.user, v:1),
// kopia till/från fil och bygget av WALTER_STATE som js/app.js renderar. Inga DOM-anrop.
// Ägarens data finns aldrig här – den kommer från data/state.js eller data/owner.enc.
(function (root) {
  "use strict";

  const KEY = "walter.user";
  const LAMPS = 10;
  const NOT_A_COPY = "Det här är ingen Walter-kopia";

  const copy = (o) => JSON.parse(JSON.stringify(o));
  const pad = (n) => String(n).padStart(2, "0");
  // Dagens datum i webbläsarens tidszon, "YYYY-MM-DD"
  function today() {
    const d = new Date();
    return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
  }

  // ---------- Lagring (blockerad lagring kastar – även själva åtkomsten kan kasta) ----------
  function storageOk() {
    try {
      const ls = root.localStorage;
      ls.setItem("walter.test", "1");
      ls.removeItem("walter.test");
      return true;
    } catch (e) { return false; }
  }
  function load() {
    try {
      const text = root.localStorage.getItem(KEY);
      return text ? importText(text) : null;
    } catch (e) { return null; }
  }
  function save(user) {
    try { root.localStorage.setItem(KEY, JSON.stringify(user)); return true; } catch (e) { return false; }
  }

  // ---------- Ny Walter ----------
  // Varje insättning är en historikrad med flow (motorns kontrakt), även startbeloppet.
  // lastDay = marknadsloggens senaste dag, så att dagar före starten aldrig spelas upp.
  function create(amountSek, exchangeId, day) {
    const log = (root.WALTER_MARKET && root.WALTER_MARKET.log) || [];
    const dates = log.map((r) => r && r.date).filter((d) => typeof d === "string").sort();
    const start = amountSek;
    return {
      v: 1, startDate: day, exchangeId, start, level: 1, mode: "AVVAKTAR",
      lastDay: dates.length ? dates[dates.length - 1] : day,
      portfolio: { start, value: start, peak: start, holdings: { BTC: 0, ETH: 0, GOLD: 0, CASH: start }, positions: {},
        firstTrade: null, history: [{ date: day, value: start, cash: start, note: "start", flow: start }] },
      journal: [], trades: []
    };
  }

  // ---------- Kopia ----------
  function exportFile(user) {
    return new File([JSON.stringify(user, null, 2)], `walter-kopia-${today()}.json`, { type: "application/json" });
  }
  const isObj = (o) => o !== null && typeof o === "object" && !Array.isArray(o);
  function importText(text) {
    let u;
    try { u = JSON.parse(text); } catch (e) { throw new Error(NOT_A_COPY); }
    const pf = isObj(u) ? u.portfolio : null;
    const ok = isObj(u) && u.v === 1 && typeof u.startDate === "string" && typeof u.lastDay === "string" &&
      typeof u.exchangeId === "string" && Number.isFinite(u.start) && Number.isFinite(u.level) && typeof u.mode === "string" &&
      Array.isArray(u.journal) && Array.isArray(u.trades) &&
      isObj(pf) && Number.isFinite(pf.value) && isObj(pf.holdings) && Number.isFinite(pf.holdings.CASH) &&
      isObj(pf.positions) && Array.isArray(pf.history);
    if (!ok) throw new Error(NOT_A_COPY);
    return u;
  }

  // ---------- WALTER_STATE för appen ----------
  // Samma form som ägarens state.js. Allt kommer från användarens Walter + marknadsfilen; saknas något är det null.
  function toState(user, market) {
    const now = (market && market.now) || {};
    const day = now.date || user.lastDay;
    const usdsek = now.usdsek || null;
    const fx = usdsek && usdsek.value ? usdsek.value : null;
    const px = now.px || {};
    const exchange = (root.WALTER_EXCHANGES || []).find((x) => x.id === user.exchangeId) || null;
    // Nivåerna (och versionen) kommer från marknadsfilen. Saknas de väntar Walter, precis som utan regler.
    const levels = copy(now.levels || {});
    if (levels[1]) levels[1] = Object.assign({}, levels[1], { unlocked: true, since: user.startDate });

    let proposal;
    if (!exchange) {
      proposal = { ready: false, red: now.red == null ? null : now.red, mode: user.mode, currentMode: user.mode, trades: [],
        valueSek: null, missing: [], plain: "Jag hittar inte din börs i listan, så jag räknar inget förslag." };
    } else if (!now.rules || !now.levels) {
      proposal = { ready: false, red: null, mode: user.mode, currentMode: user.mode, trades: [],
        valueSek: null, missing: [], plain: "Jag väntar på marknadsdata innan jag gör något." };
    } else {
      proposal = root.WalterEngine.propose(copy(user), now, now.rules, exchange);
    }
    proposal.asOf = day;

    return {
      version: now.version || null,
      startDate: user.startDate,
      updatedAt: day,
      fetchedAt: now.fetchedAt || null,
      mode: user.mode,
      level: user.level,
      levels,
      portfolio: copy(user.portfolio),
      journal: copy(user.journal),
      lamps: copy(now.lamps || []),
      lampScore: { red: now.red == null ? null : now.red, total: LAMPS, asOf: day, source: now.ready ? "data" : "väntar" },
      market: {
        asOf: day,
        // Bitcoin i USD = SEK-priset delat med samma USDSEK som hämtaren räknade med. Saknas något: null.
        btc: { value: px.BTC && fx ? Math.round(px.BTC / fx) : null, unit: "usd", asOf: day },
        usdsek,
        eursek: now.eursek || null,
        vix: { value: now.vix == null ? null : now.vix, asOf: day },
        spx: { value: null, belowMa: now.spxBelowMa == null ? null : now.spxBelowMa, asOf: day },
        ethBtcAbove30dMa: now.ethBtcAbove30dMa == null ? null : now.ethBtcAbove30dMa,
        btcLong: now.btcLong == null ? null : now.btcLong
      },
      rules: copy(now.rules || {}),
      k4: [],
      proposal
    };
  }

  root.WalterUser = { load, save, storageOk, create, exportFile, importText, toState, today };
})(typeof window !== "undefined" ? window : this);
