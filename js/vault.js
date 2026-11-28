// Walter-valvet i webbläsaren: dekrypterar kuvertet från fetcher/walter_vault.py.
// Rent, inga DOM-anrop. Kuvert: {v, kdf:"PBKDF2-SHA256", iter, salt, iv, ct} i vanlig base64.
(function () {
  "use strict";

  const FEL = "Fel kod eller trasig fil";

  function b64(s) {
    return Uint8Array.from(atob(s), (c) => c.charCodeAt(0));
  }

  async function decrypt(env, code) {
    try {
      if (!env || env.v !== 1 || env.kdf !== "PBKDF2-SHA256") throw new Error("kuvert");
      const enc = new TextEncoder();
      const base = await crypto.subtle.importKey("raw", enc.encode(code), "PBKDF2", false, ["deriveKey"]);
      const key = await crypto.subtle.deriveKey(
        { name: "PBKDF2", hash: "SHA-256", salt: b64(env.salt), iterations: Number(env.iter) },
        base,
        { name: "AES-GCM", length: 256 },
        false,
        ["decrypt"]
      );
      const plain = await crypto.subtle.decrypt({ name: "AES-GCM", iv: b64(env.iv) }, key, b64(env.ct));
      return JSON.parse(new TextDecoder().decode(plain));
    } catch (e) {
      throw new Error(FEL);
    }
  }

  window.WalterVault = { decrypt };
})();
