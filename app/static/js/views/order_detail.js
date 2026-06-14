// Order detail overlay: shows fields, components, and pictures (view/add/remove).
// Opened from the Sales and Order/Stock reports.
(function () {
  "use strict";
  const { el, clear, toast } = window.ui;

  function money(n) { return "₹ " + (Number(n) || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 }); }
  function nameOf(list, id) { const x = list.find((i) => i.id === id); return x ? x.name : "—"; }
  function infoRow(label, value) {
    return el("tr", {}, [el("td", { class: "muted", style: "width:160px;" }, label), el("td", {}, value)]);
  }

  function overlay(children) {
    const box = el("div", { class: "card", style: "width:820px;max-width:95vw;max-height:90vh;overflow:auto;" }, children);
    const back = el("div", {
      style: "position:fixed;inset:0;background:rgba(28,27,25,.45);display:flex;align-items:center;justify-content:center;z-index:900;",
      onclick: (e) => { if (e.target === back) back.remove(); },
    }, box);
    document.body.appendChild(back);
    return back;
  }

  async function open(orderId) {
    const [o, comps, purs, cats, wts, sss] = await Promise.all([
      api.get(`/api/orders/${orderId}`),
      api.get("/api/component-types"), api.get("/api/purity-types"),
      api.get("/api/item-categories"), api.get("/api/weight-types"), api.get("/api/supply-sources"),
    ]);
    const cust = await api.get(`/api/customers/${o.customer_id}`).catch(() => ({ name: "" }));

    const itemsTable = el("table", {}, [
      el("thead", {}, el("tr", {}, ["Component", "Pcs", "Weight", "Purity", "Rate", "Price"].map((h) => el("th", {}, h)))),
      el("tbody", {}, o.items.length ? o.items.map((it) => el("tr", {}, [
        el("td", {}, nameOf(comps, it.component_type_id)),
        el("td", {}, it.pcs ?? "—"),
        el("td", {}, it.weight ?? "—"),
        el("td", {}, it.purity_type_id ? nameOf(purs, it.purity_type_id) : "—"),
        el("td", { class: "amount num" }, it.rate != null ? money(it.rate) : "—"),
        el("td", { class: "amount num" }, money(it.price)),
      ])) : [el("tr", {}, el("td", { class: "muted", colspan: "6" }, "No components."))]),
    ]);

    const gallery = el("div", { style: "display:flex;gap:10px;flex-wrap:wrap;margin-top:8px;" });
    const fileInput = el("input", { type: "file", accept: "image/*", multiple: true, onchange: addImages });

    async function loadImages() {
      const imgs = await api.get(`/api/orders/${orderId}/images`);
      clear(gallery);
      if (!imgs.length) gallery.appendChild(el("span", { class: "muted" }, "No pictures."));
      for (const img of imgs) {
        const src = `/api/orders/${orderId}/images/${img.id}`;
        gallery.appendChild(el("div", { style: "position:relative;" }, [
          el("a", { href: src, target: "_blank", title: "Open full size" },
            el("img", { src, style: "width:96px;height:96px;object-fit:cover;border-radius:6px;border:1px solid var(--hairline);" })),
          el("button", { class: "remove-row-btn", title: "Delete picture",
            style: "position:absolute;top:-8px;right:-8px;background:#fff;border-radius:50%;",
            onclick: async () => {
              try { await api.del(`/api/orders/${orderId}/images/${img.id}`); loadImages(); }
              catch (e) { toast("Delete failed.", "error"); }
            } }, "×"),
        ]));
      }
    }
    async function addImages(e) {
      const files = e.target.files;
      if (!files.length) return;
      const fd = new FormData();
      for (const f of files) fd.append("files", f);
      try {
        const res = await fetch(`/api/orders/${orderId}/images`, { method: "POST", body: fd, credentials: "same-origin" });
        if (!res.ok) throw new Error();
        toast("Pictures added."); e.target.value = ""; loadImages();
      } catch (_) { toast("Upload failed.", "error"); }
    }

    overlay([
      el("div", { class: "card-header" }, [
        el("h2", {}, `Order #${o.id} — ${cust.name || ""}`),
        el("span", { class: "pill " + (o.status === "delivered" ? "pill-green" : "pill-copper") }, o.status),
      ]),
      el("div", { class: "card-body" }, [
        el("table", {}, el("tbody", {}, [
          infoRow("Date", o.order_date),
          infoRow("Category", nameOf(cats, o.item_category_id)),
          infoRow("Item name", o.item_name || "—"),
          infoRow("Weight type", o.weight_type_id ? nameOf(wts, o.weight_type_id) : "—"),
          infoRow("Supplied from", o.supply_source_id ? nameOf(sss, o.supply_source_id) : "—"),
          infoRow("Order code", o.order_code || "—"),
          infoRow("Notes", o.notes || "—"),
          infoRow("Total", money(o.total_amount)),
          infoRow("Received", money(o.payment_received)),
          infoRow("Balance", money(o.balance)),
        ])),
        el("div", { class: "form-section-title" }, "Components"),
        itemsTable,
        el("div", { class: "form-section-title" }, "Pictures"),
        gallery,
        el("div", { style: "margin-top:10px;" }, fileInput),
      ]),
    ]);
    loadImages();
  }

  window.KhataOrderDetail = { open };
})();
