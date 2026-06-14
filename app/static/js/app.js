// Khata SPA shell. Phase 0: sidebar nav switching + a health ping.
// Feature view modules are added in later phases.

(function () {
  "use strict";

  function switchView(view) {
    document.querySelectorAll(".nav-item[data-view]").forEach((i) =>
      i.classList.toggle("active", i.dataset.view === view)
    );
    document.querySelectorAll(".view").forEach((v) =>
      v.classList.toggle("active", v.id === "view-" + view)
    );
  }

  function wireNav() {
    document.querySelectorAll(".nav-item[data-view]").forEach((item) => {
      item.addEventListener("click", () => switchView(item.dataset.view));
    });
  }

  async function ping() {
    try {
      const r = await fetch("/health");
      const data = await r.json();
      console.log("Khata health:", data);
    } catch (e) {
      console.warn("health check failed", e);
    }
  }

  document.addEventListener("DOMContentLoaded", () => {
    wireNav();
    ping();
  });
})();
