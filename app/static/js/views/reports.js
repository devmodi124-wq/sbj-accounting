// Generic report screen: filter bar, sortable headers, pagination, CSV export.
(function () {
  "use strict";
  const { el, clear } = window.ui;
  const PAGE = 25;

  function money(v) { return "₹ " + (Number(v) || 0).toLocaleString("en-IN", { maximumFractionDigits: 2 }); }

  function makeReport(cfg) {
    let state = { sort: cfg.defaultSort, direction: "desc", offset: 0,
      search: "", date_from: "", date_to: "", status: "", ageing: "" };
    let root, tbody, pageInfo, footer;
    const filterOptions = {};  // selectFilter param -> [{id,name}]
    const hasAction = !!(cfg.ledger || cfg.orderDetail);

    function params(extra) {
      const p = new URLSearchParams();
      p.set("limit", PAGE); p.set("offset", state.offset);
      if (state.sort) { p.set("sort", state.sort); p.set("direction", state.direction); }
      if (cfg.hasSearch && state.search) p.set("search", state.search);
      if (cfg.hasDateRange && state.date_from) p.set("date_from", state.date_from);
      if (cfg.hasDateRange && state.date_to) p.set("date_to", state.date_to);
      if (cfg.statusOptions && state.status) p.set("status", state.status);
      if (cfg.hasAgeing && state.ageing) p.set("ageing", state.ageing);
      (cfg.selectFilters || []).forEach((sf) => { if (state[sf.param]) p.set(sf.param, state[sf.param]); });
      for (const [k, v] of Object.entries(extra || {})) p.set(k, v);
      return p;
    }

    async function load() {
      const data = await api.get(cfg.endpoint + "?" + params().toString());
      clear(tbody);
      if (!data.rows.length) {
        tbody.appendChild(el("tr", {}, el("td", { class: "muted", colspan: String(cfg.columns.length + (hasAction ? 1 : 0)) }, "No records.")));
      }
      for (const row of data.rows) {
        const cells = cfg.columns.map((c) => {
          let val = row[c.key];
          if (c.money) {
            const neg = c.negIfPositive && Number(row[c.key]) > 0;
            return el("td", { class: "amount num" + (neg ? " negative" : "") }, money(val));
          }
          if (c.pill) {
            const cls = c.pill(row[c.key]);
            return el("td", {}, el("span", { class: "pill " + cls }, String(val)));
          }
          return el("td", {}, String(val === null || val === undefined || val === "" ? "—" : val));
        });
        if (cfg.ledger) {
          cells.push(el("td", {}, el("button", { class: "btn btn-sm",
            onclick: () => window.KhataLedger.open(cfg.ledger, row[cfg.ledgerIdKey]) }, "Ledger")));
        } else if (cfg.orderDetail) {
          cells.push(el("td", {}, el("button", { class: "btn btn-sm",
            onclick: () => window.KhataOrderDetail.open(row.id) }, "View")));
        }
        tbody.appendChild(el("tr", {}, cells));
      }
      pageInfo.textContent = `Showing ${data.rows.length ? state.offset + 1 : 0}–${state.offset + data.rows.length} of ${data.total}`;
      if (footer && data.total_outstanding !== undefined) {
        footer.textContent = "Total outstanding: ₹ " + Number(data.total_outstanding).toLocaleString("en-IN");
      }
    }

    function setSort(key) {
      if (state.sort === key) state.direction = state.direction === "asc" ? "desc" : "asc";
      else { state.sort = key; state.direction = "desc"; }
      state.offset = 0; load();
    }

    function exportAs(fmt) {
      const p = params({ format: fmt });
      const a = el("a", { href: cfg.endpoint + "?" + p.toString(), download: "" });
      document.body.appendChild(a); a.click(); a.remove();
    }

    function filterBar() {
      const controls = [];
      if (cfg.hasSearch) {
        controls.push(el("input", { type: "search", placeholder: "Search…",
          oninput: (e) => { state.search = e.target.value.trim(); state.offset = 0; load(); } }));
      }
      if (cfg.hasDateRange) {
        controls.push(el("input", { type: "date", title: "From",
          onchange: (e) => { state.date_from = e.target.value; state.offset = 0; load(); } }));
        controls.push(el("input", { type: "date", title: "To",
          onchange: (e) => { state.date_to = e.target.value; state.offset = 0; load(); } }));
      }
      if (cfg.statusOptions) {
        controls.push(el("select", { onchange: (e) => { state.status = e.target.value; state.offset = 0; load(); } },
          [el("option", { value: "" }, "All statuses")].concat(
            cfg.statusOptions.map((s) => el("option", { value: s.value }, s.label)))));
      }
      if (cfg.hasAgeing) {
        controls.push(el("select", { onchange: (e) => { state.ageing = e.target.value; state.offset = 0; load(); } },
          ["", "0-30", "31-60", "61-90", "90+"].map((a) =>
            el("option", { value: a }, a ? a + " days" : "All ageing"))));
      }
      (cfg.selectFilters || []).forEach((sf) => {
        const opts = [el("option", { value: "" }, sf.allLabel || "All")].concat(
          (filterOptions[sf.param] || []).map((o) => el("option", { value: o.id }, o.name)));
        controls.push(el("select", { onchange: (e) => { state[sf.param] = e.target.value; state.offset = 0; load(); } }, opts));
      });
      controls.push(el("div", { class: "filter-spacer" }));
      if (footer) controls.push(footer);
      controls.push(el("button", { class: "btn", onclick: () => exportAs("csv"), title: "Download CSV" }, "⤓ CSV"));
      controls.push(el("button", { class: "btn", onclick: () => exportAs("xlsx"), title: "Download Excel" }, "⤓ Excel"));
      return el("div", { class: "filter-bar" }, controls);
    }

    function header() {
      return el("thead", {}, el("tr", {}, cfg.columns.map((c) =>
        el("th", c.sortable ? { class: "sortable", onclick: () => setSort(c.key),
          style: c.money ? "text-align:right;" : null } : (c.money ? { style: "text-align:right;" } : {}),
          c.label + (c.sortable && state.sort === c.key ? (state.direction === "asc" ? " ▲" : " ▾") : "")))
        .concat(hasAction ? [el("th", {}, "")] : [])));
    }

    function pager() {
      pageInfo = el("span", {});
      const prev = el("button", { class: "page-btn", onclick: () => { if (state.offset >= PAGE) { state.offset -= PAGE; load(); } } }, "‹");
      const next = el("button", { class: "page-btn", onclick: () => { state.offset += PAGE; load(); } }, "›");
      return el("div", { class: "pagination" }, [pageInfo, el("div", { class: "pages" }, [prev, next])]);
    }

    return {
      async mount(viewEl) {
        if (cfg.footer) footer = el("span", { class: "pill pill-red" });
        for (const sf of (cfg.selectFilters || [])) {
          try { filterOptions[sf.param] = await api.get(sf.endpoint + "?active_only=true&limit=1000"); }
          catch (_) { filterOptions[sf.param] = []; }
        }
        tbody = el("tbody");
        root = el("div", {}, [
          el("div", { class: "topbar" }, el("div", {}, [
            el("h1", {}, cfg.title), el("div", { class: "meta" }, cfg.subtitle)])),
          el("div", { class: "card" }, el("div", { class: "card-body" }, [
            filterBar(),
            el("div", { class: "table-scroll" }, el("table", {}, [header(), tbody])),
            pager(),
          ])),
        ]);
        clear(viewEl).appendChild(root);
        load();
      },
    };
  }

  const statusPill = (s) => (s === "delivered" || s === "paid") ? "pill-green" : "pill-copper";
  const ageingPill = (a) => a === "90+" ? "pill-red" : (a === "0-30" ? "pill-green" : (a === "—" ? "pill-muted" : "pill-copper"));

  window.KhataViews = window.KhataViews || {};
  window.KhataViews.sales = makeReport({
    endpoint: "/api/reports/sales", title: "Sales Report", subtitle: "One row per order",
    hasSearch: false, hasDateRange: true, defaultSort: "order_date", orderDetail: true,
    statusOptions: [{ value: "delivered", label: "Delivered" }, { value: "pending", label: "Pending" }],
    selectFilters: [
      { param: "category_id", endpoint: "/api/item-categories", allLabel: "All categories" },
      { param: "source_id", endpoint: "/api/order-sources", allLabel: "All sources" },
    ],
    columns: [
      { key: "order_date", label: "Date", sortable: true }, { key: "customer_name", label: "Customer", sortable: true },
      { key: "item_category", label: "Category" }, { key: "item_name", label: "Item" },
      { key: "item_count", label: "Items", sortable: true }, { key: "source", label: "Source" },
      { key: "total_amount", label: "Total", money: true, sortable: true },
      { key: "payment_received", label: "Received", money: true }, { key: "balance", label: "Balance", money: true, negIfPositive: true },
      { key: "status", label: "Status", pill: statusPill },
    ],
  });
  window.KhataViews.stock = makeReport({
    endpoint: "/api/reports/stock", title: "Order / Stock Report", subtitle: "Work in progress",
    hasDateRange: true, defaultSort: "order_date", orderDetail: true,
    statusOptions: [{ value: "pending", label: "Pending" }, { value: "delivered", label: "Delivered" }],
    selectFilters: [{ param: "category_id", endpoint: "/api/item-categories", allLabel: "All categories" }],
    columns: [
      { key: "order_date", label: "Date", sortable: true }, { key: "customer_name", label: "Customer" },
      { key: "item_category", label: "Category" }, { key: "item_name", label: "Item" },
      { key: "item_count", label: "Items" }, { key: "source", label: "Source" },
      { key: "status", label: "Status", pill: statusPill }, { key: "days_pending", label: "Days pending", sortable: true },
    ],
  });
  window.KhataViews.debtors = makeReport({
    endpoint: "/api/reports/debtors", title: "Debtors Report", subtitle: "Customers with an outstanding balance",
    hasSearch: true, hasAgeing: true, footer: true, defaultSort: "balance", ledger: "customer", ledgerIdKey: "customer_id",
    columns: [
      { key: "name", label: "Customer", sortable: true }, { key: "phone", label: "Phone" },
      { key: "billed", label: "Total billed", money: true }, { key: "received", label: "Received", money: true },
      { key: "balance", label: "Balance", money: true, negIfPositive: true, sortable: true },
      { key: "last_txn", label: "Last txn", sortable: true }, { key: "ageing", label: "Ageing", pill: ageingPill },
    ],
  });
  window.KhataViews.creditors = makeReport({
    endpoint: "/api/reports/creditors", title: "Creditors Report", subtitle: "Suppliers we owe",
    hasSearch: true, hasAgeing: true, footer: true, defaultSort: "balance", ledger: "party", ledgerIdKey: "party_id",
    columns: [
      { key: "name", label: "Supplier", sortable: true }, { key: "phone", label: "Phone" },
      { key: "purchased", label: "Total purchased", money: true }, { key: "paid", label: "Paid", money: true },
      { key: "balance", label: "Balance", money: true, negIfPositive: true, sortable: true },
      { key: "last_txn", label: "Last txn", sortable: true }, { key: "ageing", label: "Ageing", pill: ageingPill },
    ],
  });
  window.KhataViews.purchases = makeReport({
    endpoint: "/api/reports/purchases", title: "Purchases Report", subtitle: "Supplier purchases",
    hasDateRange: true, defaultSort: "purchase_date", ledger: "party", ledgerIdKey: "party_id",
    statusOptions: [{ value: "pending", label: "Pending" }, { value: "paid", label: "Paid" }],
    selectFilters: [{ param: "party_id", endpoint: "/api/parties", allLabel: "All suppliers" }],
    columns: [
      { key: "purchase_date", label: "Date", sortable: true }, { key: "party_name", label: "Supplier", sortable: true },
      { key: "details", label: "Details" },
      { key: "amount", label: "Amount", money: true, sortable: true }, { key: "amount_paid", label: "Paid", money: true },
      { key: "balance", label: "Balance", money: true, negIfPositive: true, sortable: true },
      { key: "status", label: "Status", pill: statusPill },
    ],
  });
  window.KhataViews.customers = makeReport({
    endpoint: "/api/reports/customers", title: "Customer Report", subtitle: "Per-customer lifetime view",
    hasSearch: true, defaultSort: "lifetime", ledger: "customer", ledgerIdKey: "customer_id",
    columns: [
      { key: "name", label: "Customer", sortable: true }, { key: "phone", label: "Phone" },
      { key: "lifetime", label: "Lifetime", money: true, sortable: true }, { key: "order_count", label: "Orders", sortable: true },
      { key: "avg_order_value", label: "Avg order", money: true }, { key: "balance", label: "Balance", money: true, negIfPositive: true },
      { key: "last_visit", label: "Last visit", sortable: true },
    ],
  });
  window.KhataViews.ledgers = {
    mount(viewEl) {
      clear(viewEl).appendChild(el("div", {}, [
        el("div", { class: "topbar" }, el("div", {}, [el("h1", {}, "Ledgers"),
          el("div", { class: "meta" }, "Open a ledger from the Debtors, Creditors or Customer reports.")])),
        el("div", { class: "card" }, el("div", { class: "card-body muted" },
          "Use the Ledger button on a row in Debtors, Creditors, or Customers.")),
      ]));
    },
  };
})();
