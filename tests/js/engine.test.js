// Tester för js/engine.js. Paritetsfallen räknas av Python (tests/make_fixtures.py → engine-cases.json).
const E = () => window.WalterEngine;
const sortKeys = (v) => Array.isArray(v) ? v.map(sortKeys)
  : v && typeof v === "object" ? Object.keys(v).sort().reduce((o, k) => (o[k] = sortKeys(v[k]), o), {}) : v;
const same = (a, b) => eq(sortKeys(a), sortKeys(b));
const clone = (x) => JSON.parse(JSON.stringify(x));
let _fx = null;
const fixtures = async () => _fx || (_fx = await (await fetch("../fixtures/engine-cases.json")).json());

const RULES = { parkeraAtRed: 7, wakeAtRed: 5, modes: { buyAtRed: 2, buyLittleAtRed: 4, littleShare: 0.5 },
  paper: { minTradePct: 2 }, minCash: 0.25, caps: { BTC: 0.35, ETH: 0.2, GOLD: 0.2 },
  unlock: { early: { days: 15, gainPct: 20, maxDd: 8, minGreen: 7 }, normal: { days: 30, gainPct: 10, maxDd: 12 } },
  ethMaxRed: 4, gold: { vixAbove: 20, spxBelowMa: true, allowedWhenParked: true },
  withdrawalFees: { takerPct: 0.4, slippagePct: 0.2, fxPct: 1 } };
const LEVELS = { 3: { gainPct: 50, maxDd: 12 } };
const EX = { id: "test", quote: "SEK", takerPct: 0.4, slippagePct: 0.2, fxPct: 1, assets: { BTC: true, ETH: true, GOLD: true } };
const PX = { BTC: 1050000, ETH: 38000, GOLD: 37000 };
const row = (date, red, extra) => Object.assign(
  { date, ready: true, red, px: PX, ethBtcAbove30dMa: false, vix: 15, spxBelowMa: false }, extra || {});
const newUser = (cash, start, extra) => Object.assign({ v: 1, startDate: "2026-10-01", exchangeId: "test", start,
  level: 1, mode: "AVVAKTAR", lastDay: "2026-09-30",
  portfolio: { start, value: cash, peak: Math.max(cash, start), holdings: { BTC: 0, ETH: 0, GOLD: 0, CASH: cash },
    positions: {}, firstTrade: null, history: [{ date: "2026-09-30", value: start, cash: start, note: "start", flow: start }] },
  journal: [], trades: [] }, extra || {});

const PARITY = ["offensiv_from_cash", "normal_half_caps", "normal_cash_100000_20", "normal_trims_btc", "avvaktar_keeps", "parkera_sells_all",
  "buffer_6_stays_parked", "buffer_5_wakes", "eth_level2", "gold_level3_parked"];
for (const name of PARITY) {
  test("parity_" + name, async () => {
    const fx = await fixtures();
    const c = fx.cases.find((x) => x.name === name);
    if (!c) throw new Error("fallet saknas i fixturen");
    const user = Object.assign(newUser(0, 100000), clone(c.user), { journal: [], trades: [] });
    const p = E().propose(user, c.row, fx.rules, fx.exchange);
    eq(p.mode, c.expect.mode);
    eq(p.valueSek, c.expect.valueSek);
    same(p.trades, c.expect.trades);
    E().apply(user, p, c.row.date);
    eq(user.mode, c.expect.mode);
    same(user.portfolio.holdings, c.expect.portfolio.holdings);
    same(user.portfolio.positions, c.expect.portfolio.positions);
    eq(user.portfolio.value, c.expect.portfolio.value);
    eq(user.portfolio.peak, c.expect.portfolio.peak);
    eq(user.portfolio.firstTrade, c.expect.portfolio.firstTrade);
    same(user.portfolio.history, c.expect.portfolio.history);
  });
}

test("missing_paxg_stays_cash", () => {
  const ex = Object.assign({}, EX, { assets: { BTC: true, ETH: true } });
  const user = newUser(100000, 100000, { level: 3, mode: "PARKERA" });
  const p = E().propose(user, row("2026-10-05", 8, { vix: 25 }), RULES, ex);
  eq(p.trades.filter((t) => t.asset === "GOLD").length, 0);
  eq(p.missing, ["GOLD"]);
  if (!p.plain.includes("Guld finns inte på din börs")) throw new Error("plain: " + p.plain);
});

test("fee_adds_fx_when_quote_not_sek", () => {
  const ex = Object.assign({}, EX, { quote: "EUR" });
  const p = E().propose(newUser(100000, 100000), row("2026-10-05", 1), RULES, ex);
  eq(p.trades[0].feeSek, 560);  // 35 000 × (0,4 + 0,2 + 1) %
});

test("catchup_skips_not_ready", () => {
  const user = newUser(100000, 100000);
  const r = E().catchUp(user, [row("2026-10-01", 1, { ready: false, px: { BTC: null, ETH: null, GOLD: null } })], RULES, LEVELS, EX);
  eq(r.events.length, 0);
  eq(r.user.mode, "AVVAKTAR");
  eq(r.user.portfolio.holdings.CASH, 100000);
  eq(r.user.lastDay, "2026-10-01");
});

test("catchup_gaps", () => {
  const user = newUser(100000, 100000);
  const log = [row("2026-10-10", 5), row("2026-09-29", 1), row("2026-10-01", 1), row("2026-10-02", 3)];
  const r = E().catchUp(user, log, RULES, LEVELS, EX);
  eq(r.events.map((e) => e.date), ["2026-10-01", "2026-10-02", "2026-10-10"]);
  const days = r.user.portfolio.history.map((h) => h.date).filter((d) => d > "2026-09-30");
  eq(days, ["2026-10-01", "2026-10-02", "2026-10-10"]);
  eq(r.user.lastDay, "2026-10-10");
  eq(E().catchUp(r.user, log, RULES, LEVELS, EX).events.length, 0);  // samma logg igen → inget nytt
});

test("catchup_90_days", () => {
  const user = newUser(100000, 100000);
  const log = [];
  for (let i = 0; i < 90; i++) {
    const d = new Date(Date.UTC(2026, 9, 1 + i)).toISOString().slice(0, 10);
    log.push(row(d, [1, 3, 5, 7, 8, 5, 4][i % 7], { px: { BTC: 1e6 + i * 5000, ETH: 38000, GOLD: 37000 }, vix: 15 + (i % 11) }));
  }
  const t0 = performance.now();
  const r = E().catchUp(user, log, RULES, LEVELS, EX);
  const ms = performance.now() - t0;
  if (ms >= 200) throw new Error("tog " + ms + " ms");
  eq(r.user.lastDay, log[89].date);
  eq(r.user.mode, "AVVAKTAR");  // dag 89: 5 röda efter 8 → vaknar till Avvaktar
  eq(r.events.filter((e) => !/^Level/.test(e.plain)).length, 77);  // 6 lägesbyten per vecka + 5 sista dagarna
  if (r.user.portfolio.holdings.CASH < 0) throw new Error("negativa kontanter");
});

test("level2_early_unlock", () => {
  // Dag 15, +20 % marknadsvinst, drawdown 7 %, 7 gröna (3 röda)
  const user = newUser(120000, 100000, { mode: "NORMAL" });
  user.portfolio.peak = 129032.26;
  eq(E().levelFor(user, row("2026-10-15", 3), RULES, LEVELS), 2);
  eq(E().levelFor(user, row("2026-10-14", 3), RULES, LEVELS), 1);  // dag 14 räcker inte
  const r = E().catchUp(user, [row("2026-10-15", 3)], RULES, LEVELS, EX);
  eq(r.user.level, 2);
  eq(r.user.journal.filter((j) => j.plain.includes("Level 2")).length, 1);
  eq(r.events.filter((j) => j.plain.includes("Level 2")).length, 1);
});

test("level_sticky", () => {
  const user = newUser(90000, 100000, { level: 2, mode: "NORMAL" });
  eq(E().levelFor(user, row("2026-10-20", 3), RULES, LEVELS), 1);
  const r = E().catchUp(user, [row("2026-10-20", 3)], RULES, LEVELS, EX);
  eq(r.user.level, 2);
  eq(r.user.journal.filter((j) => j.plain.includes("Level")).length, 0);
});

test("summary_two_trades", () => {
  const user = newUser(100000, 100000);
  const r = E().catchUp(user, [row("2026-10-01", 1), row("2026-10-02", 7)], RULES, LEVELS, EX);
  eq(E().summary(r.events), "Medan du var borta gjorde jag 2 affärer: köpte bitcoin för 35 000 kr och sålde bitcoin för 34 790 kr.");
  eq(E().summary([]), "");
});

test("round_like_python", () => {
  const R = E().round;
  eq(R(0.015, 2), 0.01);      // egentligen 0,01499…
  eq(R(0.005, 2), 0.01);      // egentligen 0,00500…1
  eq(R(0.125, 2), 0.12);      // exakt lika → jämn
  eq(R(0.375, 2), 0.38);
  eq(R(2.675, 2), 2.67);
  eq(R(17500.035, 2), 17500.03);
  eq(R(1.23456789123, 8), 1.23456789);
  eq(R(-0.125, 2), -0.12);
  eq(R(2.5, 0), 2);
  eq(R(3.5, 0), 4);
});

test("catchup_waits_for_missing_price", () => {
  const user = newUser(82150, 100000);
  user.portfolio.positions.BTC = { units: 0.017, costSek: 17500, since: "2026-10-01" };
  user.portfolio.holdings.BTC = 17850;
  user.portfolio.value = 100000;
  const r = E().catchUp(user, [row("2026-10-03", 7, { px: { BTC: null, ETH: 38000, GOLD: 37000 } })], RULES, LEVELS, EX);
  eq(r.user.trades.length, 0);
  eq(r.user.portfolio.holdings.BTC, 17850);
  eq(r.user.portfolio.positions.BTC.units, 0.017);
  eq(r.user.mode, "PARKERA");
  if (!r.events[0].plain.includes("väntar på pris")) throw new Error("plain: " + r.events[0].plain);
});

test("catchup_duplicate_date_prefers_ready", () => {
  const user = newUser(100000, 100000);
  const half = row("2026-10-01", 1, { ready: false, px: { BTC: null, ETH: null, GOLD: null } });
  const r = E().catchUp(user, [row("2026-10-01", 1), half], RULES, LEVELS, EX);
  eq(r.user.mode, "OFFENSIV");
  eq(r.user.trades.length, 1);
  const r2 = E().catchUp(newUser(100000, 100000), [half, row("2026-10-01", 1)], RULES, LEVELS, EX);
  eq(r2.user.trades.length, 1);
});

test("catchup_ignores_rows_before_start", () => {
  const user = newUser(100000, 100000, { lastDay: null });
  const r = E().catchUp(user, [row("2026-09-28", 1), row("2026-10-01", 5)], RULES, LEVELS, EX);
  eq(r.user.trades.length, 0);
  eq(r.user.mode, "AVVAKTAR");
  eq(r.user.lastDay, "2026-10-01");
});
