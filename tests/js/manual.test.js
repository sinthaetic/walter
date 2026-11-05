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

test("manual_stop_not_hit_and_stop_price", () => {
  const p = M().create(1000, "2026-11-01");
  M().buy(p, 1000, 100, 0, "2026-11-01");
  eq(M().checkStop(p, [{ date: "2026-11-02", px: 95 }], 0), null);
  eq(M().stopPx(p), 90);
  eq(Math.round(M().value(p, 95)), 950);
});
