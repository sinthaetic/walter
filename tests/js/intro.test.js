// Tester för js/intro.js (summan: bara siffror, mellanslag och "kr").
test("parse_ok", () => {
  const p = window.WalterIntro.parseAmount;
  eq(p("10 000"), 10000);
  eq(p("10000"), 10000);
  eq(p("250000 kr"), 250000);
  eq(p("10 000 kr"), 10000);
  eq(p("100"), 100);
  eq(p("100000000"), 100000000);
});
test("parse_rejects", () => {
  const p = window.WalterIntro.parseAmount;
  ["", "0", "-5", "abc", "99", "1e9", "200000000", "2,5 miljoner", "kr", "10.5"].forEach((t) => eq(p(t), null));
});
test("ex_meta_two_lines", () => {
  const m = window.WalterIntro.exMeta({ licence: { country: "LU" }, takerPct: 0.4 });
  eq(m, ["Tillstånd: Luxemburg", "Avgift 0,4 %"]);
  eq(window.WalterIntro.exMeta({ licence: { country: "XX" }, takerPct: 0.25 }), ["Tillstånd: XX", "Avgift 0,25 %"]);
});
