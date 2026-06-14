// Small DOM / formatting helpers shared by view modules.
(function () {
  "use strict";

  function el(tag, attrs, children) {
    const node = document.createElement(tag);
    if (attrs) {
      for (const [k, v] of Object.entries(attrs)) {
        if (k === "class") node.className = v;
        else if (k === "html") node.innerHTML = v;
        else if (k.startsWith("on") && typeof v === "function") {
          node.addEventListener(k.slice(2).toLowerCase(), v);
        } else if (v !== null && v !== undefined && v !== false) {
          node.setAttribute(k, v);
        }
      }
    }
    for (const c of [].concat(children || [])) {
      if (c === null || c === undefined || c === false) continue;
      node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
    }
    return node;
  }

  function clear(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
    return node;
  }

  let toastTimer = null;
  function toast(message, kind) {
    let t = document.getElementById("toast");
    if (!t) {
      t = el("div", { id: "toast" });
      t.style.cssText =
        "position:fixed;bottom:20px;right:20px;padding:10px 16px;border-radius:6px;" +
        "font-size:13px;z-index:1000;box-shadow:0 4px 16px rgba(0,0,0,.15);";
      document.body.appendChild(t);
    }
    t.textContent = message;
    t.style.background = kind === "error" ? "#9B3B3B" : "#2F5D4E";
    t.style.color = "#fff";
    t.style.display = "block";
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => (t.style.display = "none"), 2600);
  }

  function errorText(e) {
    const map = {
      name_exists: "That name already exists.",
      username_taken: "That username is taken.",
      cannot_deactivate_self: "You can't deactivate your own account.",
      cannot_demote_self: "You can't change your own role.",
      has_references: "This record has linked orders/transactions and can't be deleted.",
      admin_required: "Only an admin can do this.",
    };
    return map[e && e.detail] || (e && e.message) || "Something went wrong.";
  }

  window.ui = { el, clear, toast, errorText };
})();
