// Tester för js/exchanges.js (börslistan med MiCA-börser).
const XS = () => window.WALTER_EXCHANGES || [];

test("exchanges_listed_and_sorted", () => {
  const names = XS().map((x) => x.name);
  if (!names.length) throw new Error("listan är tom");
  eq(names, names.slice().sort((a, b) => a.localeCompare(b)));
});

test("all_have_source_and_date", () => {
  for (const x of XS()) {
    if (!/^https:\/\/\S+$/.test(x.source || "")) throw new Error(x.id + ": källa saknas");
    if (!/^\d{4}-\d{2}-\d{2}$/.test(x.checked || "")) throw new Error(x.id + ": datum saknas");
    if (!x.licence || x.licence.register !== "ESMA" || !x.licence.authority || !x.licence.country)
      throw new Error(x.id + ": tillstånd saknas");
  }
});

test("no_binance", () => {
  for (const x of XS()) if (/binance/i.test(x.id + " " + x.name)) throw new Error("Binance har inget MiCA-tillstånd");
});

test("fees_are_numbers", () => {
  for (const x of XS()) {
    for (const k of ["takerPct", "slippagePct", "fxPct"]) {
      const v = x[k];
      if (typeof v !== "number" || !Number.isFinite(v) || v < 0 || v > 5) throw new Error(x.id + "." + k + " = " + v);
    }
    if (!["EUR", "USD", "SEK"].includes(x.quote)) throw new Error(x.id + ": quote " + x.quote);
  }
});

test("assets_btc_true", () => {
  for (const x of XS()) {
    if (x.assets.BTC !== true) throw new Error(x.id + ": BTC saknas");
    for (const a of ["ETH", "GOLD"]) if (typeof x.assets[a] !== "boolean") throw new Error(x.id + ": " + a + " måste vara true/false");
  }
});
