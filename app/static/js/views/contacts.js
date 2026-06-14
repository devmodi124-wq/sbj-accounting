// Reusable list/search/create/edit screen for customers and parties.
(function () {
  "use strict";
  const { el, clear, toast, errorText } = window.ui;

  function makeContactsView(opts) {
    let root, tbody, searchInput, editingId = null;
    const form = {};

    async function load() {
      const q = searchInput.value.trim();
      const rows = await api.get(opts.endpoint + (q ? `?q=${encodeURIComponent(q)}` : ""));
      clear(tbody);
      if (!rows.length) {
        tbody.appendChild(el("tr", {}, el("td", { colspan: "4", class: "muted" }, "No records.")));
      }
      for (const r of rows) {
        tbody.appendChild(
          el("tr", {}, [
            el("td", {}, r.name),
            el("td", {}, r.phone || "—"),
            el("td", {}, r.address || "—"),
            el("td", {}, el("button", { class: "btn btn-sm", onclick: () => edit(r) }, "Edit")),
          ])
        );
      }
    }

    function edit(r) {
      editingId = r ? r.id : null;
      form.name.value = r ? r.name : "";
      form.phone.value = r ? (r.phone || "") : "";
      form.address.value = r ? (r.address || "") : "";
      form.notes.value = r ? (r.notes || "") : "";
      form.title.textContent = r ? `Edit ${opts.singular}` : `New ${opts.singular}`;
      form.card.classList.remove("hidden");
      form.name.focus();
    }

    async function save() {
      const payload = {
        name: form.name.value.trim(),
        phone: form.phone.value.trim() || null,
        address: form.address.value.trim() || null,
        notes: form.notes.value.trim() || null,
      };
      if (!payload.name) return toast("Name is required.", "error");
      try {
        if (editingId) await api.put(`${opts.endpoint}/${editingId}`, payload);
        else await api.post(opts.endpoint, payload);
        form.card.classList.add("hidden");
        toast("Saved.");
        load();
      } catch (e) {
        toast(errorText(e), "error");
      }
    }

    function build(viewEl) {
      searchInput = el("input", { type: "search", placeholder: `Search ${opts.title.toLowerCase()}…`, oninput: load });
      tbody = el("tbody");
      form.name = el("input", { type: "text" });
      form.phone = el("input", { type: "text" });
      form.address = el("input", { type: "text" });
      form.notes = el("input", { type: "text" });
      form.title = el("h2", {}, `New ${opts.singular}`);
      form.card = el("div", { class: "card hidden" }, el("div", { class: "card-body" }, [
        form.title,
        el("div", { class: "form-grid cols-2", style: "margin-top:12px;" }, [
          field("Name", form.name), field("Phone", form.phone),
          field("Address", form.address), field("Notes", form.notes),
        ]),
        el("div", { class: "form-actions" }, [
          el("button", { class: "btn", onclick: () => form.card.classList.add("hidden") }, "Cancel"),
          el("button", { class: "btn btn-primary", onclick: save }, "Save"),
        ]),
      ]));

      root = el("div", {}, [
        el("div", { class: "topbar" }, [
          el("div", {}, [el("h1", {}, opts.title), el("div", { class: "meta" }, opts.subtitle)]),
          el("button", { class: "btn btn-primary", onclick: () => edit(null) }, `+ New ${opts.singular}`),
        ]),
        form.card,
        el("div", { class: "card" }, el("div", { class: "card-body" }, [
          el("div", { class: "filter-bar" }, searchInput),
          el("div", { class: "table-scroll" }, el("table", {}, [
            el("thead", {}, el("tr", {}, [th("Name"), th("Phone"), th("Address"), th("")])),
            tbody,
          ])),
        ])),
      ]);
      clear(viewEl).appendChild(root);
    }

    function field(label, input) {
      return el("div", { class: "field" }, [el("label", {}, label), input]);
    }
    function th(t) { return el("th", {}, t); }

    return {
      mount(viewEl) {
        build(viewEl);
        load();
      },
    };
  }

  window.KhataViews = window.KhataViews || {};
  window.KhataViews.customers = makeContactsView({
    endpoint: "/api/customers", title: "Customers", singular: "customer",
    subtitle: "Search, add and edit customer records",
  });
  window.KhataViews.parties = makeContactsView({
    endpoint: "/api/parties", title: "Suppliers", singular: "supplier",
    subtitle: "Search, add and edit supplier (party) records",
  });
})();
