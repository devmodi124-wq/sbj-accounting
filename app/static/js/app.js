// Khata SPA shell: auth orchestration + sidebar nav.
// Feature view modules are added in later phases.
(function () {
  "use strict";

  const $ = (id) => document.getElementById(id);
  let mode = "login"; // "login" | "bootstrap"

  function show(el, on) { el.classList.toggle("hidden", !on); }

  function setBanner(el, msg) {
    if (!msg) { show(el, false); el.textContent = ""; return; }
    el.textContent = msg;
    show(el, true);
  }

  const ERROR_MESSAGES = {
    invalid_credentials: "Incorrect username or password.",
    session_invalid: "You were signed out — your account signed in elsewhere.",
    inactive_user: "This account is disabled. Ask an admin.",
  };

  // ===== Auth screen =====
  function showAuth(nextMode, info) {
    mode = nextMode;
    show($("auth-screen"), true);
    show($("app-screen"), false);
    setBanner($("auth-error"), "");
    setBanner($("auth-info"), info || "");
    show($("fullname-field"), mode === "bootstrap");
    $("auth-submit").textContent = mode === "bootstrap" ? "Create admin account" : "Sign in";
    if (mode === "bootstrap") {
      $("auth-info").textContent = "First run — create the administrator account.";
      show($("auth-info"), true);
    }
    $("auth-username").focus();
  }

  async function submitAuth(ev) {
    ev.preventDefault();
    setBanner($("auth-error"), "");
    const username = $("auth-username").value.trim();
    const password = $("auth-password").value;
    if (!username || !password) {
      setBanner($("auth-error"), "Enter a username and password.");
      return;
    }
    $("auth-submit").disabled = true;
    try {
      if (mode === "bootstrap") {
        await api.post("/auth/bootstrap", {
          username, password, full_name: $("auth-fullname").value.trim(),
        });
      } else {
        await api.post("/auth/login", { username, password });
      }
      $("auth-password").value = "";
      await init();
    } catch (e) {
      setBanner($("auth-error"), ERROR_MESSAGES[e.detail] || e.message || "Sign-in failed.");
    } finally {
      $("auth-submit").disabled = false;
    }
  }

  // ===== Main app =====
  function showApp(user) {
    show($("auth-screen"), false);
    show($("app-screen"), true);
    $("userName").textContent = user.full_name || user.username;
    $("userRole").textContent = user.role === "admin" ? "Admin" : "Employee";
    $("userAvatar").textContent = (user.full_name || user.username || "?").charAt(0).toUpperCase();
    const isAdmin = user.role === "admin";
    document.querySelectorAll(".nav-admin").forEach((el) => show(el, isAdmin));
    show($("nav-system-section"), isAdmin);
  }

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
    $("logout-btn").addEventListener("click", async () => {
      await api.post("/auth/logout");
      showAuth("login", "Signed out.");
    });
  }

  // ===== Bootstrap of the page =====
  async function init() {
    const status = await api.get("/auth/status");
    if (status.state === "needs_bootstrap") return showAuth("bootstrap");
    if (status.state === "locked") return showAuth("login", "Database locked — sign in to unlock.");
    if (!status.authenticated) return showAuth("login");
    showApp(status.user);
  }

  document.addEventListener("DOMContentLoaded", () => {
    $("auth-form").addEventListener("submit", submitAuth);
    wireNav();
    init().catch((e) => setBanner($("auth-error"), e.message));
  });
})();
