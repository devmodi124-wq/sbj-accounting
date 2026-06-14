// New Order screen: customer search-or-create, dynamic component rows, live totals.
(function () {
  "use strict";
  const { el, clear, toast, errorText } = window.ui;

  let components = [], purities = [];
  let selectedCustomerId = null;
  let rowsBody, totalEl, balanceEl, errorBanner;
  const f = {}; // form fields

  function money(n) {
    const v = Number(n) || 0;
    return "₹ " + v.toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 2 });
  }
  function num(v) { return parseFloat(String(v).replace(/,/g, "")) || 0; }

  function isLabour(componentId) {
    const c = components.find((x) => x.id === componentId);
    return c && /labour/i.test(c.name);
  }

  function recompute() {
    let total = 0;
    rowsBody.querySelectorAll("tr").forEach((tr) => { total += num(tr.querySelector(".price").value); });
    const received = num(f.received.value);
    const balance = total - received;
    totalEl.textContent = money(total);
    balanceEl.textContent = money(balance);
    balanceEl.classList.toggle("zero", Math.abs(balance) < 0.005);
  }

  function componentRow() {
    const compSel = el("select", { class: "comp" },
      components.map((c) => el("option", { value: c.id }, c.name)));
    const puritySel = el("select", { class: "purity" },
      [el("option", { value: "" }, "—")].concat(
        purities.map((p) => el("option", { value: p.id }, p.name))));
    const pcs = el("input", { type: "text", class: "pcs" });
    const weight = el("input", { type: "text", class: "amount-input weight" });
    const rate = el("input", { type: "text", class: "amount-input rate" });
    const price = el("input", { type: "text", class: "amount-input price", oninput: recompute });

    function syncPurity() {
      const labour = isLabour(Number(compSel.value));
      puritySel.disabled = labour;
      if (labour) puritySel.value = "";
    }
    compSel.addEventListener("change", syncPurity);
    syncPurity();

    const tr = el("tr", {}, [
      el("td", {}, compSel), el("td", {}, pcs), el("td", {}, weight),
      el("td", {}, puritySel), el("td", {}, rate), el("td", {}, price),
      el("td", { class: "col-remove" },
        el("button", { class: "remove-row-btn", title: "Remove", onclick: () => { tr.remove(); recompute(); } }, "×")),
    ]);
    return tr;
  }

  function addRow() { rowsBody.appendChild(componentRow()); }

  function collectItems() {
    const items = [];
    rowsBody.querySelectorAll("tr").forEach((tr) => {
      const price = num(tr.querySelector(".price").value);
      const compId = Number(tr.querySelector(".comp").value);
      if (!compId) return;
      const purityVal = tr.querySelector(".purity").value;
      const weightVal = tr.querySelector(".weight").value.trim();
      const rateVal = tr.querySelector(".rate").value.trim();
      const pcsVal = tr.querySelector(".pcs").value.trim();
      items.push({
        component_type_id: compId,
        pcs: pcsVal ? parseInt(pcsVal, 10) : null,
        weight: weightVal ? String(num(weightVal)) : null,
        purity_type_id: purityVal ? Number(purityVal) : null,
        rate: rateVal ? String(num(rateVal)) : null,
        price: String(price),
      });
    });
    return items;
  }

  // ---- Customer type-ahead ----
  function customerSearch() {
    const input = el("input", { type: "text", id: "custSearch", autocomplete: "off",
      placeholder: "Type a name to search…" });
    const dropdown = el("div", { class: "customer-dropdown", style: "display:none;" });
    const wrap = el("div", { class: "customer-search-wrap" }, [input, dropdown]);
    let timer = null;

    function close() { dropdown.style.display = "none"; }
    async function run() {
      selectedCustomerId = null; // typing means "maybe new" until a pick
      const q = input.value.trim();
      if (!q) return close();
      let rows = [];
      try { rows = await api.get(`/api/customers?q=${encodeURIComponent(q)}`); } catch (e) { return; }
      clear(dropdown);
      rows.forEach((r) => dropdown.appendChild(
        el("div", { class: "opt", onmousedown: () => pick(r) },
          [r.name, el("span", { class: "phone" }, r.phone || "")])));
      dropdown.appendChild(el("div", { class: "opt-new", onmousedown: () => { close(); } },
        `+ Add new customer "${q}"`));
      dropdown.style.display = "block";
    }
    function pick(r) { input.value = r.name; selectedCustomerId = r.id; close(); }

    input.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(run, 180); });
    input.addEventListener("blur", () => setTimeout(close, 150));
    f.customerInput = input;
    return wrap;
  }

  function field(label, node, span) {
    return el("div", { class: "field", style: span ? `grid-column: span ${span};` : null },
      [el("label", {}, label), node]);
  }

  async function save(asDraft) {
    errorBanner.classList.add("hidden");
    const name = f.customerInput.value.trim();
    if (!selectedCustomerId && !name) return toast("Choose or enter a customer.", "error");
    if (!f.itemName.value.trim()) return toast("Item name is required.", "error");

    const payload = {
      customer_id: selectedCustomerId,
      customer_name: selectedCustomerId ? null : name,
      order_date: f.date.value,
      item_name: f.itemName.value.trim(),
      order_code: f.code.value.trim() || null,
      notes: f.notes.value.trim() || null,
      status: asDraft ? "pending" : f.status.value,
      payment_received: String(num(f.received.value)),
      payment_mode: f.mode.value,
      items: collectItems(),
    };
    try {
      await api.post("/api/orders", payload);
      toast(asDraft ? "Draft saved." : "Order saved.");
      reset();
    } catch (e) {
      if (e.status === 422) { errorBanner.textContent = e.detail || e.message; errorBanner.classList.remove("hidden"); }
      else toast(errorText(e), "error");
    }
  }

  function reset() {
    selectedCustomerId = null;
    f.customerInput.value = ""; f.itemName.value = ""; f.code.value = "";
    f.notes.value = ""; f.received.value = "0"; f.status.value = "pending"; f.mode.value = "cash";
    clear(rowsBody); addRow(); recompute();
    errorBanner.classList.add("hidden");
  }

  async function mount(viewEl) {
    [components, purities] = await Promise.all([
      api.get("/api/component-types?active_only=true"),
      api.get("/api/purity-types?active_only=true"),
    ]);
    f.date = el("input", { type: "date", value: new Date().toISOString().slice(0, 10) });
    f.itemName = el("input", { type: "text", placeholder: "e.g. Ring, Necklace" });
    f.code = el("input", { type: "text", placeholder: "optional" });
    f.notes = el("input", { type: "text", placeholder: "reference / notes" });
    f.status = el("select", {}, [el("option", { value: "pending" }, "Pending (in progress)"),
      el("option", { value: "delivered" }, "Delivered")]);
    f.received = el("input", { type: "text", class: "num", value: "0", oninput: recompute });
    f.mode = el("select", {}, ["cash", "upi", "bank_transfer", "old_gold_exchange", "other"]
      .map((m) => el("option", { value: m }, m.replace(/_/g, " "))));

    rowsBody = el("tbody");
    totalEl = el("div", { class: "total-display num" }, "₹ 0");
    balanceEl = el("div", { class: "total-display balance num" }, "₹ 0");
    errorBanner = el("div", { class: "banner-error hidden" });

    const compTable = el("table", { class: "component-table" }, [
      el("thead", {}, el("tr", {}, ["Component", "Pcs", "Weight (g)", "Purity", "Rate", "Price", ""]
        .map((h) => el("th", {}, h)))),
      rowsBody,
    ]);

    clear(viewEl).appendChild(el("div", {}, [
      el("div", { class: "topbar" }, el("div", {}, [
        el("h1", {}, "New Order"), el("div", { class: "meta" }, "Record a sale or custom order")])),
      el("div", { class: "card" }, el("div", { class: "card-body" }, [
        errorBanner,
        el("div", { class: "form-section-title" }, "Customer & order details"),
        el("div", { class: "form-grid" }, [
          field("Customer", customerSearch(), 2),
          field("Order date", f.date), field("Status", f.status),
          field("Item name", f.itemName), field("Order code", f.code),
          field("Notes", f.notes, 2),
        ]),
        el("div", { class: "form-section-title" }, "Item components"),
        compTable,
        el("button", { class: "add-row-btn", onclick: addRow }, "+ Add component"),
        el("div", { class: "form-section-title" }, "Payment"),
        el("div", { class: "totals-box" }, [
          field("Total amount", totalEl),
          field("Payment received", f.received),
          field("Balance due", balanceEl),
          field("Payment mode", f.mode),
        ]),
        el("div", { class: "form-actions" }, [
          el("button", { class: "btn", onclick: reset }, "Cancel"),
          el("button", { class: "btn", onclick: () => save(true) }, "Save as Draft"),
          el("button", { class: "btn btn-primary", onclick: () => save(false) }, "Save Order"),
        ]),
      ])),
    ]));
    addRow();
    recompute();
  }

  window.KhataViews = window.KhataViews || {};
  window.KhataViews.entry = { mount };
})();
