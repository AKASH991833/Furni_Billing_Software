"""Unit and Integration Tests for Universal Multi-Product Software Licensing and Bank-Grade Security."""
import os
import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

# Ensure license_server is in sys.path
BASE_DIR = Path(__file__).resolve().parent.parent / "license_server"
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Use in-memory SQLite for test isolation
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["PRIVATE_SIGNING_KEY"] = "LsWRDbrl2SkImDvdZyPkKzLJH62FU1lteNUZ6cc5Y6w="
os.environ["ADMIN_USERNAME"] = "admin"
os.environ["ADMIN_PASSWORD_HASH"] = "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9"  # sha256 of 'admin123'
os.environ["RATE_LIMIT_ACTIVATION_PER_MIN"] = "100"

from app.main import app
from app.models.database import close_db, get_session, init_db
from app.services.license_service import (
    clear_failed_logins,
    create_customer,
    create_license,
    create_product,
    is_ip_locked,
    list_products,
    record_failed_login,
    update_product,
    verify_admin_credentials,
)


@pytest.fixture(autouse=True)
def setup_test_db():
    init_db()
    yield
    close_db()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_token(client):
    res = client.post("/api/v1/admin/login", json={"username": "admin", "password": "admin123"})
    assert res.status_code == 200, res.text
    return res.json()["token"]


def test_default_products_auto_seeded():
    """Verify that default products (furniture_bill, ac_service, general_billing) are seeded."""
    products = list_products()
    codes = {p["code"] for p in products}
    assert "furniture_bill" in codes
    assert "ac_service" in codes
    assert "general_billing" in codes


def test_create_and_manage_new_software_product(auth_token, client):
    """Admin can register any custom software product with custom prefix."""
    # 1. Register HVAC software
    res = client.post(
        "/api/v1/admin/products",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "name": "HVAC Repair & Maintenance Pro",
            "code": "hvac_pro",
            "prefix": "HVAC",
            "description": "Commercial HVAC software suite",
            "default_device_limit": 2,
        },
    )
    assert res.status_code == 200
    prod = res.json()["product"]
    assert prod["prefix"] == "HVAC"
    assert prod["code"] == "hvac_pro"

    # 2. Issue a license for this new product
    cust_res = client.post(
        "/api/v1/admin/customers",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"name": "Cool Air Services", "mobile": "9876543210"},
    )
    assert cust_res.status_code == 200
    cid = cust_res.json()["customer"]["id"]

    lic_res = client.post(
        "/api/v1/admin/licenses",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={
            "customer_id": cid,
            "product": "hvac_pro",
            "license_type": "LIFETIME",
            "device_limit": 2,
        },
    )
    assert lic_res.status_code == 200
    key = lic_res.json()["license"]["license_key"]
    # Must start with HVAC- and have 3 groups of 4 chars
    assert key.startswith("HVAC-")
    parts = key.split("-")
    assert len(parts) == 4
    for p in parts[1:]:
        assert len(p) == 4

    # 3. Activate the new product license from client
    act_res = client.post(
        "/api/v1/license/activate",
        json={
            "license_key": key,
            "product": "hvac_pro",
            "app_version": "2.0.0",
            "device_fingerprint": "abc123def45678901234567890123456",
            "device_label": "Technician Laptop 1",
        },
    )
    assert act_res.status_code == 200
    act_data = act_res.json()
    assert act_data["success"] is True
    assert act_data["signature"] is not None
    assert act_data["license_data"]["product"] == "hvac_pro"


def test_ip_brute_force_lockout():
    """Verify that repeated failed logins lock out the attacker IP."""
    test_ip = "198.51.100.25"
    clear_failed_logins(test_ip)
    assert not is_ip_locked(test_ip)

    # 4 failed attempts: not locked yet
    for _ in range(4):
        ok, _ = verify_admin_credentials("admin", "wrong_password", client_ip=test_ip)
        assert ok is False

    assert not is_ip_locked(test_ip)

    # 5th failed attempt: triggers lockout
    ok, _ = verify_admin_credentials("admin", "wrong_password", client_ip=test_ip)
    assert ok is False
    assert is_ip_locked(test_ip)

    # Subsequent attempt blocked with security lockout
    ok, msg = verify_admin_credentials("admin", "admin123", client_ip=test_ip)
    assert ok is False
    assert "Security Lockout" in msg

    # Clear lockout
    clear_failed_logins(test_ip)
    assert not is_ip_locked(test_ip)
    ok, msg = verify_admin_credentials("admin", "admin123", client_ip=test_ip)
    assert ok is True


def test_security_headers_middleware(client):
    """Verify standard security headers are injected into all HTTP responses."""
    res = client.get("/admin/health")
    assert res.status_code == 200
    assert res.headers.get("x-frame-options") == "SAMEORIGIN"
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert "strict-origin-when-cross-origin" in res.headers.get("referrer-policy", "")
    assert "default-src 'self'" in res.headers.get("content-security-policy", "")


def test_password_change_invalidates_all_tokens(client, auth_token):
    """When the admin password is changed, old sessions are immediately revoked."""
    # 1. Old token works
    res1 = client.get("/api/v1/admin/products", headers={"Authorization": f"Bearer {auth_token}"})
    assert res1.status_code == 200

    # 2. Change password
    chg_res = client.post(
        "/api/v1/admin/change-password",
        headers={"Authorization": f"Bearer {auth_token}"},
        json={"current_password": "admin123", "new_password": "new_super_secret_password_2026"},
    )
    assert chg_res.status_code == 200

    # 3. Old token is now invalid (401 Unauthorized)
    res2 = client.get("/api/v1/admin/products", headers={"Authorization": f"Bearer {auth_token}"})
    assert res2.status_code == 401
