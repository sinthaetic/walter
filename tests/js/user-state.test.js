// Tester för js/user-state.js (användarens Walter i webbläsaren: lagring, kopia, WALTER_STATE).
const WU = () => window.WalterUser;

// Liten marknadsfil i samma form som data/market.js (fetcher/walter_public.py).
function fakeMarket() {
  const rules = {
    parkeraAtRed: 7, wakeAtRed: 5, modes: { buyAtRed: 2, buyLittleAtRed: 4, littleShare: 0.5 },
    paper: { minTradePct: 2 }, maxInvested: 0.75, minCash: 0.25, caps: { BTC: 0.35, ETH: 0.2, GOLD: 0.2 },
    unlock: { early: { days: 15, gainPct: 20, maxDd: 8, minGreen: 7 }, normal: { days: 30, gainPct: 10, maxDd: 12 } },
    ethMaxRed: 4, gold: { vixAbove: 20, spxBelowMa: true, allowedWhenParked: true },
    withdrawalFees: { takerPct: 0.4, slippagePct: 0.2, sepaEur: 1, fxPct: 1 }
  };
  const lamps = [];
  for (let i = 0; i < 10; i++) lamps.push({ id: "l" + i, name: "Lampa " + i, rule: "r", status: i < 3 ? "red" : "green", value: "1", asOf: "2026-10-22" });
  const px = { BTC: 800000, ETH: 22000, GOLD: 40000 };
  return {
    now: { date: "2026-10-22", fetchedAt: "2026-10-22T23:06:56", ready: true, red: 3, mode: "NORMAL", lamps, px,
      usdsek: { value: 10, asOf: "2026-10-22", source: "Riksbanken" }, eursek: { value: 11, asOf: "2026-10-22", source: "Riksbanken" },
      ethBtcAbove30dMa: false, btcLong: true, vix: 19, spxBelowMa: true, rules, version: "9.99",
      levels: { 1: { asset: "BTC", name: "Bitcoin" }, 2: { asset: "ETH", name: "Ethereum" }, 3: { asset: "GULD", name: "Guld", gainPct: 50, maxDd: 12 } } },
    log: [{ date: "2026-10-21", ready: true, red: 4, px }, { date: "2026-10-22", ready: true, red: 3, px }]
  };
}

// Byter window.localStorage mot något annat under fn och lägger tillbaka det efteråt.
async function withStorage(desc, fn) {
  const old = Object.getOwnPropertyDescriptor(window, "localStorage");
  Object.defineProperty(window, "localStorage", Object.assign({ configurable: true }, desc));
  try { await fn(); } finally { Object.defineProperty(window, "localStorage", old); }
}

test("create_shape", () => {
  const saved = window.WALTER_MARKET;
  try {
    delete window.WALTER_MARKET;
    eq(WU().create(10000, "kraken", "2026-10-23"), {
      v: 1, startDate: "2026-10-23", exchangeId: "kraken", start: 10000, level: 1, mode: "AVVAKTAR", lastDay: "2026-10-23",
      portfolio: { start: 10000, value: 10000, peak: 10000, holdings: { BTC: 0, ETH: 0, GOLD: 0, CASH: 10000 }, positions: {},
        firstTrade: null, history: [{ date: "2026-10-23", value: 10000, cash: 10000, note: "start", flow: 10000 }] },
      journal: [], trades: []
    });
    // Finns en marknadslogg börjar räkningen efter dess senaste dag (gamla dagar spelas aldrig upp).
    window.WALTER_MARKET = fakeMarket();
    eq(WU().create(5000, "kraken", "2026-10-23").lastDay, "2026-10-22");
  } finally { window.WALTER_MARKET = saved; }
});

test("export_import_roundtrip", async () => {
  const u = WU().create(25000, "safello", "2026-10-23");
  u.journal.push({ date: "2026-10-23", mode: "AVVAKTAR", red: 5, plain: "Jag avvaktar.", facts: [] });
  const blob = WU().exportFile(u);
  if (!(blob instanceof Blob)) throw new Error("ingen Blob");
  if (!/^walter-kopia-\d{4}-\d{2}-\d{2}\.json$/.test(blob.name || "")) throw new Error("filnamn: " + blob.name);
  eq(WU().importText(await blob.text()), u);
});

test("import_rejects_garbage", () => {
  for (const text of ["{}", "hej", '{"v":2}', "null"]) {
    let msg = null;
    try { WU().importText(text); } catch (e) { msg = e.message; }
    eq(msg, "Det här är ingen Walter-kopia");
  }
});

test("storage_blocked", async () => {
  const u = WU().create(10000, "kraken", "2026-10-23");
  const boom = () => { throw new Error("SecurityError"); };
  // Lagringen finns men kastar på varje anrop
  await withStorage({ value: { getItem: boom, setItem: boom, removeItem: boom } }, () => {
    eq(WU().save(u), false);
    eq(WU().load(), null);
    eq(WU().storageOk(), false);
  });
  // Redan åtkomsten kastar (blockerade kakor i vissa webbläsare)
  await withStorage({ get: boom }, () => {
    eq(WU().save(u), false);
    eq(WU().load(), null);
    eq(WU().storageOk(), false);
  });
});

test("save_load_roundtrip", () => {
  let prev = null;
  try { prev = localStorage.getItem("walter.user"); } catch (e) { /* blockerad */ }
  try {
    const u = WU().create(12000, "kraken", "2026-10-23");
    eq(WU().storageOk(), true);
    eq(WU().save(u), true);
    eq(WU().load(), u);
    localStorage.setItem("walter.user", "trasigt{");
    eq(WU().load(), null);
  } finally {
    if (prev === null) localStorage.removeItem("walter.user"); else localStorage.setItem("walter.user", prev);
  }
});

test("toState_has_app_fields", () => {
  const u = WU().create(10000, "kraken", "2026-10-22");
  const before = JSON.stringify(u);
  const S = WU().toState(u, fakeMarket(), "2026-10-22");
  for (const k of ["version", "startDate", "updatedAt", "fetchedAt", "mode", "level", "levels", "portfolio", "journal",
    "lamps", "lampScore", "market", "rules", "k4", "proposal"]) {
    if (!(k in S)) throw new Error("saknar " + k);
  }
  eq(S.lampScore.total, 10);
  eq(S.lampScore.red, 3);
  eq(S.lampScore.source, "data");
  eq(S.lamps.length, 10);
  eq(S.k4, []);
  eq(S.mode, "AVVAKTAR");
  eq(S.startDate, "2026-10-22");
  eq(S.proposal.ready, true);
  eq(S.proposal.mode, "NORMAL");
  // Appen läser de här fälten direkt (m.vix.value, m.spx.belowMa, m.btc.value)
  eq(S.market.vix.value, 19);
  eq(S.market.spx.belowMa, true);
  eq(S.market.btc.value, 80000);
  eq(S.market.usdsek.value, 10);
  // Version och nivåer kommer från marknadsfilen, inte från en egen kopia
  eq(S.version, "9.99");
  eq(S.levels[3], { asset: "GULD", name: "Guld", gainPct: 50, maxDd: 12 });
  eq(S.levels[1].since, "2026-10-22");
  eq("LEVELS" in WU(), false);
  // Användarens Walter ändras aldrig av att visas
  eq(JSON.stringify(u), before);
});

test("toState_waits_without_data", () => {
  const m = fakeMarket();
  m.now.ready = false;
  m.now.px = { BTC: null, ETH: null, GOLD: null };
  m.now.vix = null;
  const S = WU().toState(WU().create(10000, "kraken", "2026-10-22"), m);
  eq(S.lampScore.source === "data", false);
  eq(S.proposal.ready, false);
  eq(S.market.btc.value, null);
  eq(S.market.vix.value, null);
});

test("toState_waits_without_levels", () => {
  const m = fakeMarket();
  delete m.now.levels;
  const S = WU().toState(WU().create(10000, "kraken", "2026-10-22"), m);
  eq(S.proposal.ready, false);
  eq(S.levels, {});
});

// En kopia med trasiga eller elaka poster får aldrig läsas in (den kunde låsa appen eller skriva in HTML).
test("import_rejects_bad_shapes", () => {
  const good = () => {
    const u = WU().create(10000, "kraken", "2026-10-23");
    u.journal.push({ date: "2026-10-23", mode: "AVVAKTAR", red: 5, plain: "Jag avvaktar.", facts: ["5/10 röda"] });
    return u;
  };
  eq(WU().importText(JSON.stringify(good())).start, 10000); // utgångsläget är giltigt
  const bad = [
    (u) => { u.journal = [{}]; },
    (u) => { u.journal[0].red = "<img src=x onerror=alert(1)>"; },
    (u) => { u.journal[0].date = 20261023; },
    (u) => { u.journal[0].date = "<b>"; },
    (u) => { u.journal[0].facts = [1]; },
    (u) => { u.journal[0].trades = [{ asset: "BTC", side: "köp", sek: "x" }]; },
    (u) => { u.portfolio.history.push({ date: "2026-10-24", value: NaN }); },
    (u) => { u.portfolio.history[0].date = 5; },
    (u) => { u.portfolio.history[0].note = {}; },
    (u) => { u.portfolio.peak = "1"; },
    (u) => { u.portfolio.holdings.BTC = null; },
    (u) => { u.portfolio.positions.BTC = { units: "1", costSek: 0 }; },
    (u) => { u.level = "<i>"; },
    (u) => { u.startDate = "igår"; },
    (u) => { u.trades = [{ date: "2026-10-23" }]; }
  ];
  bad.forEach((f, i) => {
    const u = good();
    f(u);
    // JSON gör NaN till null – båda ska avvisas
    let msg = null;
    try { WU().importText(JSON.stringify(u)); } catch (e) { msg = e.message; }
    if (msg !== "Det här är ingen Walter-kopia") throw new Error("fall " + i + " avvisades inte");
  });
});

// En ny Walter gör sitt första drag samma dag: dagens rad räknas och genomförs, dagen spelas inte upp igen.
test("first_move_on_creation_day", () => {
  const saved = window.WALTER_MARKET;
  try {
    const m = fakeMarket();
    window.WALTER_MARKET = m;
    const u = WU().create(100000, "kraken", "2026-10-22");
    const entry = WU().firstMove(u, m, "2026-10-22");
    if (!entry) throw new Error("inget första drag");
    eq(u.mode, "NORMAL"); // 3 röda → Köper lite
    eq(u.journal.length, 1);
    eq(u.journal[0].date, "2026-10-22");
    if (!(u.portfolio.holdings.BTC > 0)) throw new Error("köpte ingen bitcoin");
    if (!/^Jag köpte bitcoin/.test(entry.plain)) throw new Error("inte Walters röst: " + entry.plain);
    eq(u.lastDay, "2026-10-22");
    // Ikapp-räkningen samma dag gör inget mer
    const before = JSON.stringify(u);
    window.WalterEngine.catchUp(u, m.log, m.now.rules, m.now.levels, window.WALTER_EXCHANGES.find((x) => x.id === "kraken"));
    eq(JSON.stringify(u), before);
    // Kopian av en Walter efter första draget går att läsa in
    eq(WU().importText(JSON.stringify(u)).journal.length, 1);
    // Lamporna inte klara men priserna finns: autopiloten gör första draget, läget (vädret) står kvar
    const m2 = fakeMarket(); m2.now.ready = false;
    const u2 = WU().create(100000, "kraken", "2026-10-22");
    if (!WU().firstMove(u2, m2, "2026-10-22")) throw new Error("inget drag på priserna");
    eq(u2.mode, "AVVAKTAR");
    if (!(u2.portfolio.holdings.BTC > 0)) throw new Error("köpte ingen bitcoin");
    // Utan priser väntar Walter
    const m3 = fakeMarket(); m3.now.ready = false; m3.now.px = { BTC: null, ETH: null, GOLD: null };
    const u3 = WU().create(100000, "kraken", "2026-10-22");
    eq(WU().firstMove(u3, m3, "2026-10-22"), null);
    eq(u3.journal.length, 0);
  } finally { window.WALTER_MARKET = saved; }
});

// Gammal marknadsdata räknas aldrig som färsk: varken första draget eller förslaget
test("stale_market_waits", () => {
  const saved = window.WALTER_MARKET;
  try {
    const m = fakeMarket();
    window.WALTER_MARKET = m;
    // fetchedAt 2026-10-22, lampMaxAgeDays.default saknas → 4 dagar
    eq(WU().isFresh(m.now, "2026-10-26"), true);
    eq(WU().isFresh(m.now, "2026-10-27"), false);
    m.now.rules.lampMaxAgeDays = { default: 1 };
    eq(WU().isFresh(m.now, "2026-10-24"), false);
    eq(WU().isFresh(Object.assign({}, m.now, { fetchedAt: null }), "2026-10-22"), false);
    delete m.now.rules.lampMaxAgeDays;

    const u = WU().create(100000, "kraken", "2026-10-22");
    eq(WU().firstMove(u, m, "2026-10-30"), null);
    eq(u.journal.length, 0);
    const S = WU().toState(u, m, "2026-10-30");
    eq(S.proposal.ready, false);
    eq(S.proposal.plain, "Walter väntar på färsk marknadsdata.");
    // Färsk data samma dag: förslaget räknas
    eq(WU().toState(u, m, "2026-10-22").proposal.ready, true);
  } finally { window.WALTER_MARKET = saved; }
});

test("first_move_refuses_market_before_start", () => {
  const saved = window.WALTER_MARKET;
  try {
    const m = fakeMarket();
    window.WALTER_MARKET = m;
    const u = WU().create(100000, "kraken", "2026-10-23");
    eq(WU().firstMove(u, m, "2026-10-23"), null);
    eq(u.journal.length, 0);
    eq(u.portfolio.holdings.CASH, 100000);
  } finally { window.WALTER_MARKET = saved; }
});

// Upplåsningen av ägarens Walter (introt och Inställningar använder samma funktion)
test("unlock_owner_saves_key_only_on_success", async () => {
  const env = await (await fetch("../fixtures/vault-sample.enc")).json();
  const ok = async () => ({ ok: true, json: async () => env });
  const store = {};
  const fake = { setItem: (k, v) => { store[k] = v; }, getItem: (k) => store[k] || null, removeItem: (k) => { delete store[k]; } };
  await withStorage({ value: fake }, async () => {
    eq(await WU().unlockOwner("fel", ok), { ok: false, msg: "Koden stämde inte." });
    eq("walter.ownerKey" in store, false);
    eq(await WU().unlockOwner("TEST-KOD", async () => ({ ok: false })), { ok: false, msg: "Jag når inte ägarfilen just nu." });
    eq(await WU().unlockOwner("TEST-KOD", async () => { throw new Error("nät"); }), { ok: false, msg: "Jag når inte ägarfilen just nu." });
    eq("walter.ownerKey" in store, false);
    eq(await WU().unlockOwner("TEST-KOD", ok), { ok: true, msg: "" });
    eq(store["walter.ownerKey"], "TEST-KOD");
  });
  await withStorage({ get() { throw new Error("blockerad"); } }, async () => {
    eq(await WU().unlockOwner("TEST-KOD", ok), { ok: false, msg: "Koden stämde, men din webbläsare låter mig inte spara den." });
  });
});
