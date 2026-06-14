// Ledger overlay, opened from Debtors/Creditors/Customer reports.
(function () {
  "use strict";
  const { el, clear } = window.ui;

  function overlay(children) {
    const box = el("div", { class: "card", style: "width:760px;max-width:94vw;max-height:88vh;overflow:auto;" }, children);
    const back = el("div", {
      style: "position:fixed;inset:0;background:rgba(28,27,25,.45);display:flex;" +
        "align-items:center;justify-content:center;z-index:900;",
      onclick: (e) => { if (e.target === back) back.remove(); },
    }, box);
    document.body.appendChild(back);
    return back;
  }

  async function open(type, id) {
    const data = await api.get(`/api/ledgers/${type}/${id}`);
    const back = overlay([
      el("div", { class: "card-header" }, [
        el("h2", {}, `Ledger — ${data.entity.name}`),
        el("button", { class: "btn btn-sm", onclick: () => downloadCsv(type, id) }, "⤓ Export"),
      ]),
      el("div", { class: "card-body", style: "padding:0;" },
        el("table", {}, [
          el("thead", {}, el("tr", {}, ["Date", "Particulars", "Debit", "Credit", "Balance"]
            .map((h) => el("th", {}, h)))),
          el("tbody", {}, data.entries.map((e) => el("tr", {}, [
            el("td", {}, e.date),
            el("td", {}, e.particulars),
            el("td", { class: "amount num" }, e.debit),
            el("td", { class: "amount num" }, e.credit),
            el("td", { class: "amount num" }, e.balance),
          ]))),
        ])),
      el("div", { class: "card-header", style: "border-top:1px solid var(--hairline);border-bottom:none;" }, [
        el("span", { class: "muted" }, "Closing balance"),
        el("strong", { class: "num" }, "₹ " + data.closing_balance),
      ]),
    ]);
    return back;
  }

  function downloadCsv(type, id) {
    const a = el("a", { href: `/api/ledgers/${type}/${id}?format=csv`, download: "" });
    document.body.appendChild(a); a.click(); a.remove();
  }

  window.KhataLedger = { open };
})();
