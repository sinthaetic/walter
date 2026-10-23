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
      ethBtcAbove30dMa: false, btcLong: true, vix: 19, spxBelowMa: true, rules },
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
  const S = WU().toState(u, fakeMarket());
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
