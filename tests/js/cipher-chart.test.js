// js/cipher-chart.js: de rena delarna (lampornas historik + logg, Walters affärer ur journalen, datum till stapel).
const CCt = window.WalterCipherChart;
const utc = (iso, h = 0) => Date.UTC(+iso.slice(0, 4), +iso.slice(5, 7) - 1, +iso.slice(8, 10), h) / 1000;

test("mergePulse: loggen vinner samma dag, nya dagar läggs till, rader utan röda hoppas över", () => {
  const pulse = [["2026-10-20", 4], ["2026-10-21", 2], ["2026-10-22", 2]];
  const log = [{ date: "2026-10-22", ready: true, red: 3 }, { date: "2026-10-23", ready: true, red: 5 },
    { date: "2026-10-24", ready: false, red: null }, { date: "2026-10-25", red: null }];
  eq(CCt.mergePulse(pulse, log), [["2026-10-20", 4], ["2026-10-21", 2], ["2026-10-22", 3], ["2026-10-23", 5]]);
});

test("mergePulse: utan historik eller logg blir det en tom lista", () => {
  eq(CCt.mergePulse(undefined, undefined), []);
  eq(CCt.mergePulse([], [{ date: "2026-10-23", red: 1 }]), [["2026-10-23", 1]]);
});

test("tradeMarks: appens trades, Pythons faktarader och en koll utan affär", () => {
  const journal = [
    { date: "2026-10-25", check: true, trades: [] },
    { date: "2026-10-23", plain: "…", facts: ["Köp: 0,05 BTC à 809 073 kr = 44 555,00 kr, avgift 267 kr", "3/10 röda"] },
    { date: "2026-10-21", facts: ["Sålt: 89 SEK BTC (damm) → kontant"] },
    { date: "2026-10-19", trades: [{ asset: "BTC", side: "sälj", sek: 10 }, { asset: "ETH", side: "köp", sek: 5 }, { asset: "GOLD", side: "köp", sek: 5 }] },
    { date: "2026-10-16", plain: "Tung dag", facts: ["BTC $81 776"] }
  ];
  eq(CCt.tradeMarks(journal), [
    { date: "2026-10-19", side: "sell" }, { date: "2026-10-19", side: "buy" },
    { date: "2026-10-21", side: "sell" }, { date: "2026-10-23", side: "buy" }, { date: "2026-10-25", side: "check" }]);
  eq(CCt.tradeMarks(undefined), []);
});

test("alignTime: DAG samma dag, 4 TIM dagens första stapel, VECKA veckan som innehåller dagen", () => {
  const daily = ["2026-10-21", "2026-10-22", "2026-10-23"].map(d => ({ time: utc(d) }));
  eq(CCt.alignTime("2026-10-22", daily, "1D"), utc("2026-10-22"));
  eq(CCt.alignTime("2026-10-24", daily, "1D"), null);
  const h4 = [utc("2026-10-21", 20), utc("2026-10-22", 0), utc("2026-10-22", 4), utc("2026-10-22", 8)].map(time => ({ time }));
  eq(CCt.alignTime("2026-10-22", h4, "4h"), utc("2026-10-22", 0));
  eq(CCt.alignTime("2026-10-23", h4, "4h"), null);
  const weekly = ["2026-10-12", "2026-10-19"].map(d => ({ time: utc(d) }));  // måndagar
  eq(CCt.alignTime("2026-10-25", weekly, "1W"), utc("2026-10-19"));         // söndag i veckan
  eq(CCt.alignTime("2026-10-14", weekly, "1W"), utc("2026-10-12"));
  eq(CCt.alignTime("2026-11-02", weekly, "1W"), null);
});

test("pulseBars: 5 − röda per stapel, VECKA tar veckans sista dag, gammal data ger ingen punkt", () => {
  const pulse = [["2026-10-12", 2], ["2026-10-18", 7], ["2026-10-19", 8]];
  const daily = ["2026-10-11", "2026-10-12", "2026-10-13", "2026-10-19", "2026-10-30"].map(d => ({ time: utc(d) }));
  eq(CCt.pulseBars(pulse, daily, "1D", 0), [
    { time: utc("2026-10-12"), value: 3 }, { time: utc("2026-10-13"), value: 3 }, { time: utc("2026-10-19"), value: -3 }]);
  eq(CCt.pulseBars(pulse, daily, "1D", 2).map(p => p.time), [utc("2026-10-13"), utc("2026-10-19")]);
  const weekly = [{ time: utc("2026-10-12") }];
  eq(CCt.pulseBars(pulse, weekly, "1W", 0), [{ time: utc("2026-10-12"), value: -2 }]);  // söndag 18 okt = 7 röda
});
