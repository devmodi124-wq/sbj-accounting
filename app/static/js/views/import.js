// Admin Import screen: download template, upload, validate (preview), commit.
(function () {
  "use strict";
  const { el, clear, toast } = window.ui;

  async function uploadFile(url, file) {
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(url, { method: "POST", body: fd, credentials: "same-origin" });
    let data = null;
    if ((res.headers.get("content-type") || "").includes("application/json")) data = await res.json();
    if (!res.ok) { const e = new Error((data && data.detail) || res.statusText); e.status = res.status; throw e; }
    return data;
  }

  function mount(viewEl) {
    const fileInput = el("input", { type: "file", accept: ".xlsx,.zip" });
    const report = el("div", {});
    const commitBtn = el("button", { class: "btn btn-primary", disabled: true, onclick: commit }, "Import data");
    let lastValid = false;

    function downloadTemplate() {
      const a = el("a", { href: "/api/import/template", download: "" });
      document.body.appendChild(a); a.click(); a.remove();
    }

    function renderReport(r) {
      clear(report);
      const summary = Object.entries(r.summary || {})
        .filter(([, n]) => n > 0).map(([k, n]) => `${k}: ${n}`).join(" · ");
      if (r.ok) {
        report.appendChild(el("div", { class: "banner-info" }, "Looks good — " + (summary || "no rows") + ". Ready to import."));
      } else {
        report.appendChild(el("div", { class: "banner-error" }, `${r.errors.length} problem(s) found — fix and re-validate.`));
        report.appendChild(el("div", { class: "table-scroll" }, el("table", {}, [
          el("thead", {}, el("tr", {}, ["Sheet", "Row", "Problem"].map((h) => el("th", {}, h)))),
          el("tbody", {}, r.errors.map((e) => el("tr", {}, [
            el("td", {}, e.sheet), el("td", {}, String(e.row)), el("td", {}, e.message)]))),
        ])));
      }
    }

    async function validate() {
      if (!fileInput.files[0]) return toast("Choose a file first.", "error");
      try {
        const r = await uploadFile("/api/import/validate", fileInput.files[0]);
        lastValid = r.ok; commitBtn.disabled = !r.ok; renderReport(r);
      } catch (e) { toast(e.message || "Validation failed.", "error"); }
    }

    async function commit() {
      if (!lastValid || !fileInput.files[0]) return;
      try {
        const r = await uploadFile("/api/import/commit", fileInput.files[0]);
        const imp = r.imported;
        clear(report).appendChild(el("div", { class: "banner-info" },
          "Imported — " + Object.entries(imp).filter(([, n]) => n > 0).map(([k, n]) => `${n} ${k}`).join(", ") + "."));
        commitBtn.disabled = true; lastValid = false; fileInput.value = "";
        toast("Import complete.");
      } catch (e) {
        toast(e.status === 422 ? "Validation failed — re-validate." : (e.message || "Import failed."), "error");
      }
    }

    clear(viewEl).appendChild(el("div", {}, [
      el("div", { class: "topbar" }, el("div", {}, [
        el("h1", {}, "Import"), el("div", { class: "meta" }, "Bulk-import historical data from Excel")])),
      el("div", { class: "card" }, el("div", { class: "card-body" }, [
        el("p", { class: "muted" }, "1. Download the template and fill it in. 2. Upload and validate. 3. Import."),
        el("p", { class: "muted" }, "To include pictures: list filenames in the 'images' column (separate with ;), put the photos in an 'images' folder, ZIP it with the workbook, and upload the .zip."),
        el("div", { class: "form-actions", style: "justify-content:flex-start;border:none;padding:0;margin:0 0 16px;" },
          el("button", { class: "btn", onclick: downloadTemplate }, "⤓ Download template")),
        el("div", { class: "filter-bar" }, [fileInput,
          el("button", { class: "btn", onclick: validate }, "Validate"), commitBtn]),
        report,
      ])),
    ]));
  }

  window.KhataViews = window.KhataViews || {};
  window.KhataViews.import = { mount };
})();
