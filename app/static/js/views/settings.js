// Admin Settings: app settings, component/purity types, users.
(function () {
  "use strict";
  const { el, clear, toast, errorText } = window.ui;

  function field(label, input) {
    return el("div", { class: "field" }, [el("label", {}, label), input]);
  }

  // ---- App settings card ----
  function appSettingsCard() {
    const inputs = {};
    const keys = [
      ["currency_symbol", "Currency symbol"],
      ["date_format", "Date format"],
      ["employee_backdate_limit_days", "Employee backdate limit (days)"],
      ["opening_cash_balance", "Opening cash balance"],
      ["backup_folder_path", "Backup folder path"],
    ];
    const body = el("div", { class: "card-body" });
    const grid = el("div", { class: "form-grid cols-2" });
    for (const [k, label] of keys) {
      inputs[k] = el("input", { type: "text" });
      grid.appendChild(field(label, inputs[k]));
    }
    body.appendChild(grid);
    body.appendChild(el("div", { class: "form-actions" },
      el("button", { class: "btn btn-primary", onclick: save }, "Save settings")));

    async function load() {
      const s = await api.get("/api/settings");
      for (const [k] of keys) inputs[k].value = s[k] || "";
    }
    async function save() {
      const payload = {};
      for (const [k] of keys) payload[k] = inputs[k].value.trim();
      try { await api.put("/api/settings", payload); toast("Settings saved."); }
      catch (e) { toast(errorText(e), "error"); }
    }
    load();
    return el("div", { class: "card" }, [
      el("div", { class: "card-header" }, el("h2", {}, "Application settings")), body,
    ]);
  }

  // ---- Lookup manager (component/purity types) ----
  function lookupCard(endpoint, title) {
    const tbody = el("tbody");
    const nameInput = el("input", { type: "text", placeholder: "New name…" });

    async function load() {
      const rows = await api.get(endpoint);
      clear(tbody);
      for (const r of rows) {
        const toggle = el("button", { class: "btn btn-sm", onclick: () => setActive(r) },
          r.is_active ? "Deactivate" : "Activate");
        tbody.appendChild(el("tr", {}, [
          el("td", {}, r.name),
          el("td", {}, r.is_active ? el("span", { class: "pill pill-green" }, "Active")
            : el("span", { class: "pill pill-muted" }, "Inactive")),
          el("td", {}, toggle),
        ]));
      }
    }
    async function add() {
      const name = nameInput.value.trim();
      if (!name) return;
      try { await api.post(endpoint, { name }); nameInput.value = ""; toast("Added."); load(); }
      catch (e) { toast(errorText(e), "error"); }
    }
    async function setActive(r) {
      try { await api.put(`${endpoint}/${r.id}`, { is_active: !r.is_active }); load(); }
      catch (e) { toast(errorText(e), "error"); }
    }
    load();
    return el("div", { class: "card" }, [
      el("div", { class: "card-header" }, el("h2", {}, title)),
      el("div", { class: "card-body" }, [
        el("div", { class: "filter-bar" }, [nameInput,
          el("button", { class: "btn", onclick: add }, "+ Add")]),
        el("table", {}, [el("thead", {}, el("tr", {}, [
          el("th", {}, "Name"), el("th", {}, "Status"), el("th", {}, "")])), tbody]),
      ]),
    ]);
  }

  // ---- Users ----
  function usersCard() {
    const tbody = el("tbody");
    const u = {
      username: el("input", { type: "text", placeholder: "username" }),
      password: el("input", { type: "password", placeholder: "password" }),
      full: el("input", { type: "text", placeholder: "full name" }),
      role: el("select", {}, [el("option", { value: "employee" }, "Employee"),
        el("option", { value: "admin" }, "Admin")]),
    };
    async function load() {
      const rows = await api.get("/api/users");
      clear(tbody);
      for (const r of rows) {
        tbody.appendChild(el("tr", {}, [
          el("td", {}, r.username),
          el("td", {}, r.full_name || "—"),
          el("td", {}, r.role === "admin" ? "Admin" : "Employee"),
          el("td", {}, r.is_active ? el("span", { class: "pill pill-green" }, "Active")
            : el("span", { class: "pill pill-muted" }, "Disabled")),
          el("td", {}, el("button", { class: "btn btn-sm", onclick: () => resetPw(r) }, "Reset password")),
        ]));
      }
    }
    async function create() {
      const payload = {
        username: u.username.value.trim(), password: u.password.value,
        full_name: u.full.value.trim(), role: u.role.value,
      };
      if (!payload.username || !payload.password) return toast("Username & password required.", "error");
      try {
        await api.post("/api/users", payload);
        u.username.value = u.password.value = u.full.value = "";
        toast("User created."); load();
      } catch (e) { toast(errorText(e), "error"); }
    }
    async function resetPw(r) {
      const pw = prompt(`New password for ${r.username}:`);
      if (!pw) return;
      try { await api.post(`/api/users/${r.id}/reset-password`, { password: pw }); toast("Password reset."); }
      catch (e) { toast(errorText(e), "error"); }
    }
    load();
    return el("div", { class: "card" }, [
      el("div", { class: "card-header" }, el("h2", {}, "Users")),
      el("div", { class: "card-body" }, [
        el("div", { class: "filter-bar" }, [u.username, u.full, u.password, u.role,
          el("button", { class: "btn btn-primary", onclick: create }, "+ Create user")]),
        el("table", {}, [el("thead", {}, el("tr", {}, [
          el("th", {}, "Username"), el("th", {}, "Name"), el("th", {}, "Role"),
          el("th", {}, "Status"), el("th", {}, "")])), tbody]),
      ]),
    ]);
  }

  window.KhataViews = window.KhataViews || {};
  window.KhataViews.settings = {
    mount(viewEl) {
      clear(viewEl).appendChild(el("div", {}, [
        el("div", { class: "topbar" }, el("div", {}, [
          el("h1", {}, "Settings"), el("div", { class: "meta" }, "Administration")])),
        appSettingsCard(),
        lookupCard("/api/component-types", "Component types"),
        lookupCard("/api/purity-types", "Purity types"),
        usersCard(),
      ]));
    },
  };
})();
