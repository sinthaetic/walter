// Tester för js/manual.js: egen handel i bitcoin med släpande stopp −10 %.
const M = () => window.WalterManual;

test("manual_buy_sell_with_fee", () => {
  const p = M().create(10000, "2026-11-01", { value: 1000, gain: 0 });
  eq(M().buy(p, 4000, 800000, 0.01, "2026-11-01"), true);
  eq(p.cash, 6000);
  eq(Math.round(p.units * 1e8), Math.round(4000 * 0.99 / 800000 * 1e8));
  eq(M().buy(p, 7000, 800000, 0.01, "2026-11-01"), false); // mer än kassan
  eq(M().sell(p, 1e9, 900000, 0.01, "2026-11-02"), true);   // mer än innehavet = allt
  eq(p.units, 0);
  eq(p.costSek, 0);
  eq(p.cash, Math.round((6000 + 4000 * 0.99 / 800000 * 900000 * 0.99) * 100) / 100);
  eq(p.trades[1].gainSek, Math.round((4000 * 0.99 / 800000 * 900000 * 0.99 - 4000) * 100) / 100);
});

test("manual_sell_part_keeps_average_cost", () => {
  const p = M().create(10000, "2026-11-01");
  M().buy(p, 4000, 800000, 0, "2026-11-01");
  M().sell(p, 1000, 800000, 0, "2026-11-01"); // en fjärdedel
  eq(p.costSek, 3000);
  eq(p.cash, 7000);
});

test("manual_trailing_stop_follows_peak", () => {
  const p = M().create(10000, "2026-11-01");
  M().buy(p, 10000, 100, 0, "2026-11-01");
  const rows = [{ date: "2026-11-01", px: 100 }, { date: "2026-11-02", px: 120 }, { date: "2026-11-03", px: 110 },
    { date: "2026-11-04", px: 107 }, { date: "2026-11-05", px: 90 }];
  const hit = M().checkStop(p, rows, 0);
  eq(hit.date, "2026-11-04");      // 107 <= 120 × 0,9 = 108
  eq(p.units, 0);
  eq(p.cash, 10700);
  eq(p.trades[1].why, "stopp");
  eq(p.checked, "2026-11-04");
  eq(M().checkStop(p, rows, 0), null); // ingen position: dagarna gås igenom, inget säljs
  eq(p.checked, "2026-11-05");
});

test("manual_short_earns_when_price_falls", () => {
  const p = M().create(1000, "2026-11-01");
  eq(M().short(p, 1000, 100, 0.01, "2026-11-01"), true);
  eq(p.cash, 0);
  eq(M().buy(p, 1, 100, 0, "2026-11-01"), false);    // aldrig köp och blankning samtidigt
  eq(M().short(p, 1, 100, 0, "2026-11-01"), false);  // en blankning i taget
  const days = 10, margin = 990, units = margin / 100, fund = units * 100 * M().FUNDING_DAY * days;
  eq(Math.round(M().value(p, 80, "2026-11-11") * 100), Math.round((margin + 20 * units - fund) * 100));
  eq(M().cover(p, 80, 0.01, "2026-11-11"), true);
  eq(p.short, null);
  eq(p.cash, Math.round((margin + 20 * units - fund - units * 80 * 0.01) * 100) / 100);
  eq(p.trades[1].side, "stäng");
  eq(p.trades[1].gainSek, Math.round((p.cash - 1000) * 100) / 100);
});

test("manual_short_blocked_while_holding", () => {
  const p = M().create(1000, "2026-11-01");
  M().buy(p, 500, 100, 0, "2026-11-01");
  eq(M().short(p, 100, 100, 0, "2026-11-01"), false);
});

test("manual_short_trailing_stop_from_low", () => {
  const p = M().create(1000, "2026-11-01");
  M().short(p, 1000, 100, 0, "2026-11-01");
  const hit = M().checkStop(p, [{ date: "2026-11-02", px: 80 }, { date: "2026-11-03", px: 87 }, { date: "2026-11-04", px: 89 }], 0);
  eq(hit.date, "2026-11-04");       // 89 >= 80 × 1,1 = 88
  eq(p.short, null);
  eq(p.trades[1].why, "stopp");
  const q = M().create(1000, "2026-11-01");
  M().short(q, 1000, 100, 0, "2026-11-01");
  eq(M().checkLive(q, 95, 0, "2026-11-01"), false);
  eq(Math.round(M().stopPx(q) * 10), 1045);
  eq(M().checkLive(q, 105, 0, "2026-11-01"), true);
});

test("manual_short_never_loses_more_than_stake", () => {
  const p = M().create(1000, "2026-11-01");
  M().short(p, 1000, 100, 0, "2026-11-01");
  eq(M().value(p, 500, "2026-11-02"), 0);   // gap rakt förbi stoppet: insatsen är borta, inget mer
  M().cover(p, 500, 0.01, "2026-11-02", "stopp");
  eq(p.cash, 0);
  eq(p.trades[1].gainSek, -1000);
});

test("arena_pot_curve_replays_trades_and_short", () => {
  const p = M().create(1000, "2026-11-01");
  M().buy(p, 1000, 100, 0, "2026-11-01");
  M().sell(p, Infinity, 120, 0, "2026-11-02");
  M().short(p, 1200, 120, 0, "2026-11-03");
  M().cover(p, 90, 0, "2026-11-05");
  const c = M().potCurve(p, [{ date: "2026-10-31", px: 90 }, { date: "2026-11-01", px: 100 }, { date: "2026-11-02", px: 120 },
    { date: "2026-11-04", px: 100 }, { date: "2026-11-05", px: 90 }, { date: "2026-11-06", px: 200 }]);
  eq(c.map((x) => x.date), ["2026-11-01", "2026-11-02", "2026-11-04", "2026-11-05", "2026-11-06"]);
  eq(c[0].pct, 0); eq(c[1].pct, 20);
  eq(Math.round(c[3].pct), Math.round((p.cash / 1000 - 1) * 100));
  eq(c[4].pct, c[3].pct);          // stängd: priset rör inte kassan
});

test("arena_walter_curve_ignores_deposits", () => {
  const px = (b) => ({ BTC: b });
  const rows = [{ date: "2026-11-01", px: px(100) }, { date: "2026-11-02", px: px(110) }, { date: "2026-11-03", px: px(110) }];
  const trades = [{ date: "2026-11-01", side: "köp", asset: "BTC", units: 10, sek: 1000, feeSek: 0 }];
  const flows = [{ date: "2026-11-01", flow: 1000 }, { date: "2026-11-03", flow: 500 }];
  const c = M().walterCurve(trades, flows, rows, "2026-11-01");
  eq(c.map((x) => x.pct), [0, 10, 10]);   // insättningen 3 nov är ingen vinst
});

test("arena_rounds_and_badges_count_results_not_trades", () => {
  const du = [{ date: "2026-10-31", pct: 0 }, { date: "2026-11-30", pct: -2 }, { date: "2026-12-05", pct: -1 }];
  const wa = [{ date: "2026-10-31", pct: 0 }, { date: "2026-11-30", pct: -10 }, { date: "2026-12-05", pct: -11 }];
  const r = M().rounds(du, wa, [], "2026-12-05");
  eq(r.map((x) => [x.month, x.winner, x.live]), [["2026-10", null, false], ["2026-11", "du", false], ["2026-12", "du", true]]);
  const b = M().badges(r);
  eq(b.find((x) => x.id === "ras").won, true);
  eq(b.find((x) => x.id === "still").won, true);
  eq(b.find((x) => x.id === "tre").won, false);
  const live = M().badges([{ month: "2026-12", du: 1, walter: -8, winner: "du", live: true, trades: 2 }]);
  eq([live[0].won, live[0].live], [false, true]); // en pågående runda låser inte upp
});

test("arena_copy_roundtrip_and_rejects_bad_files", () => {
  const p = M().create(1000, "2026-11-01", { value: 900, gain: 0 });
  M().short(p, 500, 100, 0.01, "2026-11-01");
  eq(M().parsePot(M().exportText(p)), p);
  eq(M().parsePot("inte json"), null);
  eq(M().parsePot(JSON.stringify({ walterManual: 1, pot: { ...p, cash: "1" } })), null);
  eq(M().parsePot(JSON.stringify({ walterManual: 1, pot: { ...p, since: "<img>" } })), null);
  eq(M().parsePot(JSON.stringify({ walterManual: 1, pot: { ...p, trades: [{ date: "2026-11-01", side: "x", sek: 1, units: 1, px: 1, feeSek: 0 }] } })), null);
});

test("manual_stop_not_hit_and_stop_price", () => {
  const p = M().create(1000, "2026-11-01");
  M().buy(p, 1000, 100, 0, "2026-11-01");
  eq(M().checkStop(p, [{ date: "2026-11-02", px: 95 }], 0), null);
  eq(M().stopPx(p), 90);
  eq(Math.round(M().value(p, 95)), 950);
});
