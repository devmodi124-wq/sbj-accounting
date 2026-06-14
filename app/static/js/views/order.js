// New Order screen: customer search-or-create, category/weight/source dropdowns,
// dynamic component rows, live totals, and multiple pictures (stored encrypted).
(function () {
  "use strict";
  const { el, clear, toast, errorText } = window.ui;

  let components = [], purities = [], categories = [], weights = [], supplies = [];
  let selectedCustomerId = null;
  let selectedImages = [];
  let rowsBody, totalEl, balanceEl, errorBanner, thumbs;
  const f = {}; // form fields

  function money(n) {
    const v = Number(n) || 0;
    return "₹ " + v.toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 2 });
  }
  function num(v) { return parseFloat(String(v).replace(/,/g, "")) || 0; }
  function field(label, node, span) {
    return el("div", { class: "field", style: span ? `grid-column: span ${span};` : null },
      [el("label", {}, label), node]);
  }
  function options(list, placeholder) {
    const opts = list.map((x) => el("option", { value: x.id }, x.name));
    return placeholder !== undefined ? [el("option", { value: "" }, placeholder)].concat(opts) : opts;
  }

  function isLabour(componentId) {
    const c = components.find((x) => x.id === componentId);
    return c && /labour/i.test(c.name);
  }

  function recompute() {
    let total = 0;
    rowsBody.querySelectorAll("tr").forEach((tr) => { total += num(tr.querySelector(".price").value); });
    const balance = total - num(f.received.value);
    totalEl.textContent = money(total);
    balanceEl.textContent = money(balance);
    balanceEl.classList.toggle("zero", Math.abs(balance) < 0.005);
  }

  function componentRow() {
    const compSel = el("select", { class: "comp" }, options(components));
    const puritySel = el("select", { class: "purity" }, options(purities, "—"));
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
        price: String(num(tr.querySelector(".price").value)),
      });
    });
    return items;
  }

  // ---- Customer type-ahead ----
  function customerSearch() {
    const input = el("input", { type: "text", autocomplete: "off", placeholder: "Type a name to search…" });
    const dropdown = el("div", { class: "customer-dropdown", style: "display:none;" });
    const wrap = el("div", { class: "customer-search-wrap" }, [input, dropdown]);
    let timer = null;
    function close() { dropdown.style.display = "none"; }
    async function run() {
      selectedCustomerId = null;
      const q = input.value.trim();
      if (!q) return close();
      let rows = [];
      try { rows = await api.get(`/api/customers?q=${encodeURIComponent(q)}`); } catch (e) { return; }
      clear(dropdown);
      rows.forEach((r) => dropdown.appendChild(
        el("div", { class: "opt", onmousedown: () => { input.value = r.name; selectedCustomerId = r.id; close(); } },
          [r.name, el("span", { class: "phone" }, r.phone || "")])));
      dropdown.appendChild(el("div", { class: "opt-new", onmousedown: close }, `+ Add new customer "${q}"`));
      dropdown.style.display = "block";
    }
    input.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(run, 180); });
    input.addEventListener("blur", () => setTimeout(close, 150));
    f.customerInput = input;
    return wrap;
  }

  // ---- Pictures ----
  function onPickImages(e) {
    for (const file of e.target.files) selectedImages.push(file);
    e.target.value = "";
    renderThumbs();
  }
  function renderThumbs() {
    clear(thumbs);
    selectedImages.forEach((file, idx) => {
      const url = URL.createObjectURL(file);
      thumbs.appendChild(el("div", { style: "position:relative;" }, [
        el("img", { src: url, style: "width:64px;height:64px;object-fit:cover;border-radius:4px;border:1px solid var(--hairline);" }),
        el("button", { class: "remove-row-btn", title: "Remove",
          style: "position:absolute;top:-8px;right:-8px;background:#fff;border-radius:50%;",
          onclick: () => { selectedImages.splice(idx, 1); renderThumbs(); } }, "×"),
      ]));
    });
  }
  async function uploadImages(orderId) {
    if (!selectedImages.length) return;
    const fd = new FormData();
    selectedImages.forEach((file) => fd.append("files", file));
    await fetch(`/api/orders/${orderId}/images`, { method: "POST", body: fd, credentials: "same-origin" });
  }

  async function save(asDraft) {
    errorBanner.classList.add("hidden");
    const name = f.customerInput.value.trim();
    if (!selectedCustomerId && !name) return toast("Choose or enter a customer.", "error");
    if (!f.category.value) return toast("Item category is required.", "error");

    const payload = {
      customer_id: selectedCustomerId,
      customer_name: selectedCustomerId ? null : name,
      order_date: f.date.value,
      item_category_id: Number(f.category.value),
      item_name: f.itemName.value.trim() || null,
      weight_type_id: f.weight.value ? Number(f.weight.value) : null,
      supply_source_id: f.supply.value ? Number(f.supply.value) : null,
      order_code: f.code.value.trim() || null,
      notes: f.notes.value.trim() || null,
      status: asDraft ? "pending" : f.status.value,
      payment_received: String(num(f.received.value)),
      payment_mode: f.mode.value,
      items: collectItems(),
    };
    try {
      const created = await api.post("/api/orders", payload);
      await uploadImages(created.id);
      toast(asDraft ? "Draft saved." : "Order saved.");
      reset();
    } catch (e) {
      if (e.status === 422) { errorBanner.textContent = e.detail || e.message; errorBanner.classList.remove("hidden"); }
      else toast(errorText(e), "error");
    }
  }

  function reset() {
    selectedCustomerId = null;
    selectedImages = [];
    f.customerInput.value = ""; f.itemName.value = ""; f.code.value = "";
    f.notes.value = ""; f.received.value = "0"; f.status.value = "pending";
    f.mode.value = "cash"; f.category.value = ""; f.weight.value = ""; f.supply.value = "";
    clear(rowsBody); addRow(); recompute();
    renderThumbs();
    errorBanner.classList.add("hidden");
  }

  async function mount(viewEl) {
    [components, purities, categories, weights, supplies] = await Promise.all([
      api.get("/api/component-types?active_only=true"),
      api.get("/api/purity-types?active_only=true"),
      api.get("/api/item-categories?active_only=true"),
      api.get("/api/weight-types?active_only=true"),
      api.get("/api/supply-sources?active_only=true"),
    ]);
    f.date = el("input", { type: "date", value: new Date().toISOString().slice(0, 10) });
    f.category = el("select", {}, options(categories, "Select category…"));
    f.itemName = el("input", { type: "text", placeholder: "optional, e.g. Ladies ring with stone" });
    f.weight = el("select", {}, options(weights, "—"));
    f.supply = el("select", {}, options(supplies, "—"));
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
    thumbs = el("div", { style: "display:flex;gap:10px;flex-wrap:wrap;margin-top:8px;" });
    const imgInput = el("input", { type: "file", accept: "image/*", multiple: true, onchange: onPickImages });

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
          field("Category *", f.category), field("Item name", f.itemName),
          field("Weight type", f.weight), field("Supplied from", f.supply),
          field("Order code", f.code), field("Notes", f.notes, 3),
        ]),
        el("div", { class: "form-section-title" }, "Item components"),
        compTable,
        el("button", { class: "add-row-btn", onclick: addRow }, "+ Add component"),
        el("div", { class: "form-section-title" }, "Pictures"),
        imgInput, thumbs,
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
