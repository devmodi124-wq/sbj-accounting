// Tiny JSON fetch wrapper shared by all screens.
(function () {
  "use strict";

  async function request(method, url, body) {
    const opts = { method, headers: {}, credentials: "same-origin" };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(url, opts);
    let data = null;
    if ((res.headers.get("content-type") || "").includes("application/json")) {
      data = await res.json();
    }
    if (!res.ok) {
      const err = new Error((data && data.detail) || res.statusText);
      err.status = res.status;
      err.detail = data && data.detail;
      throw err;
    }
    return data;
  }

  window.api = {
    request,
    get: (u) => request("GET", u),
    post: (u, b) => request("POST", u, b),
    put: (u, b) => request("PUT", u, b),
    del: (u) => request("DELETE", u),
  };
})();
