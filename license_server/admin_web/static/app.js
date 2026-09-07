/* Furniture Bill License Admin - SPA */
(function () {
  "use strict";

  const $ = (s, c) => (c || document).querySelector(s);
  const $$ = (s, c) => [...(c || document).querySelectorAll(s)];

  // ---- Token ----
  let token = localStorage.getItem("fb_admin_token");
  function setToken(t) { token = t; if (t) localStorage.setItem("fb_admin_token", t); else localStorage.removeItem("fb_admin_token"); }

  // ---- Fetch helper ----
  async function api(method, path, body) {
    const opts = { method, headers: {} };
    if (token) opts.headers["Authorization"] = "Bearer " + token;
    if (body !== undefined) { opts.headers["Content-Type"] = "application/json"; opts.body = JSON.stringify(body); }
    const res = await fetch(path, opts);
    const json = await res.json().catch(() => ({}));
    if (!res.ok && res.status === 401) { setToken(null); showLogin(); throw new Error("Session expired."); }
    return json;
  }

  // ---- Toasts ----
  function toast(msg, kind) {
    const el = document.createElement("div");
    el.className = "toast " + (kind || "");
    el.textContent = msg;
    $("#toast-wrap").appendChild(el);
    setTimeout(() => el.remove(), 4500);
  }

  // ---- Views ----
  function showLogin() { $("#login-view").classList.remove("hidden"); $("#dashboard-view").classList.add("hidden"); }
  function showDash()  { $("#login-view").classList.add("hidden"); $("#dashboard-view").classList.remove("hidden"); refresh(); }

  // ---- Modal ----
  function showModal(html) { $("#modal-box").innerHTML = html; $("#modal-overlay").classList.remove("hidden"); }
  function hideModal() { $("#modal-overlay").classList.add("hidden"); $("#modal-box").innerHTML = ""; }

  // ---- Tabs ----
  function switchTab(name) {
    $$(".tab").forEach(t => t.classList.toggle("active", t.dataset.tab === name));
    $("#panel-licenses").classList.toggle("hidden", name !== "licenses");
    $("#panel-customers").classList.toggle("hidden", name !== "customers");
    refresh();
  }

  // ---- Data ----
  let licenses = [], customers = [], customerMap = {};

  async function refresh() {
    const active = $(".tab.active")?.dataset.tab || "licenses";
    if (active === "licenses") await loadLicenses();
    else await loadCustomers();
  }

  async function loadLicenses() {
    try {
      const q = ($("#license-search") || {}).value || "";
      const d = await api("GET", "/admin/licenses?search=" + encodeURIComponent(q));
      licenses = d.licenses || [];
      renderLicenses();
    } catch (e) { toast(e.message, "err"); }
  }

  async function loadCustomers() {
    try {
      const q = ($("#customer-search") || {}).value || "";
      const d = await api("GET", "/admin/customers?search=" + encodeURIComponent(q));
      customers = d.customers || [];
      customerMap = {};
      customers.forEach(c => customerMap[c.id] = c);
      renderCustomers();
    } catch (e) { toast(e.message, "err"); }
  }

  // ---- Render ----
  function esc(s) { if (!s) return ""; const d = document.createElement("div"); d.textContent = s; return d.innerHTML; }
  function badge(status) {
    const cls = ({"ACTIVE":"active","REVOKED":"revoked","BLOCKED":"blocked"}[status] || "revoked");
    return '<span class="badge ' + cls + '">' + esc(status) + '</span>';
  }
  function dateShort(v) { return v ? v.slice(0, 10) : "-"; }

  function renderLicenses() {
    const tbody = $("#license-rows");
    if (!licenses.length) { tbody.innerHTML = '<tr><td colspan="7" class="muted">No licenses found.</td></tr>'; return; }
    tbody.innerHTML = licenses.map(lic => {
      const cust = lic.customer_name || customerMap[lic.customer_id]?.name || "-";
      const prodLabel = (lic.product === "ac_service" ? "AC Service" : (lic.product === "future_product" ? "Future Product" : "Furniture Bill"));
      return '<tr data-id="' + lic.id + '">'
        + '<td class="key">' + esc(lic.license_key) + '</td>'
        + '<td><span class="muted">' + esc(prodLabel) + '</span></td>'
        + '<td>' + esc(cust) + '</td>'
        + '<td>' + badge(lic.status) + '</td>'
        + '<td class="muted">' + (lic.device_label || (lic.current_device ? esc(lic.current_device.slice(0,16))+"&hellip;" : "None")) + '</td>'
        + '<td class="muted">' + dateShort(lic.activated_at) + '</td>'
        + '<td><div class="row-actions">'
        + '<button class="btn link" data-act="reset" data-id="' + lic.id + '"' + (!lic.current_device ? ' disabled' : '') + ' title="Reset device binding">Reset Device</button>'
        + '<button class="btn link" data-act="events" data-id="' + lic.id + '" title="View audit history">Events</button>'
        + '<button class="btn link danger" data-act="revoke" data-id="' + lic.id + '"' + (lic.status === 'REVOKED' ? ' disabled' : '') + '>Revoke</button>'
        + '<button class="btn link danger" data-act="block" data-id="' + lic.id + '"' + (lic.status === 'BLOCKED' ? ' disabled' : '') + '>Block</button>'
        + '<button class="btn link" data-act="activate" data-id="' + lic.id + '"' + (lic.status === 'ACTIVE' ? ' disabled' : '') + '>Reactivate</button>'
        + '</div></td></tr>';
    }).join("");
  }

  function renderCustomers() {
    const tbody = $("#customer-rows");
    if (!customers.length) { tbody.innerHTML = '<tr><td colspan="5" class="muted">No customers found.</td></tr>'; return; }
    tbody.innerHTML = customers.map(c => {
      const licCount = licenses.filter(l => l.customer_id === c.id).length;
      return '<tr>'
        + '<td>' + esc(c.name) + '</td>'
        + '<td class="muted">' + esc(c.mobile || "-") + '</td>'
        + '<td class="muted">' + esc(c.email || "-") + '</td>'
        + '<td>' + licCount + '</td>'
        + '<td class="muted">' + dateShort(c.created_at) + '</td>'
        + '</tr>';
    }).join("");
  }

  // ---- License actions ----
  async function licAction(act, id) {
    if (act === "events") {
      await showEventsModal(id);
      return;
    }
    const confirmMsg = {
      reset: "Reset the device binding for this license? The customer will be able to activate on a new computer.",
      deactivate: "Deactivate this license device binding?",
      revoke: "Revoke this license permanently? Activation will be blocked.",
      block: "Block this license? Activation will be temporarily blocked.",
      activate: "Reactivate this license (set status to ACTIVE)?"
    };
    if (!confirm(confirmMsg[act] || "Continue?")) return;
    try {
      if (act === "reset" || act === "deactivate") {
        await api("POST", "/api/v1/admin/licenses/" + id + "/reset-device", { reason: "Admin reset from UI" });
        toast("Device binding reset successfully.", "ok");
      } else if (act === "activate") {
        await api("POST", "/api/v1/admin/licenses/" + id + "/reactivate", { reason: "Admin reactivated from UI" });
        toast("License status set to ACTIVE.", "ok");
      } else if (act === "revoke") {
        await api("POST", "/api/v1/admin/licenses/" + id + "/revoke", { reason: "Admin revoked from UI" });
        toast("License REVOKED.", "ok");
      } else if (act === "block") {
        await api("POST", "/api/v1/admin/licenses/" + id + "/block", { reason: "Admin blocked from UI" });
        toast("License BLOCKED.", "ok");
      }
      await loadLicenses();
    } catch (e) { toast(e.message, "err"); }
  }

  async function showEventsModal(licId) {
    try {
      const res = await api("GET", "/api/v1/admin/licenses/" + licId + "/events");
      const evs = res.events || [];
      let rows = '<tr><td colspan="5" class="muted">No events recorded.</td></tr>';
      if (evs.length) {
        rows = evs.map(e => (
          '<tr>'
          + '<td><b>' + esc(e.action) + '</b></td>'
          + '<td class="muted">' + esc((e.created_at || "").slice(0, 19).replace("T", " ")) + '</td>'
          + '<td>' + (e.success ? '<span class="badge active">Success</span>' : '<span class="badge blocked">Failed</span>') + '</td>'
          + '<td class="muted">' + esc(e.device_fingerprint ? e.device_fingerprint.slice(0, 12) + "…" : "-") + '</td>'
          + '<td class="muted">' + esc(e.detail || "-") + '</td>'
          + '</tr>'
        )).join("");
      }
      showModal('<h2>License Audit Events</h2>'
        + '<p class="sub">Complete audit history for License #' + licId + '</p>'
        + '<div style="max-height:320px;overflow-y:auto;margin:12px 0;">'
        + '<table class="table" style="font-size:12px;">'
        + '<thead><tr><th>Action</th><th>Timestamp</th><th>Result</th><th>Device</th><th>Detail</th></tr></thead>'
        + '<tbody>' + rows + '</tbody></table></div>'
        + '<div class="modal-actions"><button class="btn primary" id="m-close-events">Close</button></div>');
      $("#m-close-events").onclick = hideModal;
    } catch (e) { toast(e.message, "err"); }
  }

  // ---- Modals ----
  function showCustomerModal() {
    showModal('<h2>New Customer</h2>'
      + '<label>Name <input id="m-cust-name" required placeholder="e.g. Acme Furniture"></label>'
      + '<label>Mobile <input id="m-cust-mobile" placeholder="e.g. 9876543210"></label>'
      + '<label>Email <input id="m-cust-email" type="email" placeholder="customer@example.com"></label>'
      + '<label>Notes <input id="m-cust-notes" placeholder="Optional notes"></label>'
      + '<div class="modal-actions"><button class="btn" id="m-cancel">Cancel</button><button class="btn primary" id="m-save-cust">Save</button></div>');
    $("#m-cancel").onclick = hideModal;
    $("#m-save-cust").onclick = async () => {
      const name = ($("#m-cust-name").value || "").trim();
      if (!name) { toast("Name is required.", "err"); return; }
      try {
        await api("POST", "/admin/customers", { name, mobile: $("#m-cust-mobile").value || null, email: $("#m-cust-email").value || null, notes: $("#m-cust-notes").value || null });
        hideModal(); toast("Customer created.", "ok"); await loadCustomers();
      } catch (e) { toast(e.message, "err"); }
    };
  }

  async function showLicenseModal() {
    await loadCustomers();
    if (!customers.length) { toast("Create a customer first.", "err"); return; }
    const opts = customers.map(c => '<option value="' + c.id + '">' + esc(c.name) + '</option>').join("");
    showModal('<h2>New Commercial License</h2>'
      + '<label>Customer <select id="m-lic-cust">' + opts + '</select></label>'
      + '<label>Product <select id="m-lic-prod">'
      +   '<option value="furniture_bill">Furniture / Interior Billing (FB)</option>'
      +   '<option value="ac_service">AC Service / AMC / Inventory (AC)</option>'
      +   '<option value="future_product">Future Product (FP)</option>'
      + '</select></label>'
      + '<label>License Type <select id="m-lic-type"><option value="LIFETIME">LIFETIME (One-Time / Offline-First)</option></select></label>'
      + '<label>Device Limit <input id="m-lic-limit" type="number" min="1" max="10" value="1"></label>'
      + '<div class="modal-actions"><button class="btn" id="m-cancel">Cancel</button><button class="btn primary" id="m-save-lic">Generate License</button></div>');
    $("#m-cancel").onclick = hideModal;
    $("#m-save-lic").onclick = async () => {
      const cid = parseInt($("#m-lic-cust").value);
      const product = $("#m-lic-prod").value || "furniture_bill";
      const limit = parseInt($("#m-lic-limit").value) || 1;
      if (!cid) { toast("Select a customer.", "err"); return; }
      try {
        const d = await api("POST", "/api/v1/admin/licenses", { customer_id: cid, product: product, license_type: "LIFETIME", device_limit: limit });
        hideModal();
        toast("License generated: " + d.license.license_key, "ok");
        await loadLicenses();
      } catch (e) { toast(e.message, "err"); }
    };
  }

  // ---- Events ----
  document.addEventListener("DOMContentLoaded", () => {
    if (token) showDash(); else showLogin();

    $("#login-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const u = $("#login-username").value.trim();
      const p = $("#login-password").value;
      if (!u || !p) return;
      try {
        const d = await api("POST", "/admin/login", { username: u, password: p });
        if (!d.token) throw new Error(d.detail || "Login failed");
        setToken(d.token);
        $("#login-error").textContent = "";
        showDash();
      } catch (ex) { $("#login-error").textContent = "Invalid credentials."; }
    });

    $("#logout-btn").addEventListener("click", () => { setToken(null); showLogin(); });
    $$(".tab").forEach(t => t.addEventListener("click", () => switchTab(t.dataset.tab)));
    $("#license-search").addEventListener("input", () => { clearTimeout(this._t); this._t = setTimeout(loadLicenses, 350); });
    $("#customer-search").addEventListener("input", () => { clearTimeout(this._t); this._t = setTimeout(loadCustomers, 350); });

    $("#new-customer-btn").addEventListener("click", showCustomerModal);
    $("#new-license-btn").addEventListener("click", showLicenseModal);

    $("#license-rows").addEventListener("click", (e) => {
      const btn = e.target.closest("[data-act]");
      if (btn) licAction(btn.dataset.act, parseInt(btn.dataset.id));
    });

    $("#modal-overlay").addEventListener("click", (e) => { if (e.target === $("#modal-overlay")) hideModal(); });
  });
})();