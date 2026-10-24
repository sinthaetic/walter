// Paritet: js/wcipher.js mot Python-porten backtest/wcipher.py (historiktestet). Fixturen görs av tests/make_fixtures.py.
test("W-Cipher: samma signaler som Python-porten (sort och stapel)", async () => {
  const fx = await (await fetch("../fixtures/wcipher-bars.json")).json();
  const r = WCipher.compute(fx.bars);
  eq(r.signals.map(s => [s.i, s.kind]), fx.expect.signals);
});

test("W-Cipher: wt1 och wt2 som Python-porten (inom 1e-9)", async () => {
  const fx = await (await fetch("../fixtures/wcipher-bars.json")).json();
  const r = WCipher.compute(fx.bars);
  eq(r.wt1.length, fx.expect.wt1.length);
  let worst = 0;
  for (let i = 0; i < r.wt1.length; i++) {
    worst = Math.max(worst, Math.abs(r.wt1[i] - fx.expect.wt1[i]), Math.abs(r.wt2[i] - fx.expect.wt2[i]));
  }
  if (!(worst < 1e-9)) throw new Error("största skillnad " + worst);
});

test("W-Cipher: fixturen har alla tio signalsorter", async () => {
  const fx = await (await fetch("../fixtures/wcipher-bars.json")).json();
  eq([...new Set(fx.expect.signals.map(s => s[1]))].sort(), Object.keys(WCipher.KINDS).sort());
});
