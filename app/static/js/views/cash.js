// Cash Book: record cash received/paid + list, with per-row Edit and Delete.
// Entries auto-created from a sale's cash payment are locked (edit the order).
(function () {
  "use strict";
  const { el, clear, toast, errorText } = window.ui;

  function money(n) { return "₹ " + (Number(n) || 0).toLocaleString("en-IN"); }
  function field(label, node) { return el("div", { class: "field" }, [el("label", {}, label), node]); }

  function mount(viewEl) {
    let editingId = null;
    const f = {
      date: el("input", { type: "date", value: new Date().toISOString().slice(0, 10) }),
      person: el("input", { type: "text", placeholder: "person / party name" }),
      type: el("select", {}, [el("option", { value: "received" }, "Received (in)"),
        el("option", { value: "paid" }, "Paid (out)")]),
      amount: el("input", { type: "text", class: "amount-input" }),
      details: el("input", { type: "text", placeholder: "details" }),
    };
    const tbody = el("tbody");
    const errorBanner = el("div", { class: "banner-error hidden" });
    const saveBtn = el("button", { class: "btn btn-primary", onclick: save }, "Add entry");
    const cancelBtn = el("button", { class: "btn hidden", onclick: () => reset() }, "Cancel edit");

    async function load() {
      const rows = await api.get("/api/cash");
      clear(tbody);
      for (const r of rows) {
        const actions = r.auto_generated
          ? el("span", { class: "muted", style: "font-size:12px;" }, `auto · sale #${r.order_id}`)
          : el("span", {}, [
              el("button", { class: "btn btn-sm", onclick: () => edit(r) }, "Edit"),
              el("button", { class: "btn btn-sm", style: "margin-left:6px;border-color:var(--red);color:var(--red);",
                onclick: () => del(r) }, "Delete"),
            ]);
        tbody.appendChild(el("tr", {}, [
          el("td", {}, r.entry_date),
          el("td", {}, r.person_name || "—"),
          el("td", {}, r.entry_type === "received"
            ? el("span", { class: "pill pill-green" }, "Received")
            : el("span", { class: "pill pill-red" }, "Paid")),
          el("td", { class: "amount num " + (r.entry_type === "received" ? "positive" : "negative") }, money(r.amount)),
          el("td", {}, r.details || "—"),
          el("td", { style: "white-space:nowrap;" }, actions),
        ]));
      }
    }

    function edit(r) {
      editingId = r.id;
      f.date.value = r.entry_date;
      f.person.value = r.person_name || "";
      f.type.value = r.entry_type;
      f.amount.value = r.amount;
      f.details.value = r.details || "";
      saveBtn.textContent = `Update entry #${r.id}`;
      cancelBtn.classList.remove("hidden");
      window.scrollTo(0, 0);
    }

    async function del(r) {
      if (!confirm(`Delete this cash entry (${money(r.amount)})? This cannot be undone.`)) return;
      try { await api.del(`/api/cash/${r.id}`); toast("Deleted."); if (editingId === r.id) reset(); load(); }
      catch (e) { toast(errorText(e), "error"); }
    }

    function reset() {
      editingId = null;
      f.person.value = f.amount.value = f.details.value = "";
      f.type.value = "received";
      saveBtn.textContent = "Add entry";
      cancelBtn.classList.add("hidden");
      errorBanner.classList.add("hidden");
    }

    async function save() {
      errorBanner.classList.add("hidden");
      const amount = parseFloat(f.amount.value.replace(/,/g, ""));
      if (!amount) return toast("Enter an amount.", "error");
      const payload = {
        entry_date: f.date.value, person_name: f.person.value.trim(),
        entry_type: f.type.value, amount: String(amount), details: f.details.value.trim() || null,
      };
      try {
        if (editingId) await api.put(`/api/cash/${editingId}`, payload);
        else await api.post("/api/cash", payload);
        toast(editingId ? "Updated." : "Saved.");
        reset(); load();
      } catch (e) {
        if (e.status === 422) { errorBanner.textContent = e.detail || e.message; errorBanner.classList.remove("hidden"); }
        else toast(errorText(e), "error");
      }
    }

    clear(viewEl).appendChild(el("div", {}, [
      el("div", { class: "topbar" }, el("div", {}, [
        el("h1", {}, "Cash Book"), el("div", { class: "meta" }, "Record cash received and paid")])),
      el("div", { class: "card" }, el("div", { class: "card-body" }, [
        errorBanner,
        el("div", { class: "form-grid" }, [
          field("Date", f.date), field("Person", f.person),
          field("Type", f.type), field("Amount", f.amount),
        ]),
        field("Details", f.details),
        el("div", { class: "form-actions" }, [cancelBtn, saveBtn]),
      ])),
      el("div", { class: "card" }, el("div", { class: "card-body" }, el("div", { class: "table-scroll" },
        el("table", {}, [el("thead", {}, el("tr", {}, ["Date", "Person", "Type", "Amount", "Details", ""]
          .map((h) => el("th", {}, h)))), tbody])))),
    ]));
    load();
  }

  window.KhataViews = window.KhataViews || {};
  window.KhataViews.cash = { mount };
})();
