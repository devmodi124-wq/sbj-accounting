// New / Edit Order screen. An order has one or more *items* (pieces); each item
// has its own category/weight/source, a component breakdown, and its own
// pictures. Order-level fields: customer, date, status, source, reference, notes.
(function () {
  "use strict";
  const { el, clear, toast, errorText } = window.ui;

  let components = [], purities = [], categories = [], weights = [], supplies = [], sources = [];
  let selectedCustomerId = null;
  let editingOrderId = null;   // null = create mode
  let pieces = [];             // array of piece-card controllers
  let piecesWrap, totalEl, balanceEl, errorBanner;
  const f = {}; // order-level fields + title/buttons

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

  function recomputeAll() {
    let total = 0;
    pieces.forEach((p) => { total += p.recompute(); });
    const balance = total - num(f.received.value);
    totalEl.textContent = money(total);
    balanceEl.textContent = money(balance);
    balanceEl.classList.toggle("zero", Math.abs(balance) < 0.005);
  }

  // ---- A single component row inside a piece ----
  function componentRow(c) {
    const compSel = el("select", { class: "comp" }, options(components));
    const puritySel = el("select", { class: "purity" }, options(purities, "—"));
    const pcs = el("input", { type: "text", class: "pcs" });
    const weight = el("input", { type: "text", class: "amount-input weight" });
    const rate = el("input", { type: "text", class: "amount-input rate" });
    const price = el("input", { type: "text", class: "amount-input price", oninput: recomputeAll });

    function syncPurity() {
      const labour = isLabour(Number(compSel.value));
      puritySel.disabled = labour;
      if (labour) puritySel.value = "";
    }
    compSel.addEventListener("change", syncPurity);

    if (c) {
      compSel.value = String(c.component_type_id);
      pcs.value = c.pcs ?? "";
      weight.value = c.weight ?? "";
      rate.value = c.rate ?? "";
      price.value = c.price ?? "";
    }
    syncPurity();
    if (c && c.purity_type_id && !puritySel.disabled) puritySel.value = String(c.purity_type_id);

    const tr = el("tr", {}, [
      el("td", {}, compSel), el("td", {}, pcs), el("td", {}, weight),
      el("td", {}, puritySel), el("td", {}, rate), el("td", {}, price),
      el("td", { class: "col-remove" },
        el("button", { class: "remove-row-btn", title: "Remove", onclick: () => { tr.remove(); recomputeAll(); } }, "×")),
    ]);
    return tr;
  }

  // ---- A piece (item) card ----
  function makePieceCard(data) {
    const ctrl = { pieceId: data ? data.id : null, newFiles: [], images: (data && data.images) ? data.images.slice() : [] };
    const nameInput = el("input", { type: "text", placeholder: "optional, e.g. Ladies ring with stone",
      value: data ? (data.item_name || "") : "" });
    const catSel = el("select", {}, options(categories, "Select category…"));
    const wtSel = el("select", {}, options(weights, "—"));
    const ssSel = el("select", {}, options(supplies, "—"));
    if (data) {
      catSel.value = data.item_category_id ? String(data.item_category_id) : "";
      wtSel.value = data.weight_type_id ? String(data.weight_type_id) : "";
      ssSel.value = data.supply_source_id ? String(data.supply_source_id) : "";
    }

    const rowsBody = el("tbody");
    const subtotalEl = el("span", { class: "num", style: "font-weight:600;" }, "₹ 0");
    const thumbs = el("div", { style: "display:flex;gap:10px;flex-wrap:wrap;margin-top:8px;" });
    const existingWrap = el("div", { style: "display:flex;gap:10px;flex-wrap:wrap;margin-top:8px;" });
    const fileInput = el("input", { type: "file", accept: "image/*", multiple: true, onchange: onPick });

    function addRow(c) { rowsBody.appendChild(componentRow(c)); }
    function onPick(e) { for (const file of e.target.files) ctrl.newFiles.push(file); e.target.value = ""; renderThumbs(); }
    function renderThumbs() {
      clear(thumbs);
      ctrl.newFiles.forEach((file, idx) => {
        const url = URL.createObjectURL(file);
        thumbs.appendChild(el("div", { style: "position:relative;" }, [
          el("img", { src: url, style: "width:64px;height:64px;object-fit:cover;border-radius:4px;border:1px solid var(--hairline);" }),
          el("button", { class: "remove-row-btn", title: "Remove",
            style: "position:absolute;top:-8px;right:-8px;background:#fff;border-radius:50%;",
            onclick: () => { ctrl.newFiles.splice(idx, 1); renderThumbs(); } }, "×"),
        ]));
      });
    }
    function renderExisting() {
      clear(existingWrap);
      if (!editingOrderId || !ctrl.pieceId) return;
      ctrl.images.forEach((img) => {
        const src = `/api/orders/${editingOrderId}/items/${ctrl.pieceId}/images/${img.id}`;
        existingWrap.appendChild(el("div", { style: "position:relative;" }, [
          el("a", { href: src, target: "_blank" },
            el("img", { src, style: "width:64px;height:64px;object-fit:cover;border-radius:4px;border:1px solid var(--hairline);" })),
          el("button", { class: "remove-row-btn", title: "Delete picture",
            style: "position:absolute;top:-8px;right:-8px;background:#fff;border-radius:50%;",
            onclick: async () => {
              try {
                await api.del(`/api/orders/${editingOrderId}/items/${ctrl.pieceId}/images/${img.id}`);
                ctrl.images = ctrl.images.filter((x) => x.id !== img.id);
                renderExisting();
              } catch (_) { toast("Delete failed.", "error"); }
            } }, "×"),
        ]));
      });
    }

    ctrl.recompute = function () {
      let sub = 0;
      rowsBody.querySelectorAll("tr").forEach((tr) => { sub += num(tr.querySelector(".price").value); });
      subtotalEl.textContent = money(sub);
      return sub;
    };
    ctrl.collect = function () {
      const comps = [];
      rowsBody.querySelectorAll("tr").forEach((tr) => {
        const compId = Number(tr.querySelector(".comp").value);
        if (!compId) return;
        const purityVal = tr.querySelector(".purity").value;
        const weightVal = tr.querySelector(".weight").value.trim();
        const rateVal = tr.querySelector(".rate").value.trim();
        const pcsVal = tr.querySelector(".pcs").value.trim();
        comps.push({
          component_type_id: compId,
          pcs: pcsVal ? parseInt(pcsVal, 10) : null,
          weight: weightVal ? String(num(weightVal)) : null,
          purity_type_id: purityVal ? Number(purityVal) : null,
          rate: rateVal ? String(num(rateVal)) : null,
          price: String(num(tr.querySelector(".price").value)),
        });
      });
      return {
        id: ctrl.pieceId,
        item_category_id: catSel.value ? Number(catSel.value) : null,
        item_name: nameInput.value.trim() || null,
        weight_type_id: wtSel.value ? Number(wtSel.value) : null,
        supply_source_id: ssSel.value ? Number(ssSel.value) : null,
        components: comps,
      };
    };
    ctrl.hasCategory = function () { return !!catSel.value; };
    ctrl.uploadNew = async function (orderId, pieceId) {
      if (!ctrl.newFiles.length) return;
      const fd = new FormData();
      ctrl.newFiles.forEach((file) => fd.append("files", file));
      await fetch(`/api/orders/${orderId}/items/${pieceId}/images`, { method: "POST", body: fd, credentials: "same-origin" });
    };

    const compTable = el("table", { class: "component-table" }, [
      el("thead", {}, el("tr", {}, ["Component", "Pcs", "Weight (g)", "Purity", "Rate", "Price", ""].map((h) => el("th", {}, h)))),
      rowsBody,
    ]);

    const removeBtn = el("button", { class: "btn btn-sm", style: "border-color:var(--red);color:var(--red);",
      onclick: () => removePiece(ctrl) }, "Remove item");

    ctrl.el = el("div", { class: "card", style: "margin-top:14px;background:var(--paper-alt);" },
      el("div", { class: "card-body" }, [
        el("div", { style: "display:flex;justify-content:space-between;align-items:center;" }, [
          el("h3", { class: "piece-title", style: "margin:0;" }, "Item"),
          removeBtn,
        ]),
        el("div", { class: "form-grid", style: "margin-top:10px;" }, [
          field("Category *", catSel), field("Item name", nameInput),
          field("Weight type", wtSel), field("Supplied from", ssSel),
        ]),
        el("div", { class: "form-section-title" }, "Components"),
        compTable,
        el("button", { class: "add-row-btn", onclick: () => { addRow(); recomputeAll(); } }, "+ Add component"),
        el("div", { style: "text-align:right;margin-top:6px;" }, ["Item subtotal: ", subtotalEl]),
        el("div", { class: "form-section-title" }, "Pictures"),
        existingWrap, fileInput, thumbs,
      ]));

    // Populate components.
    if (data && data.components && data.components.length) data.components.forEach((c) => addRow(c));
    else addRow();
    renderThumbs();
    renderExisting();
    return ctrl;
  }

  function renumberPieces() {
    pieces.forEach((p, i) => { p.el.querySelector(".piece-title").textContent = `Item ${i + 1}`; });
  }
  function addPiece(data) {
    const ctrl = makePieceCard(data || null);
    pieces.push(ctrl);
    piecesWrap.appendChild(ctrl.el);
    renumberPieces();
    recomputeAll();
  }
  function removePiece(ctrl) {
    if (pieces.length <= 1) return toast("An order needs at least one item.", "error");
    pieces = pieces.filter((p) => p !== ctrl);
    ctrl.el.remove();
    renumberPieces();
    recomputeAll();
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

  function setMode() {
    f.title.textContent = editingOrderId ? `Edit Order #${editingOrderId}` : "New Order";
    f.saveBtn.textContent = editingOrderId ? "Update Order" : "Save Order";
  }

  async function save(asDraft) {
    errorBanner.classList.add("hidden");
    const name = f.customerInput.value.trim();
    if (!selectedCustomerId && !name) return toast("Choose or enter a customer.", "error");
    if (!pieces.length) return toast("Add at least one item.", "error");
    if (pieces.some((p) => !p.hasCategory())) return toast("Every item needs a category.", "error");

    const payload = {
      customer_id: selectedCustomerId,
      customer_name: selectedCustomerId ? null : name,
      order_date: f.date.value,
      order_code: f.code.value.trim() || null,
      notes: f.notes.value.trim() || null,
      reference: f.reference.value.trim() || null,
      source_id: f.source.value ? Number(f.source.value) : null,
      status: asDraft ? "pending" : f.status.value,
      payment_received: String(num(f.received.value)),
      payment_mode: f.mode.value,
      items: pieces.map((p) => p.collect()),
    };
    try {
      const order = editingOrderId
        ? await api.put(`/api/orders/${editingOrderId}`, payload)
        : await api.post("/api/orders", payload);
      // Upload each piece's new pictures to its saved item id (response items are
      // ordered by sort_order, which matches the submission order).
      for (let i = 0; i < pieces.length; i++) {
        const item = order.items[i];
        if (item) await pieces[i].uploadNew(order.id, item.id);
      }
      toast(editingOrderId ? "Order updated." : (asDraft ? "Draft saved." : "Order saved."));
      reset();
    } catch (e) {
      if (e.status === 422) { errorBanner.textContent = e.detail || e.message; errorBanner.classList.remove("hidden"); }
      else toast(errorText(e), "error");
    }
  }

  function reset() {
    editingOrderId = null;
    selectedCustomerId = null;
    f.customerInput.value = ""; f.code.value = ""; f.notes.value = "";
    f.reference.value = ""; f.source.value = ""; f.received.value = "0";
    f.status.value = "pending"; f.mode.value = "cash";
    pieces = [];
    clear(piecesWrap);
    addPiece();
    recomputeAll();
    setMode();
    errorBanner.classList.add("hidden");
    window.scrollTo(0, 0);
  }

  async function edit(orderId) {
    const o = await api.get(`/api/orders/${orderId}`);
    editingOrderId = o.id;
    let custName = "";
    try { custName = (await api.get(`/api/customers/${o.customer_id}`)).name; } catch (_) {}
    f.customerInput.value = custName;
    selectedCustomerId = o.customer_id;
    f.date.value = o.order_date;
    f.code.value = o.order_code || "";
    f.notes.value = o.notes || "";
    f.reference.value = o.reference || "";
    f.source.value = o.source_id ? String(o.source_id) : "";
    f.status.value = o.status;
    f.received.value = o.payment_received;
    f.mode.value = o.payment_mode || "cash";
    pieces = [];
    clear(piecesWrap);
    if (o.items.length) o.items.forEach((it) => addPiece(it)); else addPiece();
    setMode();
    recomputeAll();
    window.scrollTo(0, 0);
  }

  async function mount(viewEl) {
    [components, purities, categories, weights, supplies, sources] = await Promise.all([
      api.get("/api/component-types?active_only=true"),
      api.get("/api/purity-types?active_only=true"),
      api.get("/api/item-categories?active_only=true"),
      api.get("/api/weight-types?active_only=true"),
      api.get("/api/supply-sources?active_only=true"),
      api.get("/api/order-sources?active_only=true"),
    ]);
    f.date = el("input", { type: "date", value: new Date().toISOString().slice(0, 10) });
    f.code = el("input", { type: "text", placeholder: "optional" });
    f.notes = el("input", { type: "text", placeholder: "notes" });
    f.reference = el("input", { type: "text", placeholder: "e.g. friends / family / referred by" });
    f.source = el("select", {}, options(sources, "—"));
    f.status = el("select", {}, [el("option", { value: "pending" }, "Pending (in progress)"),
      el("option", { value: "delivered" }, "Delivered")]);
    f.received = el("input", { type: "text", class: "num", value: "0", oninput: recomputeAll });
    f.mode = el("select", {}, ["cash", "upi", "bank_transfer", "old_gold_exchange", "other"]
      .map((m) => el("option", { value: m }, m.replace(/_/g, " "))));
    f.title = el("h1", {}, "New Order");
    f.saveBtn = el("button", { class: "btn btn-primary", onclick: () => save(false) }, "Save Order");

    piecesWrap = el("div", {});
    totalEl = el("div", { class: "total-display num" }, "₹ 0");
    balanceEl = el("div", { class: "total-display balance num" }, "₹ 0");
    errorBanner = el("div", { class: "banner-error hidden" });

    clear(viewEl).appendChild(el("div", {}, [
      el("div", { class: "topbar" }, el("div", {}, [
        f.title, el("div", { class: "meta" }, "Record or edit a sale / custom order")])),
      el("div", { class: "card" }, el("div", { class: "card-body" }, [
        errorBanner,
        el("div", { class: "form-section-title" }, "Customer & order details"),
        el("div", { class: "form-grid" }, [
          field("Customer", customerSearch(), 2),
          field("Order date", f.date), field("Status", f.status),
          field("Source", f.source), field("Reference", f.reference),
          field("Order code", f.code), field("Notes", f.notes, 3),
        ]),
        el("div", { class: "form-section-title" }, "Items"),
        piecesWrap,
        el("button", { class: "add-row-btn", style: "margin-top:12px;", onclick: () => addPiece() }, "+ Add item"),
        el("div", { class: "form-section-title" }, "Payment"),
        el("div", { class: "totals-box" }, [
          field("Order total", totalEl),
          field("Payment received", f.received),
          field("Balance due", balanceEl),
          field("Payment mode", f.mode),
        ]),
        el("div", { class: "form-actions" }, [
          el("button", { class: "btn", onclick: reset }, "Cancel"),
          el("button", { class: "btn", onclick: () => save(true) }, "Save as Draft"),
          f.saveBtn,
        ]),
      ])),
    ]));
    addPiece();
    recomputeAll();
    setMode();
  }

  window.KhataViews = window.KhataViews || {};
  window.KhataViews.entry = { mount, edit };
})();
