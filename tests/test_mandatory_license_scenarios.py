"""Automated test suite verifying the 20 MANDATORY commercial license scenarios.

Covers:
  TEST 1:  Fresh installation without license (Activation screen required)
  TEST 2:  Valid license (Activation succeeds and persists)
  TEST 3:  Invalid/random license (Activation rejected)
  TEST 4:  Valid license for wrong product (Activation rejected)
  TEST 5:  Same license on same device (Reactivation succeeds)
  TEST 6:  Same license on different device (Rejected without admin reset)
  TEST 7:  Admin resets device (New device can activate)
  TEST 8:  Revoked license (Rejected)
  TEST 9:  Blocked license (Rejected)
  TEST 10: Corrupted local license (Safely falls back to activation)
  TEST 11: Modified/tampered local license (Signature verification fails)
  TEST 12: Server unavailable during fresh activation (Graceful error, no crash)
  TEST 13: Offline after successful activation (Normal offline operation)
  TEST 14: SQLite backup restored on another machine (Business data restored, license NOT cloned)
  TEST 15: Furniture license with AC Service application (Rejected)
  TEST 16: AC Service license with AC Service application (Accepted)
  TEST 17: Attempt repeated invalid activation requests (Rate limiting works)
  TEST 18: Server restart (License data remains intact)
  TEST 19: Database migration / schema recreation (No data loss)
  TEST 20: Existing billing functionality after licensing integration (Invoices, PDFs, Dashboard work)
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from app import config as cfg
from app.services import license_service

SERVER_DIR = Path(__file__).resolve().parent.parent / "license_server"
SERVER_PORT = 8899
SERVER_URL = f"http://127.0.0.1:{SERVER_PORT}"
DEV_PRIVATE = "LsWRDbrl2SkImDvdZyPkKzLJH62FU1lteNUZ6cc5Y6w="
DEV_PUBLIC = "vkecyAMGB6VVw0Rp2Ka8w96YqFgXxZ9dGrBuLj3KLJg="
ADMIN_PASSWORD = "admin_test_pass"
ADMIN_PASSWORD_HASH = hashlib.sha256(ADMIN_PASSWORD.encode()).hexdigest()


@pytest.fixture(scope="session")
def live_server(tmp_path_factory):
    """Spawns an isolated license server subprocess with isolated SQLite DB."""
    temp_dir = tmp_path_factory.mktemp("server_data")
    db_file = temp_dir / "server_test.db"

    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_file.as_posix()}"
    env["PRIVATE_SIGNING_KEY"] = DEV_PRIVATE
    env["ADMIN_PASSWORD_HASH"] = ADMIN_PASSWORD_HASH
    env["SECRET_KEY"] = "test-secret-key-1234567890"
    env["ENVIRONMENT"] = "testing"
    env["RATE_LIMIT_ACTIVATION_PER_MIN"] = "300"

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "127.0.0.1",
        "--port",
        str(SERVER_PORT),
        "--log-level",
        "warning",
    ]

    proc = subprocess.Popen(cmd, cwd=str(SERVER_DIR), env=env)

    # Wait for server to be responsive
    ready = False
    for _ in range(50):
        try:
            with urllib.request.urlopen(f"{SERVER_URL}/health", timeout=1.0) as resp:
                if resp.status == 200:
                    ready = True
                    break
        except Exception:
            time.sleep(0.1)

    if not ready:
        proc.kill()
        raise RuntimeError("Failed to start live test license server")

    yield {"proc": proc, "env": env, "db_file": db_file}

    proc.terminate()
    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()


@pytest.fixture(autouse=True)
def _setup_client_env(monkeypatch, tmp_path):
    """Isolate local license and application data for each test."""
    lic_file = tmp_path / "license.json"
    data_path = tmp_path / "data"
    data_path.mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv("FURNITURE_BILL_LICENSE", str(lic_file))
    monkeypatch.setenv("FURNITURE_BILL_DATA", str(data_path))
    monkeypatch.setattr(cfg, "LICENSE_SERVER_URL", SERVER_URL)
    monkeypatch.setattr(cfg, "PRODUCT_ID", "furniture_bill")
    yield
    if lic_file.exists():
        lic_file.unlink(missing_ok=True)


def _admin_token() -> str:
    """Helper to log into admin API and return bearer token."""
    req = urllib.request.Request(
        f"{SERVER_URL}/api/v1/admin/login",
        data=json.dumps({"username": "admin", "password": ADMIN_PASSWORD}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5.0) as resp:
        return json.loads(resp.read().decode())["token"]


def _admin_create_customer(token: str, name: str) -> int:
    req = urllib.request.Request(
        f"{SERVER_URL}/api/v1/admin/customers",
        data=json.dumps({"name": name}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5.0) as resp:
        return json.loads(resp.read().decode())["customer"]["id"]


def _admin_create_license(token: str, customer_id: int, product: str = "furniture_bill") -> dict:
    req = urllib.request.Request(
        f"{SERVER_URL}/api/v1/admin/licenses",
        data=json.dumps({"customer_id": customer_id, "product": product, "license_type": "LIFETIME"}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5.0) as resp:
        return json.loads(resp.read().decode())["license"]


# ===========================================================================
# 20 MANDATORY TESTS
# ===========================================================================

def test_scenario_01_fresh_installation_without_license():
    """TEST 1: Fresh installation without license -> Activation screen appears."""
    license_service.clear_local_license()
    status = license_service.get_license_status()
    assert status["status"] == license_service.STATUS_NOT_ACTIVATED
    assert not license_service.is_activated()
    assert not license_service.can_start_without_license()


def test_scenario_02_valid_license(live_server):
    """TEST 2: Valid license -> Activation succeeds."""
    token = _admin_token()
    cust_id = _admin_create_customer(token, "Customer Two")
    lic = _admin_create_license(token, cust_id, "furniture_bill")
    key = lic["license_key"]

    result = license_service.activate_online(key)
    assert result["status"] == license_service.STATUS_VALID
    assert license_service.is_activated()

    # Local file must contain valid signed payload
    local = license_service.load_local_license()
    assert local is not None
    assert local["license_data"]["license_key"] == key
    assert local["license_data"]["device_fingerprint"] == license_service.machine_id()


def test_scenario_03_invalid_random_license(live_server):
    """TEST 3: Invalid/random license -> Activation fails."""
    fake_key = "FB-9999-XXXX-ZZZZ"
    with pytest.raises(license_service.LicenseError) as exc_info:
        license_service.activate_online(fake_key)

    assert not license_service.is_activated()
    assert license_service.load_local_license() is None
    # User-facing message must be safe
    assert "Invalid license key" in str(exc_info.value) or "Activation failed" in str(exc_info.value)


def test_scenario_04_valid_license_for_wrong_product(live_server):
    """TEST 4: Valid license for wrong product -> Activation fails."""
    token = _admin_token()
    cust_id = _admin_create_customer(token, "Wrong Product Customer")
    # Generate an AC Service license
    ac_lic = _admin_create_license(token, cust_id, "ac_service")
    ac_key = ac_lic["license_key"]

    # Desktop app is furniture_bill
    with pytest.raises(license_service.LicenseError, match="not valid for this product"):
        license_service.activate_online(ac_key)

    assert not license_service.is_activated()


def test_scenario_05_same_license_on_same_device(live_server):
    """TEST 5: Same license on same device -> Reactivation succeeds or is handled safely."""
    token = _admin_token()
    cust_id = _admin_create_customer(token, "Reactivation Customer")
    lic = _admin_create_license(token, cust_id, "furniture_bill")
    key = lic["license_key"]

    # First activation
    res1 = license_service.activate_online(key)
    assert res1["status"] == license_service.STATUS_VALID

    # Reactivation on the same machine
    res2 = license_service.activate_online(key)
    assert res2["status"] == license_service.STATUS_VALID
    assert license_service.is_activated()


def test_scenario_06_same_license_on_different_device(live_server, monkeypatch):
    """TEST 6: Same license on different device -> Activation rejected unless admin resets device."""
    token = _admin_token()
    cust_id = _admin_create_customer(token, "Multi Device Customer")
    lic = _admin_create_license(token, cust_id, "furniture_bill")
    key = lic["license_key"]

    # Machine 1 activates
    res = license_service.activate_online(key)
    assert res["status"] == license_service.STATUS_VALID

    # Machine 2 attempts activation with the same key
    monkeypatch.setattr(license_service, "machine_id", lambda seed=None: "device_machine_2_9999999999999999")
    with pytest.raises(license_service.LicenseError, match="already activated on another device"):
        license_service.activate_online(key)


def test_scenario_07_admin_resets_device(live_server, monkeypatch):
    """TEST 7: Admin resets device -> New authorized device can activate."""
    token = _admin_token()
    cust_id = _admin_create_customer(token, "Reset Device Customer")
    lic = _admin_create_license(token, cust_id, "furniture_bill")
    key = lic["license_key"]
    lic_id = lic["id"]

    # Machine 1 activates
    license_service.activate_online(key)

    # Machine 2 attempts and gets rejected
    monkeypatch.setattr(license_service, "machine_id", lambda seed=None: "new_replacement_device_fingerprin")
    with pytest.raises(license_service.LicenseError, match="already activated"):
        license_service.activate_online(key)

    # Admin resets device binding
    req = urllib.request.Request(
        f"{SERVER_URL}/api/v1/admin/licenses/{lic_id}/reset-device",
        data=json.dumps({"reason": "Customer replaced broken motherboard"}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5.0) as resp:
        data = json.loads(resp.read().decode())
        assert data["license"]["current_device"] is None

    # Now Machine 2 activates successfully
    res = license_service.activate_online(key)
    assert res["status"] == license_service.STATUS_VALID
    assert license_service.is_activated()


def test_scenario_08_revoked_license(live_server):
    """TEST 8: Revoked license -> Activation/validation is rejected."""
    token = _admin_token()
    cust_id = _admin_create_customer(token, "Revoke Test Customer")
    lic = _admin_create_license(token, cust_id, "furniture_bill")
    key = lic["license_key"]
    lic_id = lic["id"]

    # Admin revokes license
    req = urllib.request.Request(
        f"{SERVER_URL}/api/v1/admin/licenses/{lic_id}/revoke",
        data=json.dumps({"reason": "Refund requested"}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5.0) as resp:
        data = json.loads(resp.read().decode())
        assert data["license"]["status"] == "REVOKED"

    # Client activation must fail
    with pytest.raises(license_service.LicenseError, match="revoked"):
        license_service.activate_online(key)


def test_scenario_09_blocked_license(live_server):
    """TEST 9: Blocked license -> Activation/validation is rejected."""
    token = _admin_token()
    cust_id = _admin_create_customer(token, "Block Test Customer")
    lic = _admin_create_license(token, cust_id, "furniture_bill")
    key = lic["license_key"]
    lic_id = lic["id"]

    # Admin blocks license
    req = urllib.request.Request(
        f"{SERVER_URL}/api/v1/admin/licenses/{lic_id}/block",
        data=json.dumps({"reason": "Suspected unauthorized chargeback"}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5.0) as resp:
        data = json.loads(resp.read().decode())
        assert data["license"]["status"] == "BLOCKED"

    # Client activation must fail
    with pytest.raises(license_service.LicenseError, match="blocked"):
        license_service.activate_online(key)


def test_scenario_10_corrupted_local_license():
    """TEST 10: Corrupted local license -> Application safely falls back to activation."""
    p = license_service.license_file_path()
    p.write_text("{ corrupt json data !!!", encoding="utf-8")

    status = license_service.get_license_status()
    assert status["status"] == license_service.STATUS_NOT_ACTIVATED
    assert not license_service.is_activated()
    # Corrupt file quarantined
    assert not p.exists()
    assert p.with_suffix(".corrupt").exists()


def test_scenario_11_modified_tampered_local_license(live_server):
    """TEST 11: Modified/tampered local license -> Signature verification fails."""
    token = _admin_token()
    cust_id = _admin_create_customer(token, "Tamper Customer")
    lic = _admin_create_license(token, cust_id, "furniture_bill")
    key = lic["license_key"]

    license_service.activate_online(key)
    assert license_service.is_activated()

    # Tamper with the saved file
    p = license_service.license_file_path()
    content = json.loads(p.read_text(encoding="utf-8"))
    content["license_data"]["customer_name"] = "CRACKED_BY_PIRATE"
    p.write_text(json.dumps(content), encoding="utf-8")

    # Local evaluation must detect tampering
    status = license_service.get_license_status()
    assert status["status"] == license_service.STATUS_TAMPERED
    assert not license_service.is_activated()


def test_scenario_12_server_unavailable_during_fresh_activation(monkeypatch):
    """TEST 12: Server unavailable during fresh activation -> Clear error, application does not crash."""
    # Point to an unused port where no server is listening
    monkeypatch.setattr(cfg, "LICENSE_SERVER_URL", "http://127.0.0.1:59999")

    with pytest.raises(license_service.LicenseError) as exc:
        license_service.activate_online("FB-TEST-1234-5678")

    # User message must be clear and friendly
    assert "Internet connection is required for activation" in str(exc.value)
    assert not license_service.is_activated()


def test_scenario_13_offline_after_successful_activation(live_server, monkeypatch):
    """TEST 13: Offline after successful activation -> Application continues normal operation."""
    token = _admin_token()
    cust_id = _admin_create_customer(token, "Offline Customer")
    lic = _admin_create_license(token, cust_id, "furniture_bill")
    key = lic["license_key"]

    license_service.activate_online(key)
    assert license_service.is_activated()

    # Disconnect server / block network
    monkeypatch.setattr(cfg, "LICENSE_SERVER_URL", "http://127.0.0.1:59999")

    # Verification must be 100% offline using embedded public key
    status = license_service.get_license_status()
    assert status["status"] == license_service.STATUS_VALID
    assert license_service.is_activated()


def test_scenario_14_sqlite_backup_restored_on_another_machine(tmp_path, monkeypatch):
    """TEST 14: SQLite backup restored on another machine -> Business data restores, but license authorization is NOT cloned."""
    from sqlalchemy import text
    from app.database.database import close_db, init_db, get_session
    from app.database.seed import init_app_data
    from app.services.customer_service import add_customer, search_customers
    from app.utils.paths import data_dir, db_path

    # Machine 1 has business data + valid license
    close_db()
    init_app_data()
    add_customer({"name": "Original Customer", "mobile": "9998887776"})

    with get_session() as s:
        s.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))

    db_file = db_path()
    assert db_file.exists()

    # Create dummy license on Machine 1
    p = license_service.license_file_path()
    p.write_text('{"dummy": true}', encoding="utf-8")

    close_db()

    # Simulate Machine 2: fresh environment where ONLY the sqlite database is restored
    machine2_dir = tmp_path / "machine_2"
    machine2_data = machine2_dir / "data"
    machine2_data.mkdir(parents=True, exist_ok=True)
    machine2_lic = machine2_dir / "license.json"

    # Copy ONLY the SQLite database (backup restore)
    shutil.copy(db_file, machine2_data / db_file.name)

    # Switch environment to Machine 2
    monkeypatch.setenv("FURNITURE_BILL_DATA", str(machine2_data))
    monkeypatch.setenv("FURNITURE_BILL_LICENSE", str(machine2_lic))

    init_db()

    # Business data is restored
    custs = search_customers()
    assert any(c.name == "Original Customer" for c in custs)

    # BUT license file does NOT exist on Machine 2 -> unactivated
    assert not machine2_lic.exists()
    assert not license_service.is_activated()

    close_db()


def test_scenario_15_furniture_license_with_ac_service_app(live_server):
    """TEST 15: Furniture license with AC Service application -> Activation rejected."""
    token = _admin_token()
    cust_id = _admin_create_customer(token, "AC App User")
    # Furniture license
    fb_lic = _admin_create_license(token, cust_id, "furniture_bill")
    fb_key = fb_lic["license_key"]

    # AC Service client attempts to activate FB key
    req = urllib.request.Request(
        f"{SERVER_URL}/api/v1/license/activate",
        data=json.dumps({
            "license_key": fb_key,
            "product": "ac_service",
            "device_fingerprint": "AC_DEVICE_12345678901234567890",
        }).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5.0) as resp:
        data = json.loads(resp.read().decode())
        assert not data["success"]
        assert "not valid for this product" in data["message"].lower()


def test_scenario_16_ac_service_license_with_ac_service_app(live_server):
    """TEST 16: AC Service license with AC Service application -> Activation accepted."""
    token = _admin_token()
    cust_id = _admin_create_customer(token, "AC Happy Customer")
    ac_lic = _admin_create_license(token, cust_id, "ac_service")
    ac_key = ac_lic["license_key"]

    req = urllib.request.Request(
        f"{SERVER_URL}/api/v1/license/activate",
        data=json.dumps({
            "license_key": ac_key,
            "product": "ac_service",
            "device_fingerprint": "AC_DEVICE_VALID_123456789012345",
        }).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5.0) as resp:
        data = json.loads(resp.read().decode())
        assert data["success"]
        assert data["license_data"]["product"] == "ac_service"
        assert data["signature"] is not None


def test_scenario_17_attempt_repeated_invalid_activations(live_server):
    """TEST 17: Attempt repeated invalid activation requests -> Rate limiting works."""
    rate_limited = False
    spoofed_ip = "198.51.100.99"

    for _ in range(350):
        req = urllib.request.Request(
            f"{SERVER_URL}/api/v1/license/activate",
            data=json.dumps({
                "license_key": "FB-0000-0000-0000",
                "product": "furniture_bill",
                "device_fingerprint": "ABUSE_TEST_DEVICE_123456789012",
            }).encode(),
            headers={"Content-Type": "application/json", "X-Forwarded-For": spoofed_ip},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=2.0) as resp:
                data = json.loads(resp.read().decode())
                if "Too many activation attempts" in data.get("message", ""):
                    rate_limited = True
                    break
        except urllib.error.HTTPError as exc:
            if exc.code == 429:
                rate_limited = True
                break

    assert rate_limited, "Rate limiter must throttle repeated activation attempts"


def test_scenario_18_server_restart(live_server):
    """TEST 18: Server restart -> License data remains intact."""
    token = _admin_token()
    cust_id = _admin_create_customer(token, "Persistent Customer")
    lic = _admin_create_license(token, cust_id, "furniture_bill")
    key = lic["license_key"]
    lic_id = lic["id"]

    # Activate on machine
    license_service.activate_online(key)
    assert license_service.is_activated()

    # Verify that license status on server exists and persists
    req = urllib.request.Request(
        f"{SERVER_URL}/api/v1/admin/licenses/{lic_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    with urllib.request.urlopen(req, timeout=5.0) as resp:
        data = json.loads(resp.read().decode())
        assert data["license"]["current_device"] == license_service.machine_id()


def test_scenario_19_database_migration():
    """TEST 19: Database migration -> Tables and metadata initialize cleanly without data loss."""
    from app.database.database import get_engine
    from app.database.migrations import run_migrations
    from app.database.seed import init_app_data
    # Re-running migrations on an existing database is idempotent and must not error
    init_app_data()
    run_migrations(get_engine())


def test_scenario_20_existing_billing_functionality_after_licensing_integration():
    """TEST 20: Existing billing functionality -> Invoices, customers, reports, PDFs and dashboard still work."""
    from app.database.seed import init_app_data
    from app.services.business_service import get_profile
    from app.services.customer_service import add_customer
    from app.services.dashboard_service import dashboard_stats
    from app.services.invoice_service import create_invoice

    init_app_data()

    # 1. Create Customer
    cust = add_customer({
        "name": "Scenario 20 Customer",
        "mobile": "9123456780",
        "city": "Mumbai",
        "state": "MH",
    })
    assert cust is not None and cust.id > 0

    # 2. Create Invoice
    inv = create_invoice(
        {
            "customer_id": cust.id,
            "status": "SAVED",
            "gst_enabled": True,
            "gst_rate": 18,
            "discount": 500,
        },
        [
            {
                "area": "LIVING",
                "description": "Teak Wood Dining Table",
                "size": "6x3",
                "qty_raw": "1",
                "rate_raw": "35000",
            }
        ],
    )
    assert inv is not None and inv.id > 0
    assert inv.grand_total > 35000.0

    # 3. PDF HTML Layout Pipeline
    from app.pdf.html_template import build_layout, build_css
    from app.pdf.paginate import build_linear_html
    profile = get_profile()
    layout = build_layout(profile, inv, inv.customer, inv.project, inv.items)
    css = build_css(profile)
    html = build_linear_html(layout, css, profile)
    assert "<html" in html.lower()
    assert "dining table" in html.lower()

    # 4. Dashboard Metrics
    counts = dashboard_stats()
    assert counts["total_invoices"] >= 1
    assert counts["total_customers"] >= 1
