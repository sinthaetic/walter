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

  window.WalterTop = { fit };
})();
