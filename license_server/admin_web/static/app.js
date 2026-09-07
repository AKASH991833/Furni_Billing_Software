/* ==========================================================================
   Furniture Bill License Admin - Modern SPA Controller
   ========================================================================== */
(function () {
  "use strict";

  const $ = (s, c) => (c || document).querySelector(s);
  const $$ = (s, c) => [...(c || document).querySelectorAll(s)];

  // ---- Authentication & Token ----
  let token = localStorage.getItem("fb_admin_token");
  let currentUsername = localStorage.getItem("fb_admin_username") || "Administrator";

  function setToken(t, u) {
    token = t;
    if (t) {
      localStorage.setItem("fb_admin_token", t);
      if (u) {
        currentUsername = u;
        localStorage.setItem("fb_admin_username", u);
      }
    } else {
      localStorage.removeItem("fb_admin_token");
      localStorage.removeItem("fb_admin_username");
    }
    updateAdminDisplay();
  }

  function updateAdminDisplay() {
    const el = $("#admin-display-name");
    if (el) el.textContent = currentUsername;
  }

  // ---- API Client ----
  async function api(method, path, body) {
    const opts = { method, headers: {} };
    if (token) opts.headers["Authorization"] = "Bearer " + token;
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    const res = await fetch(path, opts);
    const json = await res.json().catch(() => ({}));
    if (!res.ok) {
      if (res.status === 401) {
        setToken(null);
        showLogin();
        throw new Error("Session expired. Please sign in again.");
      }
      throw new Error(json.message || json.detail || "Server request failed (" + res.status + ")");
    }
    return json;
  }

  // ---- Clipboard Helper ----
  function copyToClipboard(text, msg) {
    if (!text) return;
    const successMsg = msg || "Copied to clipboard!";
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text).then(() => {
        toast(successMsg, "ok");
      }).catch(() => {
        fallbackCopy(text, successMsg);
      });
    } else {
      fallbackCopy(text, successMsg);
    }
  }

  function fallbackCopy(text, msg) {
    const ta = document.createElement("textarea");
    ta.value = text;
    ta.style.position = "fixed";
    ta.style.left = "-9999px";
    ta.style.top = "-9999px";
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try {
      document.execCommand("copy");
      toast(msg, "ok");
    } catch (e) {
      prompt("Copy to clipboard (Ctrl+C, Enter):", text);
    }
    document.body.removeChild(ta);
  }

  // ---- View Switching ----
  function showLogin() {
    $("#login-view").classList.remove("hidden");
    $("#dashboard-view").classList.add("hidden");
  }

  function showDash() {
    $("#login-view").classList.add("hidden");
    $("#dashboard-view").classList.remove("hidden");
    updateAdminDisplay();
    refreshAll();
  }

  // ---- Modal Dialogs ----
  function showModal(html) {
    $("#modal-box").innerHTML = html;
    $("#modal-overlay").classList.remove("hidden");
  }

  function hideModal() {
    $("#modal-overlay").classList.add("hidden");
    $("#modal-box").innerHTML = "";
  }

  // ---- Navigation Tabs ----
  function switchTab(name) {
    $$(".tab").forEach(t => t.classList.toggle("active", t.dataset.tab === name));
    $("#panel-licenses").classList.toggle("hidden", name !== "licenses");
    $("#panel-customers").classList.toggle("hidden", name !== "customers");
  }

  // ---- State & Data ----
  let licenses = [];
  let customers = [];
  let customerMap = {};

  async function refreshAll() {
    await Promise.all([loadLicenses(), loadCustomers()]);
    updateStats();
  }

  function updateStats() {
    $("#stat-total-licenses").textContent = licenses.length;
    const activeCount = licenses.filter(l => l.status === "ACTIVE").length;
    $("#stat-active-licenses").textContent = activeCount;
    $("#stat-total-customers").textContent = customers.length;
    const boundCount = licenses.filter(l => Boolean(l.current_device)).length;
    $("#stat-bound-devices").textContent = boundCount;

    $("#count-licenses").textContent = licenses.length;
    $("#count-customers").textContent = customers.length;
  }

  async function loadLicenses() {
    try {
      const q = ($("#license-search") || {}).value || "";
      const d = await api("GET", "/api/v1/admin/licenses?search=" + encodeURIComponent(q));
      licenses = d.licenses || [];
      renderLicenses();
      updateStats();
    } catch (e) {
      toast(e.message, "err");
    }
  }

  async function loadCustomers() {
    try {
      const q = ($("#customer-search") || {}).value || "";
      const d = await api("GET", "/api/v1/admin/customers?search=" + encodeURIComponent(q));
      customers = d.customers || [];
      customerMap = {};
      customers.forEach(c => customerMap[c.id] = c);
      renderCustomers();
      updateStats();
    } catch (e) {
      toast(e.message, "err");
    }
  }

  // ---- Helpers ----
  function esc(s) {
    if (!s) return "";
    const d = document.createElement("div");
    d.textContent = s;
    return d.innerHTML;
  }

  function badge(status) {
    const cls = { "ACTIVE": "active", "REVOKED": "revoked", "BLOCKED": "blocked" }[status] || "revoked";
    return '<span class="badge ' + cls + '">' + esc(status) + '</span>';
  }

  function dateShort(v) {
    return v ? v.slice(0, 10) : "-";
  }

  // ---- Renderers ----
  function renderLicenses() {
    const tbody = $("#license-rows");
    if (!licenses.length) {
      tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No commercial licenses found. Click "+ Issue New License" to generate one.</td></tr>';
      return;
    }
    tbody.innerHTML = licenses.map(lic => {
      const cust = lic.customer_name || customerMap[lic.customer_id]?.name || "Unassigned";
      const prodLabel = (lic.product === "ac_service" ? "AC Service (AC)" : (lic.product === "future_product" ? "Future Product (FP)" : "Furniture Bill (FB)"));
      const isDeviceBound = Boolean(lic.current_device);
      const devDisplay = isDeviceBound ? (lic.device_label || esc(lic.current_device.slice(0, 14)) + "&hellip;") : '<span class="muted">Unbound (0/' + (lic.device_limit || 1) + ')</span>';

      return '<tr data-id="' + lic.id + '">'
        + '<td>'
        +   '<div class="key-wrapper">'
        +     '<span class="key-code">' + esc(lic.license_key) + '</span>'
        +     '<button class="btn-copy" data-copy="' + esc(lic.license_key) + '" title="Copy License Key">'
        +       '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>'
        +     '</button>'
        +   '</div>'
        + '</td>'
        + '<td><span class="product-tag">' + esc(prodLabel) + '</span></td>'
        + '<td><strong style="color:#FFF;">' + esc(cust) + '</strong></td>'
        + '<td>' + badge(lic.status) + '</td>'
        + '<td>' + devDisplay + '</td>'
        + '<td class="muted">' + dateShort(lic.activated_at) + '</td>'
        + '<td>'
        +   '<div class="row-actions">'
        +     '<button class="btn btn-action" data-act="reset" data-id="' + lic.id + '"' + (!isDeviceBound ? ' disabled' : '') + ' title="Allow customer to activate on a new machine">Reset Device</button>'
        +     '<button class="btn btn-action" data-act="events" data-id="' + lic.id + '" title="View complete audit log">Audit</button>'
        +     (lic.status === "ACTIVE" 
                ? '<button class="btn btn-action danger" data-act="revoke" data-id="' + lic.id + '">Revoke</button>'
                : '<button class="btn btn-action success" data-act="activate" data-id="' + lic.id + '">Reactivate</button>')
        +     (lic.status !== "BLOCKED" ? '<button class="btn btn-action danger" data-act="block" data-id="' + lic.id + '">Block</button>' : '')
        +     '<button class="btn btn-action danger" data-act="delete" data-id="' + lic.id + '" title="Delete license permanently">Delete</button>'
        +   '</div>'
        + '</td>'
        + '</tr>';
    }).join("");
  }

  function renderCustomers() {
    const tbody = $("#customer-rows");
    if (!customers.length) {
      tbody.innerHTML = '<tr><td colspan="6" class="empty-state">No customers registered yet. Click "+ Add New Customer" above.</td></tr>';
      return;
    }
    tbody.innerHTML = customers.map(c => {
      const custLicenses = licenses.filter(l => l.customer_id === c.id);
      let licCell = '';
      if (!custLicenses.length) {
        licCell = '<div class="cust-lic-empty">'
          + '<span class="muted" style="font-size:12px;">No key issued</span>'
          + '<button class="btn btn-sm btn-primary" data-cust-act="license" data-id="' + c.id + '" style="margin-left:6px;padding:3px 8px;font-size:11px;">+ Issue Key</button>'
          + '</div>';
      } else {
        licCell = '<div class="cust-lic-list">'
          + custLicenses.map(lic => {
            const isBound = Boolean(lic.current_device);
            return '<div class="cust-lic-item">'
              + '<div class="key-wrapper" style="padding:2px 7px;">'
              +   '<span class="key-code" style="font-size:12px;">' + esc(lic.license_key) + '</span>'
              +   '<button class="btn-copy" data-copy="' + esc(lic.license_key) + '" title="Copy License Key">'
              +     '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>'
              +   '</button>'
              + '</div>'
              + ' ' + badge(lic.status)
              + ' ' + (isBound 
                       ? '<span class="badge" style="background:rgba(59,130,246,0.15);color:#93C5FD;border:1px solid rgba(59,130,246,0.3);font-size:10.5px;" title="' + esc(lic.current_device) + '">Active on PC</span>' 
                       : '<span class="badge" style="background:rgba(148,163,184,0.1);color:#94A3B8;border:1px solid rgba(148,163,184,0.2);font-size:10.5px;">Ready to Activate</span>')
              + '</div>';
          }).join("")
          + '</div>';
      }

      return '<tr data-cust-id="' + c.id + '">'
        + '<td>'
        +   '<div><strong style="color:#FFF;font-size:14px;">' + esc(c.name) + '</strong></div>'
        +   (c.notes ? '<div class="muted" style="font-size:11.5px;margin-top:2px;">' + esc(c.notes) + '</div>' : '')
        + '</td>'
        + '<td>' + (c.mobile ? '<span>' + esc(c.mobile) + '</span>' : '<span class="muted">-</span>') + '</td>'
        + '<td>' + (c.email ? '<a href="mailto:' + esc(c.email) + '" style="color:#818CF8;text-decoration:none;">' + esc(c.email) + '</a>' : '<span class="muted">-</span>') + '</td>'
        + '<td>' + licCell + '</td>'
        + '<td class="muted">' + dateShort(c.created_at) + '</td>'
        + '<td>'
        +   '<div class="row-actions">'
        +     '<button class="btn btn-sm btn-primary" data-cust-act="license" data-id="' + c.id + '" title="Generate new license for ' + esc(c.name) + '">+ Issue License</button>'
        +     '<button class="btn btn-action" data-cust-act="edit" data-id="' + c.id + '" title="Edit customer details">Edit</button>'
        +     '<button class="btn btn-action danger" data-cust-act="delete" data-id="' + c.id + '" title="Delete customer and their licenses">Delete</button>'
        +   '</div>'
        + '</td>'
        + '</tr>';
    }).join("");
  }

  // ---- License Actions ----
  async function licAction(act, id) {
    if (act === "events") {
      await showEventsModal(id);
      return;
    }
    if (act === "delete") {
      if (!confirm("Are you sure you want to permanently DELETE this license from the database?")) return;
      try {
        await api("DELETE", "/api/v1/admin/licenses/" + id);
        toast("License deleted successfully.", "ok");
        await refreshAll();
      } catch (e) {
        toast(e.message, "err");
      }
      return;
    }

    const confirmMsg = {
      reset: "Reset the device binding for this license? The customer will be able to activate on their new PC.",
      revoke: "Are you sure you want to REVOKE this license? The software will stop working on the client machine.",
      block: "BLOCK this license? Activations will be immediately prohibited.",
      activate: "Reactivate this license and set status back to ACTIVE?"
    };
    if (!confirm(confirmMsg[act] || "Continue with this action?")) return;

    try {
      if (act === "reset") {
        await api("POST", "/api/v1/admin/licenses/" + id + "/reset-device", { reason: "Admin reset from Web Portal" });
        toast("Device binding reset. Customer can now activate on new PC.", "ok");
      } else if (act === "activate") {
        await api("POST", "/api/v1/admin/licenses/" + id + "/reactivate", { reason: "Admin reactivated from Web Portal" });
        toast("License status set to ACTIVE.", "ok");
      } else if (act === "revoke") {
        await api("POST", "/api/v1/admin/licenses/" + id + "/revoke", { reason: "Admin revoked from Web Portal" });
        toast("License successfully REVOKED.", "ok");
      } else if (act === "block") {
        await api("POST", "/api/v1/admin/licenses/" + id + "/block", { reason: "Admin blocked from Web Portal" });
        toast("License BLOCKED.", "ok");
      }
      await refreshAll();
    } catch (e) {
      toast(e.message, "err");
    }
  }

  // ---- Customer Actions ----
  async function custAction(act, id) {
    const c = customerMap[id];
    if (!c) return;

    if (act === "license") {
      showLicenseModal(id);
      return;
    }
    if (act === "edit") {
      showEditCustomerModal(id);
      return;
    }
    if (act === "delete") {
      if (!confirm("Are you sure you want to DELETE customer '" + c.name + "'? ALL licenses issued to this customer will also be permanently deleted.")) return;
      try {
        await api("DELETE", "/api/v1/admin/customers/" + id);
        toast("Customer '" + c.name + "' and licenses deleted.", "ok");
        await refreshAll();
      } catch (e) {
        toast(e.message, "err");
      }
    }
  }

  // ---- Audit Events Modal ----
  async function showEventsModal(licId) {
    try {
      const res = await api("GET", "/api/v1/admin/licenses/" + licId + "/events");
      const evs = res.events || [];
      let rows = '<tr><td colspan="5" class="empty-state">No audit logs recorded for this license.</td></tr>';
      if (evs.length) {
        rows = evs.map(e => (
          '<tr>'
          + '<td><strong style="color:#FFF;">' + esc(e.action) + '</strong></td>'
          + '<td class="muted">' + esc((e.created_at || "").slice(0, 19).replace("T", " ")) + '</td>'
          + '<td>' + (e.success ? '<span class="badge active">Success</span>' : '<span class="badge blocked">Failed</span>') + '</td>'
          + '<td><code style="color:#A5B4FC;font-size:11px;">' + esc(e.device_fingerprint ? e.device_fingerprint.slice(0, 14) + "…" : "-") + '</code></td>'
          + '<td class="muted">' + esc(e.detail || "-") + '</td>'
          + '</tr>'
        )).join("");
      }
      showModal('<h2>Security Audit Trail</h2>'
        + '<p class="sub">Complete chronological event history for License #' + licId + '</p>'
        + '<div style="max-height:340px;overflow-y:auto;margin:16px 0;border:1px solid var(--border);border-radius:8px;">'
        + '<table class="table" style="font-size:12px;">'
        + '<thead><tr><th>Action</th><th>Timestamp</th><th>Status</th><th>Device</th><th>Notes</th></tr></thead>'
        + '<tbody>' + rows + '</tbody></table></div>'
        + '<div class="modal-actions"><button class="btn btn-primary" id="m-close-events">Done</button></div>');
      $("#m-close-events").onclick = hideModal;
    } catch (e) {
      toast(e.message, "err");
    }
  }

  // ---- Customer Edit Modal ----
  function showEditCustomerModal(customerId) {
    const c = customerMap[customerId];
    if (!c) return;
    showModal('<h2>Edit Customer</h2>'
      + '<p class="sub">Update details for ' + esc(c.name) + '</p>'
      + '<div class="form-group">'
      +   '<label for="m-edit-name">Business / Customer Name *</label>'
      +   '<input type="text" id="m-edit-name" value="' + esc(c.name) + '" required autofocus autocomplete="off">'
      + '</div>'
      + '<div class="form-group">'
      +   '<label for="m-edit-mobile">Mobile Phone Number</label>'
      +   '<input type="tel" id="m-edit-mobile" value="' + esc(c.mobile || '') + '" placeholder="e.g. 9876543210" autocomplete="off">'
      + '</div>'
      + '<div class="form-group">'
      +   '<label for="m-edit-email">Email Address</label>'
      +   '<input type="email" id="m-edit-email" value="' + esc(c.email || '') + '" placeholder="client@example.com" autocomplete="off">'
      + '</div>'
      + '<div class="form-group">'
      +   '<label for="m-edit-notes">Notes / City / Region</label>'
      +   '<input type="text" id="m-edit-notes" value="' + esc(c.notes || '') + '" placeholder="Optional notes" autocomplete="off">'
      + '</div>'
      + '<div class="modal-actions">'
      +   '<button class="btn btn-ghost" id="m-cancel">Cancel</button>'
      +   '<button class="btn btn-primary" id="m-save-edit-cust">Save Changes</button>'
      + '</div>');

    $("#m-cancel").onclick = hideModal;
    $("#m-save-edit-cust").onclick = async () => {
      const name = ($("#m-edit-name").value || "").trim();
      if (!name) { toast("Customer name is required.", "err"); return; }
      try {
        await api("PUT", "/api/v1/admin/customers/" + customerId, {
          name: name,
          mobile: $("#m-edit-mobile").value || null,
          email: $("#m-edit-email").value || null,
          notes: $("#m-edit-notes").value || null
        });
        hideModal();
        toast("Customer updated successfully.", "ok");
        await refreshAll();
      } catch (e) {
        toast(e.message, "err");
      }
    };
  }

  // ---- Change Password Modal ----
  function showChangePasswordModal() {
    showModal('<h2>Change Administrator Password</h2>'
      + '<p class="sub">Update your master portal password. This change takes effect immediately.</p>'
      + '<div class="form-group">'
      +   '<label for="m-pwd-curr">Current Password *</label>'
      +   '<input type="password" id="m-pwd-curr" placeholder="Enter current password" required autofocus autocomplete="current-password">'
      + '</div>'
      + '<div class="form-group">'
      +   '<label for="m-pwd-new">New Password * (min 6 chars)</label>'
      +   '<input type="password" id="m-pwd-new" placeholder="Enter new strong password" required autocomplete="new-password">'
      + '</div>'
      + '<div class="form-group">'
      +   '<label for="m-pwd-confirm">Confirm New Password *</label>'
      +   '<input type="password" id="m-pwd-confirm" placeholder="Re-enter new password" required autocomplete="new-password">'
      + '</div>'
      + '<div id="m-pwd-error" style="color:#FB7185;font-size:13px;margin-bottom:12px;font-weight:500;"></div>'
      + '<div class="modal-actions">'
      +   '<button class="btn btn-ghost" id="m-cancel">Cancel</button>'
      +   '<button class="btn btn-primary" id="m-save-pwd">Update Password</button>'
      + '</div>');

    $("#m-cancel").onclick = hideModal;
    $("#m-save-pwd").onclick = async () => {
      const curr = $("#m-pwd-curr").value;
      const n = $("#m-pwd-new").value;
      const c = $("#m-pwd-confirm").value;
      const errEl = $("#m-pwd-error");
      errEl.textContent = "";

      if (!curr || !n || !c) {
        errEl.textContent = "All fields are required.";
        return;
      }
      if (n.length < 6) {
        errEl.textContent = "New password must be at least 6 characters.";
        return;
      }
      if (n !== c) {
        errEl.textContent = "New passwords do not match.";
        return;
      }

      try {
        const res = await api("POST", "/api/v1/admin/change-password", {
          current_password: curr,
          new_password: n
        });
        hideModal();
        toast("Password changed successfully!", "ok");
      } catch (e) {
        errEl.textContent = e.message || "Failed to update password.";
      }
    };
  }

  // ---- Customer Creation Modal ----
  function showCustomerModal() {
    showModal('<h2>Add New Customer</h2>'
      + '<p class="sub">Register a new business client to issue software licenses.</p>'
      + '<div class="form-group">'
      +   '<label for="m-cust-name">Business / Customer Name *</label>'
      +   '<input type="text" id="m-cust-name" placeholder="e.g. Modern Furniture Mart" required autofocus autocomplete="off">'
      + '</div>'
      + '<div class="form-group">'
      +   '<label for="m-cust-mobile">Mobile Phone Number</label>'
      +   '<input type="tel" id="m-cust-mobile" placeholder="e.g. 9876543210" autocomplete="off">'
      + '</div>'
      + '<div class="form-group">'
      +   '<label for="m-cust-email">Email Address</label>'
      +   '<input type="email" id="m-cust-email" placeholder="client@example.com" autocomplete="off">'
      + '</div>'
      + '<div class="form-group">'
      +   '<label for="m-cust-notes">Notes / City / Region</label>'
      +   '<input type="text" id="m-cust-notes" placeholder="e.g. Mumbai branch, 2-seat install" autocomplete="off">'
      + '</div>'
      + '<div class="modal-actions">'
      +   '<button class="btn btn-ghost" id="m-cancel">Cancel</button>'
      +   '<button class="btn btn-primary" id="m-save-cust">Create Customer</button>'
      + '</div>');
    
    $("#m-cancel").onclick = hideModal;
    $("#m-save-cust").onclick = async () => {
      const name = ($("#m-cust-name").value || "").trim();
      if (!name) { toast("Customer name is required.", "err"); return; }
      try {
        const res = await api("POST", "/api/v1/admin/customers", {
          name: name,
          mobile: $("#m-cust-mobile").value || null,
          email: $("#m-cust-email").value || null,
          notes: $("#m-cust-notes").value || null
        });
        toast("Customer '" + name + "' created successfully.", "ok");
        await refreshAll();

        const createdCust = res.customer;
        // Offer immediate license generation
        showModal('<h2>🎉 Customer Registered!</h2>'
          + '<p class="sub"><strong>' + esc(name) + '</strong> has been added successfully.</p>'
          + '<div style="background:rgba(99,102,241,0.08);border:1px solid rgba(99,102,241,0.25);border-radius:10px;padding:18px;margin:16px 0;text-align:center;">'
          +   '<p style="margin:0 0 14px;color:#E2E8F0;font-size:14px;">Would you like to generate an official commercial license key for <strong>' + esc(name) + '</strong> right now?</p>'
          +   '<button class="btn btn-primary" id="m-cust-gen-now" style="font-size:14px;padding:10px 22px;">⚡ Yes, Issue License Key Now</button>'
          + '</div>'
          + '<div class="modal-actions">'
          +   '<button class="btn btn-ghost" id="m-cust-done">Later / Done</button>'
          + '</div>');
        $("#m-cust-gen-now").onclick = () => showLicenseModal(createdCust ? createdCust.id : null);
        $("#m-cust-done").onclick = () => hideModal();
      } catch (e) {
        toast(e.message, "err");
      }
    };
  }

  // ---- License Creation Modal ----
  async function showLicenseModal(preselectedCustomerId = null) {
    await loadCustomers();
    if (!customers.length) {
      toast("Please create a customer first before generating a license.", "err");
      showCustomerModal();
      return;
    }
    const opts = customers.map(c => {
      const selected = (preselectedCustomerId && c.id === preselectedCustomerId) ? ' selected' : '';
      return '<option value="' + c.id + '"' + selected + '>' + esc(c.name) + '</option>';
    }).join("");

    showModal('<h2>Generate Commercial License</h2>'
      + '<p class="sub">Issue a cryptographically signed license key for a customer.</p>'
      + '<div class="form-group">'
      +   '<label for="m-lic-cust">Customer Account *</label>'
      +   '<select id="m-lic-cust">' + opts + '</select>'
      + '</div>'
      + '<div class="form-group">'
      +   '<label for="m-lic-prod">Software Product *</label>'
      +   '<select id="m-lic-prod">'
      +     '<option value="furniture_bill">Furniture Billing Desktop (FB-)</option>'
      +     '<option value="ac_service">AC Service & Maintenance (AC-)</option>'
      +     '<option value="future_product">Future Desktop Application (FP-)</option>'
      +   '</select>'
      + '</div>'
      + '<div class="form-group">'
      +   '<label for="m-lic-type">License Validity</label>'
      +   '<select id="m-lic-type"><option value="LIFETIME">LIFETIME (Permanent / Offline-First)</option></select>'
      + '</div>'
      + '<div class="form-group">'
      +   '<label for="m-lic-limit">Authorized Device Count (Seats)</label>'
      +   '<input type="number" id="m-lic-limit" min="1" max="20" value="1">'
      + '</div>'
      + '<div class="modal-actions">'
      +   '<button class="btn btn-ghost" id="m-cancel">Cancel</button>'
      +   '<button class="btn btn-primary" id="m-save-lic">Generate License Key</button>'
      + '</div>');

    $("#m-cancel").onclick = hideModal;
    $("#m-save-lic").onclick = async () => {
      const cid = parseInt($("#m-lic-cust").value);
      const product = $("#m-lic-prod").value || "furniture_bill";
      const limit = parseInt($("#m-lic-limit").value) || 1;
      if (!cid) { toast("Please select a valid customer.", "err"); return; }
      try {
        const d = await api("POST", "/api/v1/admin/licenses", {
          customer_id: cid,
          product: product,
          license_type: "LIFETIME",
          device_limit: limit
        });
        toast("License generated: " + d.license.license_key, "ok");
        await refreshAll();
        showLicenseSuccessModal(d.license, customerMap[cid]);
      } catch (e) {
        toast(e.message, "err");
      }
    };
  }

  // ---- License Generated Success Screen ----
  function showLicenseSuccessModal(lic, customer) {
    const custName = customer ? customer.name : "Valued Client";
    const key = lic.license_key;
    const prodNames = {
      "furniture_bill": "Furniture Billing Desktop Application",
      "ac_service": "AC Service & Maintenance Software",
      "future_product": "Desktop Application"
    };
    const prodName = prodNames[lic.product] || lic.product || "Software";
    const handoverText = `Hello ${custName},\n\nHere is your official commercial software license key:\n\nSoftware: ${prodName}\nLicense Key: ${key}\nLicense Type: Lifetime Edition\nDevice Seats: ${lic.device_limit || 1} PC\n\nHow to activate on your computer:\n1. Launch ${prodName} on your PC.\n2. Open the Activation screen (or click Help -> Activate License).\n3. Enter the License Key above and click 'Activate License'.\n\nThank you for choosing our software!`;

    showModal('<h2>🎉 Commercial License Key Generated!</h2>'
      + '<p class="sub">Official cryptographic key issued for <strong>' + esc(custName) + '</strong>.</p>'
      + '<div class="big-key-display">'
      +   '<div>'
      +     '<div style="font-size:11px;text-transform:uppercase;color:#94A3B8;letter-spacing:0.5px;margin-bottom:4px;">Official Commercial License Key</div>'
      +     '<div class="key-text" id="gen-key-val">' + esc(key) + '</div>'
      +   '</div>'
      +   '<button class="btn btn-primary" id="btn-copy-gen" style="min-width:110px;">📋 Copy Key</button>'
      + '</div>'
      + '<div class="key-meta-grid">'
      +   '<div class="meta-item"><span class="meta-label">Customer</span><span class="meta-val">' + esc(custName) + '</span></div>'
      +   '<div class="meta-item"><span class="meta-label">Product</span><span class="meta-val">' + esc(prodName) + '</span></div>'
      +   '<div class="meta-item"><span class="meta-label">Validity</span><span class="meta-val">LIFETIME</span></div>'
      +   '<div class="meta-item"><span class="meta-label">Authorized Devices</span><span class="meta-val">' + (lic.device_limit || 1) + ' PC</span></div>'
      + '</div>'
      + '<div class="whatsapp-share-card">'
      +   '<div style="display:flex;justify-content:space-between;align-items:center;">'
      +     '<label style="margin:0;">Client Handover Message (WhatsApp / Email Ready):</label>'
      +     '<button class="btn btn-ghost btn-sm" id="btn-copy-handover" style="padding:2px 8px;font-size:11px;">📋 Copy Message</button>'
      +   '</div>'
      +   '<textarea id="m-handover-msg" readonly rows="4">' + esc(handoverText) + '</textarea>'
      + '</div>'
      + '<div class="modal-actions" style="justify-content:space-between;">'
      +   '<button class="btn btn-ghost" id="m-done-close">Done</button>'
      +   '<button class="btn btn-primary" id="m-view-lic-tab">View in Licenses Tab →</button>'
      + '</div>');

    $("#btn-copy-gen").onclick = () => {
      copyToClipboard(key, "License Key copied to clipboard!");
    };
    $("#btn-copy-handover").onclick = () => {
      copyToClipboard(handoverText, "Full client handover message copied!");
    };
    $("#m-done-close").onclick = async () => {
      hideModal();
      await refreshAll();
    };
    $("#m-view-lic-tab").onclick = async () => {
      hideModal();
      await refreshAll();
      switchTab("licenses");
    };
  }

  // ---- Global Event Listeners ----
  document.addEventListener("DOMContentLoaded", () => {
    if (token) showDash();
    else showLogin();

    // Login Form Submit
    $("#login-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const u = $("#login-username").value.trim();
      const p = $("#login-password").value;
      if (!u || !p) return;
      try {
        const d = await api("POST", "/api/v1/admin/login", { username: u, password: p });
        if (!d.token) throw new Error(d.detail || "Invalid credentials.");
        setToken(d.token, d.username || u);
        $("#login-error").textContent = "";
        showDash();
      } catch (ex) {
        $("#login-error").textContent = "Invalid username or password. Please try again.";
      }
    });

    // Logout Button
    $("#logout-btn").addEventListener("click", () => {
      setToken(null);
      showLogin();
      toast("Signed out successfully.", "ok");
    });

    // Change Password Button
    $("#btn-change-password").addEventListener("click", showChangePasswordModal);

    // Tab Navigation
    $$(".tab").forEach(t => t.addEventListener("click", () => switchTab(t.dataset.tab)));

    // Search with debounce
    let licTimer, custTimer;
    $("#license-search").addEventListener("input", () => {
      clearTimeout(licTimer);
      licTimer = setTimeout(loadLicenses, 300);
    });
    $("#customer-search").addEventListener("input", () => {
      clearTimeout(custTimer);
      custTimer = setTimeout(loadCustomers, 300);
    });

    // New Buttons
    $("#new-customer-btn").addEventListener("click", showCustomerModal);
    $("#new-license-btn").addEventListener("click", () => showLicenseModal());

    // License Rows Actions
    $("#license-rows").addEventListener("click", (e) => {
      // Check Copy Button
      const copyBtn = e.target.closest(".btn-copy");
      if (copyBtn) {
        const key = copyBtn.dataset.copy;
        copyToClipboard(key, "Copied license key: " + key);
        return;
      }
      // Check Row Action Button
      const btn = e.target.closest("[data-act]");
      if (btn) licAction(btn.dataset.act, parseInt(btn.dataset.id));
    });

    // Customer Rows Actions
    $("#customer-rows").addEventListener("click", (e) => {
      // Check Copy Button inside Customer Table
      const copyBtn = e.target.closest(".btn-copy");
      if (copyBtn) {
        const key = copyBtn.dataset.copy;
        copyToClipboard(key, "Copied license key: " + key);
        return;
      }
      const btn = e.target.closest("[data-cust-act]");
      if (btn) custAction(btn.dataset.custAct, parseInt(btn.dataset.id));
    });

    // Modal dismiss on overlay click
    $("#modal-overlay").addEventListener("click", (e) => {
      if (e.target === $("#modal-overlay")) hideModal();
    });
  });
})();