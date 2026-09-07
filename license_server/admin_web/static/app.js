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

  // ---- Toast Notifications ----
  function toast(msg, kind) {
    const el = document.createElement("div");
    el.className = "toast " + (kind || "ok");
    const icon = kind === "err" ? "✕" : "✓";
    el.innerHTML = '<span style="font-size:16px;">' + icon + '</span><span>' + esc(msg) + '</span>';
    $("#toast-wrap").appendChild(el);
    setTimeout(() => {
      el.style.opacity = "0";
      el.style.transform = "translateX(20px)";
      setTimeout(() => el.remove(), 200);
    }, 4000);
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
      const licCount = licenses.filter(l => l.customer_id === c.id).length;
      return '<tr data-cust-id="' + c.id + '">'
        + '<td><strong style="color:#FFF;font-size:14px;">' + esc(c.name) + '</strong></td>'
        + '<td>' + (c.mobile ? '<span>' + esc(c.mobile) + '</span>' : '<span class="muted">-</span>') + '</td>'
        + '<td>' + (c.email ? '<a href="mailto:' + esc(c.email) + '" style="color:#818CF8;text-decoration:none;">' + esc(c.email) + '</a>' : '<span class="muted">-</span>') + '</td>'
        + '<td><span class="badge active" style="font-size:11px;">' + licCount + ' License' + (licCount === 1 ? '' : 's') + '</span></td>'
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
      +   '<label>Business / Customer Name *</label>'
      +   '<input id="m-edit-name" value="' + esc(c.name) + '" required autofocus>'
      + '</div>'
      + '<div class="form-group">'
      +   '<label>Mobile Phone Number</label>'
      +   '<input id="m-edit-mobile" value="' + esc(c.mobile || '') + '" placeholder="e.g. 9876543210">'
      + '</div>'
      + '<div class="form-group">'
      +   '<label>Email Address</label>'
      +   '<input id="m-edit-email" type="email" value="' + esc(c.email || '') + '" placeholder="client@example.com">'
      + '</div>'
      + '<div class="form-group">'
      +   '<label>Notes / City / Region</label>'
      +   '<input id="m-edit-notes" value="' + esc(c.notes || '') + '" placeholder="Optional notes">'
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
      +   '<label>Current Password *</label>'
      +   '<input id="m-pwd-curr" type="password" placeholder="Enter current password" required autofocus>'
      + '</div>'
      + '<div class="form-group">'
      +   '<label>New Password * (min 6 chars)</label>'
      +   '<input id="m-pwd-new" type="password" placeholder="Enter new strong password" required>'
      + '</div>'
      + '<div class="form-group">'
      +   '<label>Confirm New Password *</label>'
      +   '<input id="m-pwd-confirm" type="password" placeholder="Re-enter new password" required>'
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
      +   '<label>Business / Customer Name *</label>'
      +   '<input id="m-cust-name" placeholder="e.g. Modern Furniture Mart" required autofocus>'
      + '</div>'
      + '<div class="form-group">'
      +   '<label>Mobile Phone Number</label>'
      +   '<input id="m-cust-mobile" placeholder="e.g. 9876543210">'
      + '</div>'
      + '<div class="form-group">'
      +   '<label>Email Address</label>'
      +   '<input id="m-cust-email" type="email" placeholder="client@example.com">'
      + '</div>'
      + '<div class="form-group">'
      +   '<label>Notes / City / Region</label>'
      +   '<input id="m-cust-notes" placeholder="e.g. Mumbai branch, 2-seat install">'
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
        await api("POST", "/api/v1/admin/customers", {
          name: name,
          mobile: $("#m-cust-mobile").value || null,
          email: $("#m-cust-email").value || null,
          notes: $("#m-cust-notes").value || null
        });
        hideModal();
        toast("Customer '" + name + "' created successfully.", "ok");
        await refreshAll();
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
      +   '<label>Customer Account *</label>'
      +   '<select id="m-lic-cust">' + opts + '</select>'
      + '</div>'
      + '<div class="form-group">'
      +   '<label>Software Product *</label>'
      +   '<select id="m-lic-prod">'
      +     '<option value="furniture_bill">Furniture Billing Desktop (FB-)</option>'
      +     '<option value="ac_service">AC Service & Maintenance (AC-)</option>'
      +     '<option value="future_product">Future Desktop Application (FP-)</option>'
      +   '</select>'
      + '</div>'
      + '<div class="form-group">'
      +   '<label>License Validity</label>'
      +   '<select id="m-lic-type"><option value="LIFETIME">LIFETIME (Permanent / Offline-First)</option></select>'
      + '</div>'
      + '<div class="form-group">'
      +   '<label>Authorized Device Count (Seats)</label>'
      +   '<input id="m-lic-limit" type="number" min="1" max="20" value="1">'
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
        hideModal();
        const key = d.license.license_key;
        toast("License generated: " + key, "ok");
        await refreshAll();
        switchTab("licenses");
      } catch (e) {
        toast(e.message, "err");
      }
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
        if (key && navigator.clipboard) {
          navigator.clipboard.writeText(key).then(() => {
            toast("Copied license key: " + key, "ok");
          });
        }
        return;
      }
      // Check Row Action Button
      const btn = e.target.closest("[data-act]");
      if (btn) licAction(btn.dataset.act, parseInt(btn.dataset.id));
    });

    // Customer Rows Actions
    $("#customer-rows").addEventListener("click", (e) => {
      const btn = e.target.closest("[data-cust-act]");
      if (btn) custAction(btn.dataset.custAct, parseInt(btn.dataset.id));
    });

    // Modal dismiss on overlay click
    $("#modal-overlay").addEventListener("click", (e) => {
      if (e.target === $("#modal-overlay")) hideModal();
    });
  });
})();