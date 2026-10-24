// Tester för js/app.js: vilka lagringsnycklar ägaren och användaren får (rena funktioner, ingen DOM).
test("app_keyfor", () => {
  const k = window.WalterApp.keyFor;
  eq(k("user", "settings"), "walter.user.settings");
  eq(k("user", "live"), "walter.user.live");
  eq(k("user", "plan"), "walter.user.plan");
  eq(k("owner", "settings"), "walter.settings");
  eq(k("owner", "live"), "walter.live");
  eq(k("owner-local", "goal"), "walter.goal");
});
test("app_isuserkey", () => {
  const f = window.WalterApp.isUserKey;
  eq(["walter.user", "walter.user.plan", "walter.user.settings"].map(f), [true, true, true]);
  eq(["walter.settings", "walter.ownerKey", "walterDark", "walter.username", "walterEntered"].map(f), [false, false, false, false, false]);
});

// Insättningar (start, månadssparande, "Sätt in pengar") är aldrig marknadsvinst
test("app_gain_excludes_flows", () => {
  const g = window.WalterApp.gain({ start: 1000, value: 2600, history: [
    { date: "2026-10-01", value: 1000, flow: 1000, note: "start" },
    { date: "2026-10-05", value: 2000, flow: 1000, note: "insättning" },
    { date: "2026-10-25", value: 2500, flow: 500, note: "månadssparande", month: "2026-10" }] });
  eq([g.topUp, g.deposits, g.marketGain], [1500, 2500, 100]);
  eq(Math.round(g.marketPct * 100) / 100, 4);
});
