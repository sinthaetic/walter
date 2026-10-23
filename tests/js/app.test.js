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
