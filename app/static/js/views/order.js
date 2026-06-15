// New / Edit Order screen. An order has one or more *items* (pieces); each item
// is priced from a weights×rates panel (gross/diamond/stone/others + rates →
// auto net weight + auto subtotal). Payment can split across modes; the order
// total = Σ item subtotals, balance = total − payments received.
(function () {
  "use strict";
  const { el, clear, toast, errorText } = window.ui;

  const MODES = ["cash", "upi", "bank_transfer", "old_gold_exchange", "other"];

  let purities = [], categories = [], weights = [], supplies = [], sources = [];
  let selectedCustomerId = null;
  let editingOrderId = null;   // null = create mode
  let pieces = [];             // piece-card controllers
  let paymentRows = [];        // payment-line controllers
  let piecesWrap, paymentsWrap, totalEl, receivedEl, balanceEl, errorBanner;
  const f = {}; // order-level fields + title/buttons

  function money(n) {
    const v = Number(n) || 0;
    return "₹ " + v.toLocaleString("en-IN", { minimumFractionDigits: 0, maximumFractionDigits: 2 });
  }
  function num(v) { return parseFloat(String(v == null ? "" : v).replace(/,/g, "")) || 0; }
  function strOrNull(v) { const s = String(v == null ? "" : v).trim(); return s ? String(num(s)) : null; }
  function field(label, node, span) {
    return el("div", { class: "field", style: span ? `grid-column: span ${span};` : null },
      [el("label", {}, label), node]);
  }
  function options(list, placeholder) {
    const opts = list.map((x) => el("option", { value: x.id }, x.name));
    return placeholder !== undefined ? [el("option", { value: "" }, placeholder)].concat(opts) : opts;
  }

  function recomputeAll() {
    let total = 0;
    pieces.forEach((p) => { total += p.recompute(); });
    let received = 0;
    paymentRows.forEach((r) => { received += num(r.amountInput.value); });
    const balance = total - received;
    totalEl.textContent = money(total);
    receivedEl.textContent = money(received);
    balanceEl.textContent = money(balance);
    balanceEl.classList.toggle("zero", Math.abs(balance) < 0.005);
  }

  // ---- A piece (item) card with a weights×rates pricing panel ----
  function makePieceCard(data) {
    const ctrl = { pieceId: data ? data.id : null, newFiles: [], images: (data && data.images) ? data.images.slice() : [] };
    const nameInput = el("input", { type: "text", placeholder: "optional, e.g. Ladies ring",
      value: data ? (data.item_name || "") : "" });
    const catSel = el("select", {}, options(categories, "Select category…"));
    const wtSel = el("select", {}, options(weights, "—"));
    const ssSel = el("select", {}, options(supplies, "—"));
    const puSel = el("select", {}, options(purities, "—"));

    // weight/rate inputs
    const inp = (ph) => el("input", { type: "text", class: "amount-input", placeholder: ph || "", oninput: recomputeAll });
    const gross = inp("g"), metalRate = inp("₹/g");
    const diaWt = inp("ct"), diaRate = inp("₹/ct");
    const stoneWt = inp("ct"), stoneRate = inp("₹/ct");
    const othersWt = inp("ct"), othersRate = inp("₹/ct");
    const labourRate = inp("₹/g");
    const netEl = el("span", { class: "num", style: "font-weight:600;" }, "0.000 g");
    const breakdownEl = el("div", { class: "muted", style: "font-size:12px;margin-top:4px;" }, "");
    const subtotalEl = el("span", { class: "num", style: "font-weight:600;" }, "₹ 0");

    if (data) {
      catSel.value = data.item_category_id ? String(data.item_category_id) : "";
      wtSel.value = data.weight_type_id ? String(data.weight_type_id) : "";
      ssSel.value = data.supply_source_id ? String(data.supply_source_id) : "";
      puSel.value = data.purity_type_id ? String(data.purity_type_id) : "";
      gross.value = data.gross_weight ?? ""; metalRate.value = data.metal_rate ?? "";
      diaWt.value = data.diamond_weight ?? ""; diaRate.value = data.diamond_rate ?? "";
      stoneWt.value = data.stone_weight ?? ""; stoneRate.value = data.stone_rate ?? "";
      othersWt.value = data.others_weight ?? ""; othersRate.value = data.others_rate ?? "";
      labourRate.value = data.labour_rate ?? "";
    }

    // pictures
    const thumbs = el("div", { style: "display:flex;gap:10px;flex-wrap:wrap;margin-top:8px;" });
    const existingWrap = el("div", { style: "display:flex;gap:10px;flex-wrap:wrap;margin-top:8px;" });
    const fileInput = el("input", { type: "file", accept: "image/*", multiple: true, onchange: onPick });
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
      const g = num(gross.value), d = num(diaWt.value), s = num(stoneWt.value), o = num(othersWt.value);
      let net = g - (d + s + o) / 5;
      if (net < 0) net = 0;
      const metalV = net * num(metalRate.value);
      const diaV = d * num(diaRate.value);
      const stoneV = s * num(stoneRate.value);
      const othersV = o * num(othersRate.value);
      const labourV = net * num(labourRate.value);
      const sub = metalV + diaV + stoneV + othersV + labourV;
      netEl.textContent = net.toFixed(3) + " g";
      const parts = [];
      if (metalV) parts.push("metal " + money(metalV));
      if (diaV) parts.push("diamond " + money(diaV));
      if (stoneV) parts.push("stone " + money(stoneV));
      if (othersV) parts.push("others " + money(othersV));
      if (labourV) parts.push("labour " + money(labourV));
      breakdownEl.textContent = parts.join("  ·  ");
      subtotalEl.textContent = money(sub);
      return sub;
    };
    ctrl.collect = function () {
      return {
        id: ctrl.pieceId,
        item_category_id: catSel.value ? Number(catSel.value) : null,
        item_name: nameInput.value.trim() || null,
        weight_type_id: wtSel.value ? Number(wtSel.value) : null,
        supply_source_id: ssSel.value ? Number(ssSel.value) : null,
        purity_type_id: puSel.value ? Number(puSel.value) : null,
        gross_weight: strOrNull(gross.value),
        diamond_weight: strOrNull(diaWt.value),
        stone_weight: strOrNull(stoneWt.value),
        others_weight: strOrNull(othersWt.value),
        metal_rate: strOrNull(metalRate.value),
        diamond_rate: strOrNull(diaRate.value),
        stone_rate: strOrNull(stoneRate.value),
        others_rate: strOrNull(othersRate.value),
        labour_rate: strOrNull(labourRate.value),
      };
    };
    ctrl.hasCategory = function () { return !!catSel.value; };
    ctrl.uploadNew = async function (orderId, pieceId) {
      if (!ctrl.newFiles.length) return;
      const fd = new FormData();
      ctrl.newFiles.forEach((file) => fd.append("files", file));
      await fetch(`/api/orders/${orderId}/items/${pieceId}/images`, { method: "POST", body: fd, credentials: "same-origin" });
    };

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
          field("Purity", puSel), field("Weight type", wtSel), field("Supplied from", ssSel),
        ]),
        el("div", { class: "form-section-title" }, "Weights & rates"),
        el("div", { class: "form-grid cols-2" }, [
          field("Gross weight (g)", gross), field("Metal rate (₹/g)", metalRate),
          field("Diamond (ct)", diaWt), field("Diamond rate (₹/ct)", diaRate),
          field("Stone (ct)", stoneWt), field("Stone rate (₹/ct)", stoneRate),
          field("Others (ct)", othersWt), field("Others rate (₹/ct)", othersRate),
          field("Labour rate (₹/g)", labourRate),
          field("Net (metal) weight", netEl),
        ]),
        breakdownEl,
        el("div", { style: "text-align:right;margin-top:6px;" }, ["Item subtotal: ", subtotalEl]),
        el("div", { class: "form-section-title" }, "Pictures"),
        existingWrap, fileInput, thumbs,
      ]));

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

  // ---- Payment lines ----
  function makePaymentRow(data) {
    const modeSel = el("select", {}, MODES.map((m) => el("option", { value: m }, m.replace(/_/g, " "))));
    const amountInput = el("input", { type: "text", class: "num", value: data ? (data.amount ?? "") : "", oninput: recomputeAll });
    if (data && data.mode) modeSel.value = data.mode;
    const ctrl = { modeSel, amountInput };
    ctrl.collect = function () {
      const amt = num(amountInput.value);
      if (amt <= 0) return null;
      return { mode: modeSel.value, amount: String(amt) };
    };
    ctrl.el = el("div", { style: "display:flex;gap:8px;align-items:center;margin-bottom:6px;" }, [
      modeSel, amountInput,
      el("button", { class: "remove-row-btn", title: "Remove", onclick: () => removePayment(ctrl) }, "×"),
    ]);
    return ctrl;
  }
  function addPayment(data) {
    const ctrl = makePaymentRow(data || null);
    paymentRows.push(ctrl);
    paymentsWrap.appendChild(ctrl.el);
    recomputeAll();
  }
  function removePayment(ctrl) {
    paymentRows = paymentRows.filter((r) => r !== ctrl);
    ctrl.el.remove();
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
      payments: paymentRows.map((r) => r.collect()).filter(Boolean),
      items: pieces.map((p) => p.collect()),
    };
    try {
      const order = editingOrderId
        ? await api.put(`/api/orders/${editingOrderId}`, payload)
        : await api.post("/api/orders", payload);
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
    f.reference.value = ""; f.source.value = ""; f.status.value = "pending";
    pieces = []; clear(piecesWrap); addPiece();
    paymentRows = []; clear(paymentsWrap); addPayment();
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
    pieces = []; clear(piecesWrap);
    if (o.items.length) o.items.forEach((it) => addPiece(it)); else addPiece();
    paymentRows = []; clear(paymentsWrap);
    if (o.payments && o.payments.length) o.payments.forEach((p) => addPayment(p)); else addPayment();
    setMode();
    recomputeAll();
    window.scrollTo(0, 0);
  }

  async function mount(viewEl) {
    [purities, categories, weights, supplies, sources] = await Promise.all([
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
    f.title = el("h1", {}, "New Order");
    f.saveBtn = el("button", { class: "btn btn-primary", onclick: () => save(false) }, "Save Order");

    piecesWrap = el("div", {});
    paymentsWrap = el("div", {});
    totalEl = el("div", { class: "total-display num" }, "₹ 0");
    receivedEl = el("div", { class: "total-display num" }, "₹ 0");
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
        el("div", { class: "muted", style: "font-size:12px;margin-bottom:6px;" },
          "Add a line per mode (e.g. part cash, part UPI). Cash lines post to Cash-in-Hand."),
        paymentsWrap,
        el("button", { class: "add-row-btn", onclick: () => addPayment() }, "+ Add payment line"),
        el("div", { class: "totals-box", style: "margin-top:14px;" }, [
          field("Order total", totalEl),
          field("Received", receivedEl),
          field("Balance due", balanceEl),
        ]),
        el("div", { class: "form-actions" }, [
          el("button", { class: "btn", onclick: reset }, "Cancel"),
          el("button", { class: "btn", onclick: () => save(true) }, "Save as Draft"),
          f.saveBtn,
        ]),
      ])),
    ]));
    addPiece();
    addPayment();
    recomputeAll();
    setMode();
  }

  window.KhataViews = window.KhataViews || {};
  window.KhataViews.entry = { mount, edit };
})();
