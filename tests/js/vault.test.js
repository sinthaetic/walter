// Tester för js/vault.js. Fixturen görs av tests/make_fixtures.py.
test("dekrypterar med rätt kod", async () => {
  const env = await (await fetch("../fixtures/vault-sample.enc")).json();
  eq(await WalterVault.decrypt(env, "TEST-KOD"), { hej: "världen", n: 1.5 });
});

test("fel kod avvisas", async () => {
  const env = await (await fetch("../fixtures/vault-sample.enc")).json();
  await rejects(WalterVault.decrypt(env, "fel"), "Fel kod eller trasig fil");
});

test("ändrad ct avvisas", async () => {
  const env = await (await fetch("../fixtures/vault-sample.enc")).json();
  const b = atob(env.ct).split("");
  b[0] = String.fromCharCode(b[0].charCodeAt(0) ^ 1);
  env.ct = btoa(b.join(""));
  await rejects(WalterVault.decrypt(env, "TEST-KOD"), "Fel kod eller trasig fil");
});
