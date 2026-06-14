// Cash book: record money in/out + list.
(function () {
  "use strict";
  const { el, clear, toast, errorText } = window.ui;

  function money(n) { return "₹ " + (Number(n) || 0).toLocaleString("en-IN"); }
  function field(label, node) { return el("div", { class: "field" }, [el("label", {}, label), node]); }

  function mount(viewEl) {
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

    async function load() {
      const rows = await api.get("/api/cash");
      clear(tbody);
      for (const r of rows) {
        tbody.appendChild(el("tr", {}, [
          el("td", {}, r.entry_date),
          el("td", {}, r.person_name || "—"),
          el("td", {}, r.entry_type === "received"
            ? el("span", { class: "pill pill-green" }, "Received")
            : el("span", { class: "pill pill-red" }, "Paid")),
          el("td", { class: "amount num " + (r.entry_type === "received" ? "positive" : "negative") }, money(r.amount)),
          el("td", {}, r.details || "—"),
        ]));
      }
    }
    async function save() {
      errorBanner.classList.add("hidden");
      const amount = parseFloat(f.amount.value.replace(/,/g, ""));
      if (!amount) return toast("Enter an amount.", "error");
      try {
        await api.post("/api/cash", {
          entry_date: f.date.value, person_name: f.person.value.trim(),
          entry_type: f.type.value, amount: String(amount), details: f.details.value.trim() || null,
        });
        f.person.value = f.amount.value = f.details.value = "";
        toast("Saved."); load();
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
        el("div", { class: "form-actions" }, el("button", { class: "btn btn-primary", onclick: save }, "Add entry")),
      ])),
      el("div", { class: "card" }, el("div", { class: "card-body" }, el("div", { class: "table-scroll" },
        el("table", {}, [el("thead", {}, el("tr", {}, ["Date", "Person", "Type", "Amount", "Details"]
          .map((h) => el("th", {}, h)))), tbody])))),
    ]));
    load();
  }

  window.KhataViews = window.KhataViews || {};
  window.KhataViews.cash = { mount };
})();
