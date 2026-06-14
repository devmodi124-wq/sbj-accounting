// Dashboard: stat cards, sales-trend chart (vendored Chart.js), pending/top/breakdown.
(function () {
  "use strict";
  const { el, clear } = window.ui;

  let chart = null;

  function money(n) {
    return "₹ " + (Number(n) || 0).toLocaleString("en-IN", { maximumFractionDigits: 0 });
  }
  function statCard(label, value, sub, cls) {
    return el("div", { class: "stat-card" }, [
      el("div", { class: "stat-label" }, label),
      el("div", { class: "stat-value num " + (cls || "") }, value),
      el("div", { class: "stat-sub" }, sub || ""),
    ]);
  }
  function monthLabel(ym) {
    const [y, m] = ym.split("-");
    return ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"][+m] + " " + y.slice(2);
  }

  function renderChart(canvas, trend) {
    if (chart) { chart.destroy(); chart = null; }
    if (!window.Chart) return;
    chart = new window.Chart(canvas, {
      type: "bar",
      data: {
        labels: trend.map((t) => monthLabel(t.month)),
        datasets: [{
          data: trend.map((t) => Number(t.total)),
          backgroundColor: "#E9DCCC", hoverBackgroundColor: "#A8714A",
          borderRadius: 3,
        }],
      },
      options: {
        plugins: { legend: { display: false } },
        scales: { y: { beginAtZero: true, ticks: { callback: (v) => "₹" + (v / 1000) + "k" } } },
        responsive: true, maintainAspectRatio: false,
      },
    });
  }

  function table(headers, rows) {
    return el("table", {}, [
      el("thead", {}, el("tr", {}, headers.map((h) => el("th", {}, h)))),
      el("tbody", {}, rows.length ? rows : [el("tr", {}, el("td", { class: "muted", colspan: String(headers.length) }, "No data."))]),
    ]);
  }

  async function load(viewEl, preset) {
    const d = await api.get("/api/dashboard" + (preset ? `?range=${preset}` : ""));
    clear(viewEl);

    const rangeSel = el("select", { onchange: (e) => load(viewEl, e.target.value) },
      [["today", "Today"], ["this_month", "This Month"], ["this_quarter", "This Quarter"], ["this_year", "This Year"]]
        .map(([v, t]) => el("option", { value: v, selected: (preset || "this_month") === v }, t)));

    const canvas = el("canvas", { height: "220" });

    viewEl.appendChild(el("div", {}, [
      el("div", { class: "topbar" }, [
        el("div", {}, [el("h1", {}, "Dashboard"), el("div", { class: "meta" }, "Business at a glance")]),
        el("div", { class: "filter-bar", style: "margin-bottom:0;" }, rangeSel),
      ]),
      el("div", { class: "stat-grid" }, [
        statCard("Sales (period)", money(d.sales), ""),
        statCard("Outstanding receivables", money(d.receivables.total), `across ${d.receivables.customers} customers`, "negative"),
        statCard("Outstanding payables", money(d.payables.total), `across ${d.payables.parties} suppliers`),
        statCard("Cash in hand", money(d.cash_in_hand), "as of today", "positive"),
      ]),
      el("div", { class: "grid-2" }, [
        el("div", { class: "card" }, [
          el("div", { class: "card-header" }, [el("h2", {}, "Sales trend"), el("span", { class: "pill pill-muted" }, "Last 12 months")]),
          el("div", { class: "card-body", style: "height:260px;" }, canvas),
        ]),
        el("div", { class: "card" }, [
          el("div", { class: "card-header" }, el("h2", {}, "Pending orders")),
          el("div", { class: "card-body", style: "padding:0;" }, table(["Customer", "Item", "Date"],
            d.pending_orders.map((o) => el("tr", {}, [el("td", {}, o.customer_name), el("td", {}, o.item_name), el("td", {}, o.order_date)])))),
        ]),
      ]),
      el("div", { class: "grid-2", style: "margin-top:18px;" }, [
        el("div", { class: "card" }, [
          el("div", { class: "card-header" }, el("h2", {}, "Top customers")),
          el("div", { class: "card-body", style: "padding:0;" }, table(["Customer", "Billed", "Balance"],
            d.top_customers.map((c) => el("tr", {}, [
              el("td", {}, c.name),
              el("td", { class: "amount num" }, money(c.billed)),
              el("td", { class: "amount num " + (Number(c.balance) > 0 ? "negative" : "") }, money(c.balance)),
            ])))),
        ]),
        el("div", { class: "card" }, [
          el("div", { class: "card-header" }, el("h2", {}, "Sales by component")),
          el("div", { class: "card-body", style: "padding:0;" }, table(["Component", "Total"],
            d.sales_by_component.map((c) => el("tr", {}, [el("td", {}, c.name), el("td", { class: "amount num" }, money(c.total))])))),
        ]),
      ]),
    ]));
    renderChart(canvas, d.sales_trend);
  }

  window.KhataViews = window.KhataViews || {};
  window.KhataViews.dashboard = {
    mount(viewEl) { load(viewEl, "this_month"); },
  };
})();
