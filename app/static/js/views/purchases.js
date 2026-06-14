// Purchases: record supplier purchases + list with derived balance/status.
(function () {
  "use strict";
  const { el, clear, toast, errorText } = window.ui;

  function money(n) { return "₹ " + (Number(n) || 0).toLocaleString("en-IN"); }
  function num(v) { return parseFloat(String(v).replace(/,/g, "")) || 0; }
  function field(label, node) { return el("div", { class: "field" }, [el("label", {}, label), node]); }

  function mount(viewEl) {
    const f = {
      date: el("input", { type: "date", value: new Date().toISOString().slice(0, 10) }),
      party: el("input", { type: "text", placeholder: "supplier name" }),
      details: el("input", { type: "text", placeholder: "details" }),
      notes: el("input", { type: "text", placeholder: "e.g. 3 ct @ 6600" }),
      amount: el("input", { type: "text", class: "amount-input" }),
      paid: el("input", { type: "text", class: "amount-input" }),
    };
    const tbody = el("tbody");
    const errorBanner = el("div", { class: "banner-error hidden" });

    async function load() {
      const rows = await api.get("/api/purchases");
      clear(tbody);
      for (const r of rows) {
        tbody.appendChild(el("tr", {}, [
          el("td", {}, r.purchase_date),
          el("td", {}, r.party_name),
          el("td", {}, r.details || "—"),
          el("td", { class: "amount num" }, money(r.amount)),
          el("td", { class: "amount num" }, money(r.amount_paid)),
          el("td", { class: "amount num " + (num(r.balance) > 0 ? "negative" : "positive") }, money(r.balance)),
          el("td", {}, r.status === "paid"
            ? el("span", { class: "pill pill-green" }, "Paid")
            : el("span", { class: "pill pill-red" }, "Pending")),
        ]));
      }
    }
    async function save() {
      errorBanner.classList.add("hidden");
      if (!f.party.value.trim()) return toast("Supplier is required.", "error");
      try {
        await api.post("/api/purchases", {
          purchase_date: f.date.value, party_name: f.party.value.trim(),
          details: f.details.value.trim() || null, entry_notes: f.notes.value.trim() || null,
          amount: String(num(f.amount.value)), amount_paid: String(num(f.paid.value)),
        });
        f.party.value = f.details.value = f.notes.value = f.amount.value = f.paid.value = "";
        toast("Saved."); load();
      } catch (e) {
        if (e.status === 422) { errorBanner.textContent = e.detail || e.message; errorBanner.classList.remove("hidden"); }
        else toast(errorText(e), "error");
      }
    }

    clear(viewEl).appendChild(el("div", {}, [
      el("div", { class: "topbar" }, el("div", {}, [
        el("h1", {}, "Purchases"), el("div", { class: "meta" }, "Record purchases from suppliers")])),
      el("div", { class: "card" }, el("div", { class: "card-body" }, [
        errorBanner,
        el("div", { class: "form-grid" }, [
          field("Date", f.date), field("Supplier", f.party),
          field("Amount", f.amount), field("Amount paid", f.paid),
        ]),
        el("div", { class: "form-grid cols-2" }, [field("Details", f.details), field("Notes", f.notes)]),
        el("div", { class: "form-actions" }, el("button", { class: "btn btn-primary", onclick: save }, "Add purchase")),
      ])),
      el("div", { class: "card" }, el("div", { class: "card-body" }, el("div", { class: "table-scroll" },
        el("table", {}, [el("thead", {}, el("tr", {}, ["Date", "Supplier", "Details", "Amount", "Paid", "Balance", "Status"]
          .map((h) => el("th", {}, h)))), tbody])))),
    ]));
    load();
  }

  window.KhataViews = window.KhataViews || {};
  window.KhataViews.purchases = { mount };
})();
