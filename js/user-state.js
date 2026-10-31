// Användarens Walter i webbläsaren: lagring (bara den här webbläsaren, nyckel walter.user, v:1),
// kopia till/från fil och bygget av WALTER_STATE som js/app.js renderar. Inga DOM-anrop.
// Ägarens data finns aldrig här – den kommer från data/state.js eller data/owner.enc.
(function (root) {
  "use strict";

  const KEY = "walter.user";
  const OWNER_KEY = "walter.ownerKey";
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
  // Kopian kommer utifrån (en fil, eller localStorage som någon kan ha ändrat). Varje fält som appen ritar
  // eller räknar med kontrolleras, så att en trasig eller elak kopia aldrig kan låsa appen eller skriva in HTML.
  const fin = (v) => typeof v === "number" && Number.isFinite(v);
  const finOrNull = (v) => v === null || fin(v);
  const isDate = (v) => typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v);
  const isStr = (v) => typeof v === "string";
  const optional = (o, k, ok) => !(k in o) || o[k] === undefined || ok(o[k]);
  const allOk = (a, ok) => Array.isArray(a) && a.every(ok);
  const tradeOk = (t) => isObj(t) && isStr(t.asset) && isStr(t.side) && fin(t.sek);
  const journalOk = (j) => isObj(j) && isDate(j.date) && (j.mode === null || isStr(j.mode)) &&
    finOrNull(j.red) && isStr(j.plain) && allOk(j.facts, isStr) && optional(j, "trades", (t) => allOk(t, tradeOk));
  const historyOk = (h) => isObj(h) && isDate(h.date) && fin(h.value) && optional(h, "cash", finOrNull) &&
    optional(h, "note", isStr) && optional(h, "flow", fin) && optional(h, "test", (v) => typeof v === "boolean") &&
    optional(h, "month", (v) => typeof v === "string" && /^\d{4}-\d{2}$/.test(v));
  // Månadssparande {monthlySek ≥ 0, day 1..28, since} och mål {name, amountSek > 0, date}. Båda är valfria
  // (äldre kopior saknar dem). Målet får vara null (inget mål).
  // Riktiga kalenderdatum (som isIso i js/engine.js): 2027-02-30 godtas inte.
  const isRealDate = (v) => isDate(v) && !isNaN(Date.parse(v + "T00:00:00Z")) &&
    new Date(Date.parse(v + "T00:00:00Z")).toISOString().slice(0, 10) === v;
  // since får inte ligga före Walters start (då skulle sparande sättas in för tid innan Walter fanns)
  const savingsOk = (s, start) => isObj(s) && fin(s.monthlySek) && s.monthlySek >= 0 && s.monthlySek <= 1e9 &&
    Number.isInteger(s.day) && s.day >= 1 && s.day <= 28 &&
    optional(s, "since", (v) => isRealDate(v) && (!isDate(start) || v >= start));
  const goalOk = (g) => g === null || (isObj(g) && isStr(g.name) && g.name.length <= 60 && fin(g.amountSek) &&
    g.amountSek > 0 && g.amountSek <= 1e10 && isRealDate(g.date));
  const positionOk = (p) => isObj(p) && fin(p.units) && fin(p.costSek) && optional(p, "since", isDate);
  const userTradeOk = (t) => isObj(t) && isDate(t.date) && isStr(t.asset) && isStr(t.side) &&
    fin(t.units) && fin(t.priceSek) && fin(t.sek) && fin(t.feeSek);
  function importText(text) {
    let u;
    try { u = JSON.parse(text); } catch (e) { throw new Error(NOT_A_COPY); }
    const pf = isObj(u) ? u.portfolio : null;
    const ok = isObj(u) && u.v === 1 && isDate(u.startDate) && isDate(u.lastDay) &&
      isStr(u.exchangeId) && fin(u.start) && [1, 2, 3].includes(u.level) && isStr(u.mode) &&
      allOk(u.journal, journalOk) && allOk(u.trades, userTradeOk) &&
      isObj(pf) && fin(pf.start) && fin(pf.value) && fin(pf.peak) &&
      isObj(pf.holdings) && Object.values(pf.holdings).every(fin) && fin(pf.holdings.CASH) &&
      isObj(pf.positions) && Object.values(pf.positions).every(positionOk) &&
      (pf.firstTrade === null || pf.firstTrade === undefined || isDate(pf.firstTrade)) &&
      allOk(pf.history, historyOk) && optional(u, "savings", (s) => savingsOk(s, u.startDate)) && optional(u, "goal", goalOk) &&
      optional(u, "pendingDeposit", (v) => fin(v) && v >= 0 && v <= 1e10);
    if (!ok) throw new Error(NOT_A_COPY);
    return u;
  }

  // ---------- Månadssparande och mål (ändras under Inställningar) ----------
  // since = från vilken dag sparandet räknas. Sätts när sparandet slås på (från 0), så att ett nytt sparande
  // aldrig sätter in pengar för månader innan det fanns. Ett ändrat belopp eller dag behåller since.
  function setSavings(user, monthlySek, day, iso) {
    const amt = Math.round(Number(monthlySek));
    const d = Math.round(Number(day));
    if (!Number.isFinite(amt) || amt < 0 || amt > 1e9 || !(d >= 1 && d <= 28)) return false;
    const was = user.savings && user.savings.monthlySek > 0 ? user.savings : null;
    let since = was && isRealDate(was.since) ? was.since : (iso || today());
    if (isDate(user.startDate) && since < user.startDate) since = user.startDate;
    user.savings = { monthlySek: amt, day: d, since };
    return true;
  }
  function setGoal(user, goal) {
    if (goal === null) { user.goal = null; return true; }
    const g = { name: String(goal.name || "").trim().slice(0, 60) || "Mitt mål", amountSek: Math.round(Number(goal.amountSek)), date: goal.date };
    if (!goalOk(g)) return false;
    user.goal = g;
    return true;
  }

  // ---------- Färsk marknadsdata ----------
  // Samma gräns som lamporna (rules.lampMaxAgeDays.default, annars 4 dagar), räknat mot webbläsarens datum.
  // Okänt hämtdatum räknas som gammalt – gammal data får aldrig se färsk ut.
  function isFresh(now, day) {
    const fetched = now && typeof now.fetchedAt === "string" ? now.fetchedAt.slice(0, 10) : null;
    if (!isDate(fetched) || !isDate(day)) return false;
    const ages = (now.rules && now.rules.lampMaxAgeDays) || {};
    const max = fin(ages.default) ? ages.default : 4;
    const age = (Date.parse(day + "T00:00:00Z") - Date.parse(fetched + "T00:00:00Z")) / 86400000;
    return age <= max;
  }

  // ---------- Walters första drag ----------
  // En ny Walter handlar samma dag han skapas: dagens marknadsrad (market.now) räknas och genomförs direkt,
  // så att användaren ser Walters första drag. lastDay är oförändrad (loggens senaste dag), så dagen spelas
  // aldrig upp två gånger. Returnerar journalposten, eller null om något saknas (då väntar Walter).
  function firstMove(user, market, day) {
    const now = market && market.now;
    const exchange = (root.WALTER_EXCHANGES || []).find((x) => x.id === user.exchangeId) || null;
    // Autopiloten behöver bara priserna (propose säger ready:false utan pris); lamp-strategin en klar rad.
    const autoOk = !!root.WalterEngine && !!now && !!now.rules && root.WalterEngine.strategyOf(now.rules) === "autopilot";
    if (!now || !(now.ready || autoOk) || !now.rules || !now.levels || !exchange || !isDate(now.date) || !root.WalterEngine) return null;
    // Gammal marknadsdata, eller en marknadsdag före starten, är aldrig "dagens" drag.
    if (!isFresh(now, day || today()) || now.date < user.startDate) return null;
    const prop = root.WalterEngine.propose(user, now, now.rules, exchange);
    if (!prop.ready) return null;
    const entry = root.WalterEngine.apply(user, prop, now.date);
    // Dagen är räknad: ligger loggen efter får den aldrig spela upp samma dag igen.
    if (now.date > user.lastDay) user.lastDay = now.date;
    return entry;
  }

  // ---------- Sätt in pengar (Inställningar och översikten) ----------
  // Låtsasinsättning: hela kronor 100–100 000 000 (WalterIntro.parseAmount). Färsk marknadsdata: Walter köper direkt
  // med samma kod som månadssparandet (WalterEngine.proposeDeposit). Inte färsk: pengarna läggs som kontanter och
  // beloppet sparas i pendingDeposit, så att Walter köper för dem nästa gång priserna är färska (investPending).
  const DEPOSIT_RANGE = "Skriv ett belopp i hela kronor, minst 100 kr och högst 100 000 000 kr.";
  function deposit(user, text, market, day) {
    const E = root.WalterEngine, parse = root.WalterIntro && root.WalterIntro.parseAmount;
    const sek = parse && typeof text === "string" ? parse(text) : null;
    if (sek === null) return { ok: false, msg: DEPOSIT_RANGE };
    const now = market && market.now;
    const exchange = (root.WALTER_EXCHANGES || []).find((x) => x.id === user.exchangeId) || null;
    if (!E || !now || !now.rules || !exchange) return { ok: false, msg: "Jag väntar på marknadsdata. Försök igen om en stund." };
    const iso = day || today();
    const fresh = isFresh(now, iso) && isDate(now.date) && now.date >= user.startDate;
    const prop = E.proposeDeposit(user, now, now.rules, exchange, sek, fresh ? {} : { stale: true });
    // Datum i Walters egen tidslinje (marknadsdagar), aldrig webbläsarens: historiken håller datumordning
    const date = [user.lastDay, now.date].filter(isDate).sort().pop() || iso;
    const entry = E.applyDeposit(user, prop, date);
    if (prop.deposit.stale) user.pendingDeposit = E.round((user.pendingDeposit || 0) + sek, 2);
    return { ok: true, sek, entry, msg: entry.plain };
  }
  // Köp för en insättning som gjordes när marknadsdatan inte var färsk. Returnerar journalposten eller null.
  function investPending(user, market, day) {
    const E = root.WalterEngine, now = market && market.now;
    const exchange = (root.WALTER_EXCHANGES || []).find((x) => x.id === user.exchangeId) || null;
    const sek = user.pendingDeposit;
    if (!(sek > 0) || !E || !now || !now.rules || !exchange || !isDate(now.date)) return null;
    if (!isFresh(now, day || today()) || now.date < user.startDate) return null;
    delete user.pendingDeposit;
    if (E.strategyOf(now.rules) !== "autopilot") return null;
    const prop = E.proposeDeposit(user, now, now.rules, exchange, sek, { pending: true });
    // Inget att köpa (t.ex. har Walters vanliga koll redan investerat pengarna): ingen journalpost
    if (!prop.trades.length && !prop.deposit.waiting.length) return null;
    return E.applyDeposit(user, prop, now.date);
  }

  // ---------- Lås upp ägarens Walter ----------
  // Delas av introt och Inställningar. Bara en misslyckad dekryptering är "fel kod" – når jag inte filen
  // kan koden vara rätt. Koden sparas (walter.ownerKey) först när den har låst upp data/owner.enc.
  async function unlockOwner(code, fetchFn) {
    const get = fetchFn || ((u, o) => root.fetch(u, o));
    let env = null;
    try {
      const res = await get("data/owner.enc", { cache: "no-store" });
      if (res && res.ok) env = await res.json();
    } catch (e) { env = null; }
    if (!env) return { ok: false, msg: "Jag når inte ägarfilen just nu." };
    try { await root.WalterVault.decrypt(env, code); } catch (e) { return { ok: false, msg: "Koden stämde inte." }; }
    try { root.localStorage.setItem(OWNER_KEY, code); } catch (e) {
      return { ok: false, msg: "Koden stämde, men din webbläsare låter mig inte spara den." };
    }
    return { ok: true, msg: "" };
  }
  // Ägaren glömmer koden på den här enheten
  function forgetOwner() {
    try { root.localStorage.removeItem(OWNER_KEY); return true; } catch (e) { return false; }
  }

  // ---------- WALTER_STATE för appen ----------
  // Samma form som ägarens state.js. Allt kommer från användarens Walter + marknadsfilen; saknas något är det null.
  function toState(user, market, browserDay) {
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
    } else if (!isFresh(now, browserDay || today())) {
      proposal = { ready: false, red: null, mode: user.mode, currentMode: user.mode, trades: [],
        valueSek: null, missing: [], plain: "Walter väntar på färsk marknadsdata." };
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
      // Användarens månadssparande och mål (samma fält som ägarens state.json)
      savings: user.savings ? copy(user.savings) : null,
      goal: user.goal ? copy(user.goal) : null,
      proposal
    };
  }

  root.WalterUser = { load, save, storageOk, create, isFresh, firstMove, exportFile, importText, toState, today, unlockOwner, forgetOwner,
    setSavings, setGoal, deposit, investPending };
})(typeof window !== "undefined" ? window : this);
