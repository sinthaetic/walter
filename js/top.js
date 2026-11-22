// Sidhuvudets meny (css/top.css), samma på index.html och cipher.html.
// På smala skärmar rullar menyn i sidled: den aktiva fliken rullas in i bild, och en mjuk toning i kanten
// (.more-left / .more-right) visar att det finns fler flikar. Inga beroenden.
(function () {
  "use strict";

  function edges(nav) {
    const max = nav.scrollWidth - nav.clientWidth;
    nav.classList.toggle("more-left", max > 2 && nav.scrollLeft > 2);
    nav.classList.toggle("more-right", max > 2 && max - nav.scrollLeft > 2);
  }

  // Den aktiva fliken mitt i menyn om den inte syns helt (annars står menyn kvar till vänster)
  function show(nav) {
    nav.scrollLeft = 0;
    const a = nav.querySelector('[aria-current="page"]');
    if (!a || nav.scrollWidth <= nav.clientWidth) return;
    const r = a.getBoundingClientRect(), n = nav.getBoundingClientRect();
    if (r.left < n.left || r.right > n.right) nav.scrollLeft = Math.max(0, r.left - n.left - (n.width - r.width) / 2);
  }

  function fit() {
    document.querySelectorAll(".nav").forEach((nav) => {
      if (!nav.dataset.fit) {
        nav.dataset.fit = "1";
        nav.addEventListener("scroll", () => edges(nav), { passive: true });
        window.addEventListener("resize", () => edges(nav));
      }
      show(nav);
      edges(nav);
    });
  }

  // Typsnitten ändrar flikarnas bredd: räkna om när de laddats, och när sidan visas igen (Safari minns rullningen)
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(fit).catch(() => {});
  window.addEventListener("pageshow", fit);

  // Ny version publicerad? Webbläsaren kan hålla kvar en gammal sida, så läs versionen direkt från servern och
  // ladda om en gång med versionen i adressen. Lokalt (build "dev") och utan nät händer inget.
  (async () => {
    const mine = (document.querySelector('meta[name="walter-build"]') || {}).content;
    if (!mine || mine === "dev" || !/^https?:$/.test(location.protocol)) return;
    try {
      const html = await (await fetch(location.pathname, { cache: "no-store" })).text();
      const now = (html.match(/name="walter-build" content="([^"]+)"/) || [])[1];
      if (!now || now === "dev" || now === mine || sessionStorage.getItem("walterBuild") === now) return;
      sessionStorage.setItem("walterBuild", now); // en gång per version, så att sidan aldrig fastnar i omladdning
      const url = new URL(location.href);
      url.searchParams.set("b", now);
      location.replace(url);
    } catch (e) { /* inget nät eller blockerad lagring: sidan fungerar som den är */ }
  })();

  window.WalterTop = { fit };
})();
