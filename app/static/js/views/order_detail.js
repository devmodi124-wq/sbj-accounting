// Order detail overlay: order-level info + payments, and each item (piece) with
// its weights/rates breakdown and pictures. Opened from Sales and Stock reports.
(function () {
  "use strict";
  const { el, clear, toast } = window.ui;

  function money(n) { return "₹ " + (Number(n) || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 }); }
  function num(n) { return Number(n) || 0; }
  function nameOf(list, id) { const x = list.find((i) => i.id === id); return x ? x.name : "—"; }
  function wt(g) { return g == null ? "—" : num(g).toFixed(3) + " g"; }
  function ct(c) { return c == null || num(c) === 0 ? "—" : num(c).toFixed(3) + " ct"; }
  function infoRow(label, value) {
    return el("tr", {}, [el("td", { class: "muted", style: "width:160px;" }, label), el("td", {}, value)]);
  }
  function valRow(label, value) {
    return el("tr", {}, [el("td", { class: "muted" }, label), el("td", { class: "amount num" }, value)]);
  }

  function overlay(children) {
    const box = el("div", { class: "card", style: "width:860px;max-width:95vw;max-height:90vh;overflow:auto;" }, children);
    const back = el("div", {
      style: "position:fixed;inset:0;background:rgba(28,27,25,.45);display:flex;align-items:center;justify-content:center;z-index:900;",
      onclick: (e) => { if (e.target === back) back.remove(); },
    }, box);
    document.body.appendChild(back);
    return back;
  }

  function pieceBlock(orderId, piece, cats, wts, sss, purs) {
    const net = num(piece.net_weight);
    const vals = [
      ["Metal", net * num(piece.metal_rate)],
      ["Diamond", num(piece.diamond_weight) * num(piece.diamond_rate)],
      ["Stone", num(piece.stone_weight) * num(piece.stone_rate)],
      ["Others", num(piece.others_weight) * num(piece.others_rate)],
      ["Labour", net * num(piece.labour_rate)],
    ].filter(([, v]) => v);

    const gallery = el("div", { style: "display:flex;gap:10px;flex-wrap:wrap;margin-top:8px;" });
    const fileInput = el("input", { type: "file", accept: "image/*", multiple: true, onchange: addImages });
    const base = `/api/orders/${orderId}/items/${piece.id}/images`;
    async function loadImages() {
      const imgs = await api.get(base);
      clear(gallery);
      if (!imgs.length) gallery.appendChild(el("span", { class: "muted" }, "No pictures."));
      for (const img of imgs) {
        const src = `${base}/${img.id}`;
        gallery.appendChild(el("div", { style: "position:relative;" }, [
          el("a", { href: src, target: "_blank", title: "Open full size" },
            el("img", { src, style: "width:96px;height:96px;object-fit:cover;border-radius:6px;border:1px solid var(--hairline);" })),
          el("button", { class: "remove-row-btn", title: "Delete picture",
            style: "position:absolute;top:-8px;right:-8px;background:#fff;border-radius:50%;",
            onclick: async () => {
              try { await api.del(`${base}/${img.id}`); loadImages(); }
              catch (e) { toast("Delete failed.", "error"); }
            } }, "×"),
        ]));
      }
    }
    async function addImages(e) {
      const files = e.target.files;
      if (!files.length) return;
      const fd = new FormData();
      for (const file of files) fd.append("files", file);
      try {
        const res = await fetch(base, { method: "POST", body: fd, credentials: "same-origin" });
        if (!res.ok) throw new Error();
        toast("Pictures added."); e.target.value = ""; loadImages();
      } catch (_) { toast("Upload failed.", "error"); }
    }

    const block = el("div", { class: "card", style: "margin-top:12px;background:var(--paper-alt);" },
      el("div", { class: "card-body" }, [
        el("table", {}, el("tbody", {}, [
          infoRow("Category", piece.item_category_id ? nameOf(cats, piece.item_category_id) : "—"),
          infoRow("Item name", piece.item_name || "—"),
          infoRow("Purity", piece.purity_type_id ? nameOf(purs, piece.purity_type_id) : "—"),
          infoRow("Weight type", piece.weight_type_id ? nameOf(wts, piece.weight_type_id) : "—"),
          infoRow("Supplied from", piece.supply_source_id ? nameOf(sss, piece.supply_source_id) : "—"),
          infoRow("Gross / Net wt", `${wt(piece.gross_weight)}  /  ${wt(piece.net_weight)}`),
          infoRow("Diamond / Stone / Others", `${ct(piece.diamond_weight)} · ${ct(piece.stone_weight)} · ${ct(piece.others_weight)}`),
        ])),
        el("div", { class: "form-section-title" }, "Value breakdown"),
        el("table", {}, el("tbody", {}, vals.length
          ? vals.map(([label, v]) => valRow(label, money(v))).concat([
              el("tr", {}, [el("td", { style: "font-weight:600;" }, "Subtotal"),
                el("td", { class: "amount num", style: "font-weight:600;" }, money(piece.subtotal))]),
            ])
          : [el("tr", {}, el("td", { class: "muted", colspan: "2" }, `Subtotal ${money(piece.subtotal)}`))])),
        el("div", { class: "form-section-title" }, "Pictures"),
        gallery,
        el("div", { style: "margin-top:10px;" }, fileInput),
      ]));
    loadImages();
    return block;
  }

  async function open(orderId) {
    const [o, cats, wts, sss, srcs, purs] = await Promise.all([
      api.get(`/api/orders/${orderId}`),
      api.get("/api/item-categories"), api.get("/api/weight-types"),
      api.get("/api/supply-sources"), api.get("/api/order-sources"), api.get("/api/purity-types"),
    ]);
    const cust = await api.get(`/api/customers/${o.customer_id}`).catch(() => ({ name: "" }));

    let back;
    const editBtn = el("button", { class: "btn btn-sm", onclick: () => {
      if (back) back.remove();
      window.KhataApp.editOrder(o.id);
    } }, "Edit");

    const paymentsText = (o.payments && o.payments.length)
      ? o.payments.map((p) => `${p.mode.replace(/_/g, " ")} ${money(p.amount)}`).join("  ·  ")
      : "—";

    const itemsWrap = el("div", {}, [el("div", { class: "form-section-title" }, `Items (${o.items.length})`)]);
    o.items.forEach((piece) => itemsWrap.appendChild(pieceBlock(o.id, piece, cats, wts, sss, purs)));

    back = overlay([
      el("div", { class: "card-header" }, [
        el("h2", {}, `Order #${o.id} — ${cust.name || ""}`),
        el("div", { style: "display:flex;gap:8px;align-items:center;" }, [
          el("span", { class: "pill " + (o.status === "delivered" ? "pill-green" : "pill-copper") }, o.status),
          editBtn,
        ]),
      ]),
      el("div", { class: "card-body" }, [
        el("table", {}, el("tbody", {}, [
          infoRow("Date", o.order_date),
          infoRow("Source", o.source_id ? nameOf(srcs, o.source_id) : "—"),
          infoRow("Reference", o.reference || "—"),
          infoRow("Order code", o.order_code || "—"),
          infoRow("Notes", o.notes || "—"),
          infoRow("Total", money(o.total_amount)),
          infoRow("Payments", paymentsText),
          infoRow("Received", money(o.payment_received)),
          infoRow("Balance", money(o.balance)),
        ])),
        itemsWrap,
      ]),
    ]);
  }

  window.KhataOrderDetail = { open };
})();
