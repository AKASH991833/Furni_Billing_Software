"""End-to-end smoke tests for the license server using an in-memory SQLite DB.

Run:  python -m pytest tests -q
"""
from __future__ import annotations

import hashlib
import os

# Environment must be set before app imports read it.
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["PRIVATE_SIGNING_KEY"] = "LsWRDbrl2SkImDvdZyPkKzLJH62FU1lteNUZ6cc5Y6w="
os.environ["ADMIN_PASSWORD_HASH"] = hashlib.sha256(b"admin123").hexdigest()
os.environ["SECRET_KEY"] = "test-secret-key"

from fastapi.testclient import TestClient

from app.crypto.license_keys import is_valid_format
from app.main import app

PUBLIC_KEY_B64 = "vkecyAMGB6VVw0Rp2Ka8w96YqFgXxZ9dGrBuLj3KLJg="


def _admin_headers(client: TestClient) -> dict[str, str]:
    r = client.post("/admin/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    return {"Authorization": f"Bearer {r.json()['token']}"}


def test_full_license_flow():
    with TestClient(app) as client:
        assert client.get("/").json()["service"] == "furniture-bill-license-server"

        # --- Admin: create customer + license ---
        h = _admin_headers(client)
        r = client.post("/admin/customers", json={"name": "Mahendra Vishwakarma", "mobile": "9876543210"}, headers=h)
        assert r.status_code == 200 and r.json()["success"]
        cust_id = r.json()["customer"]["id"]

        r = client.post("/admin/licenses", json={"customer_id": cust_id, "license_type": "LIFETIME", "device_limit": 1}, headers=h)
        assert r.status_code == 200 and r.json()["success"]
        key = r.json()["license"]["license_key"]
        assert is_valid_format(key), "generated key must match FB-XXXX-XXXX-XXXX"

        # --- Client: activate on device A ---
        r = client.post("/api/activate", json={
            "license_key": key,
            "product": "furniture_bill",
            "app_version": "1.0.0",
            "device_fingerprint": "A" * 64,
        })
        assert r.status_code == 200 and r.json()["success"]
        signed = r.json()
        assert signed["license_data"]["license_key"] == key
        assert signed["signature"]

        # --- Client: verify signature offline with the public key ---
        import base64

        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        pub = Ed25519PublicKey.from_public_bytes(base64.b64decode(PUBLIC_KEY_B64))
        from cryptography.exceptions import InvalidSignature

        # tamper check
        tampered = dict(signed["license_data"])
        tampered["customer_name"] = "HACKER"
        sig_bytes = base64.b64decode(signed["signature"])
        from app.crypto.ed25519 import serialize_payload
        try:
            pub.verify(sig_bytes, serialize_payload(tampered).encode())
            assert False, "tampered payload must NOT verify"
        except InvalidSignature:
            pass  # expected

        # --- Client: re-activate same device (idempotent) ---
        r = client.post("/api/activate", json={
            "license_key": key,
            "product": "furniture_bill",
            "app_version": "1.0.0",
            "device_fingerprint": "A" * 64,
        })
        assert r.status_code == 200 and r.json()["success"]

        # --- Client: device B must be rejected ---
        r = client.post("/api/activate", json={
            "license_key": key,
            "product": "furniture_bill",
            "app_version": "1.0.0",
            "device_fingerprint": "B" * 64,
        })
        assert r.status_code == 200 and not r.json()["success"]

        # --- Admin: deactivate device, then B succeeds ---
        lic_id = signed["license_data"]["license_id"]
        r = client.post(f"/admin/licenses/{lic_id}/deactivate", json={}, headers=h)
        assert r.status_code == 200

        r = client.post("/api/activate", json={
            "license_key": key,
            "product": "furniture_bill",
            "app_version": "1.0.0",
            "device_fingerprint": "B" * 64,
        })
        assert r.status_code == 200 and r.json()["success"]

        # --- Admin: revoke blocks new activations ---
        r = client.put(f"/admin/licenses/{lic_id}/status", json={"status": "REVOKED"}, headers=h)
        assert r.status_code == 200
        r = client.post("/api/activate", json={
            "license_key": key,
            "product": "furniture_bill",
            "app_version": "1.0.0",
            "device_fingerprint": "B" * 64,
        })
        assert r.status_code == 200 and not r.json()["success"]

        # --- Security: admin routes reject bad tokens ---
        r = client.get("/admin/licenses", headers={"Authorization": "Bearer bogus"})
        assert r.status_code == 401


def test_activation_rate_limit():
    client = TestClient(app)
    # bogus key fails fast, but each attempt still counts against the rate limit
    for _ in range(15):
        r = client.post("/api/activate", json={
            "license_key": "FB-AAAA-BBBB-CCCC",  # invalid on purpose
            "product": "furniture_bill",
            "app_version": "1.0.0",
            "device_fingerprint": "F" * 64,
        })
    assert r.status_code == 200 and not r.json()["success"]


def test_generic_error_no_internals():
    with TestClient(app) as client:
        r = client.post("/api/activate", json={
            "license_key": "FB-AAAA-BBBB-CCCC",
            "product": "furniture_bill",
            "app_version": "1.0.0",
            "device_fingerprint": "F" * 64,
        })
        body = r.json()
        assert "Traceback" not in body["message"]
        assert "sqlite" not in body["message"].lower()


def test_client_deactivate_endpoint():
    """Client deactivate: only the bound device may release a license."""
    with TestClient(app) as client:
        h = _admin_headers(client)
        r = client.post("/admin/customers", json={"name": "Deactivate Test"}, headers=h)
        cust_id = r.json()["customer"]["id"]
        r = client.post("/admin/licenses", json={"customer_id": cust_id, "license_type": "LIFETIME"}, headers=h)
        key = r.json()["license"]["license_key"]

        # A third device cannot deactivate (not bound)
        r = client.post("/api/deactivate", json={
            "license_key": key,
            "device_fingerprint": "C" * 64,
        })
        assert r.status_code == 200 and not r.json()["success"]

        # Bound device activates then deactivates
        r = client.post("/api/activate", json={
            "license_key": key, "product": "furniture_bill",
            "app_version": "1.0.0", "device_fingerprint": "D" * 64,
        })
        assert r.json()["success"]

        r = client.post("/api/deactivate", json={
            "license_key": key,
            "device_fingerprint": "D" * 64,
        })
        assert r.status_code == 200 and r.json()["success"]

        # Another device can now activate
        r = client.post("/api/activate", json={
            "license_key": key, "product": "furniture_bill",
            "app_version": "1.0.0", "device_fingerprint": "E" * 64,
        })
        assert r.status_code == 200 and r.json()["success"]


def test_v1_endpoints_and_admin_actions():
    with TestClient(app) as client:
        # Public health endpoint
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "healthy"

        # V1 status
        r = client.get("/api/v1/license/status")
        assert r.status_code == 200
        assert r.json()["status"] == "online"

        # Admin login
        h = _admin_headers(client)

        # Create customer
        r = client.post("/api/v1/admin/customers", json={"name": "V1 Test Corp", "email": "v1@test.com"}, headers=h)
        assert r.status_code == 200
        cust_id = r.json()["customer"]["id"]

        # Create license with product
        r = client.post("/api/v1/admin/licenses", json={"customer_id": cust_id, "product": "furniture_bill"}, headers=h)
        assert r.status_code == 200
        lic = r.json()["license"]
        key = lic["license_key"]
        lic_id = lic["id"]
        assert lic["license_key_hash"] is not None

        # V1 Activate on device 1
        r = client.post("/api/v1/license/activate", json={
            "license_key": key,
            "product": "furniture_bill",
            "device_fingerprint": "1" * 64,
        })
        assert r.status_code == 200 and r.json()["success"]

        # V1 Validate
        r = client.post("/api/v1/license/validate", json={
            "license_key": key,
            "product": "furniture_bill",
            "device_fingerprint": "1" * 64,
        })
        assert r.status_code == 200 and r.json()["valid"]

        # V1 Validate wrong device
        r = client.post("/api/v1/license/validate", json={
            "license_key": key,
            "product": "furniture_bill",
            "device_fingerprint": "2" * 64,
        })
        assert r.status_code == 200 and not r.json()["valid"]

        # V1 Reset Device
        r = client.post(f"/api/v1/admin/licenses/{lic_id}/reset-device", json={"reason": "Customer changed laptop"}, headers=h)
        assert r.status_code == 200
        assert r.json()["license"]["current_device"] is None

        # Device 2 can now activate
        r = client.post("/api/v1/license/activate", json={
            "license_key": key,
            "product": "furniture_bill",
            "device_fingerprint": "2" * 64,
        })
        assert r.status_code == 200 and r.json()["success"]

        # Block license
        r = client.post(f"/api/v1/admin/licenses/{lic_id}/block", json={"reason": "Payment dispute"}, headers=h)
        assert r.status_code == 200
        assert r.json()["license"]["status"] == "BLOCKED"

        # Validation fails when blocked
        r = client.post("/api/v1/license/validate", json={
            "license_key": key,
            "product": "furniture_bill",
            "device_fingerprint": "2" * 64,
        })
        assert r.status_code == 200 and not r.json()["valid"]

        # Reactivate license
        r = client.post(f"/api/v1/admin/licenses/{lic_id}/reactivate", json={"reason": "Payment resolved"}, headers=h)
        assert r.status_code == 200
        assert r.json()["license"]["status"] == "ACTIVE"

        # Revoke license
        r = client.post(f"/api/v1/admin/licenses/{lic_id}/revoke", json={"reason": "Refund issued"}, headers=h)
        assert r.status_code == 200
        assert r.json()["license"]["status"] == "REVOKED"

        # Audit events query
        r = client.get(f"/api/v1/admin/licenses/{lic_id}/events", headers=h)
        assert r.status_code == 200
        events = r.json()["events"]
        actions = [e["action"] for e in events]
        assert "CREATE" in actions
        assert "ACTIVATE" in actions
        assert "RESET_DEVICE" in actions
        assert "BLOCK" in actions
        assert "REACTIVATE" in actions
        assert "REVOKE" in actions


def test_multi_product_support():
    with TestClient(app) as client:
        h = _admin_headers(client)

        r = client.post("/api/v1/admin/customers", json={"name": "Multi Product Customer"}, headers=h)
        cust_id = r.json()["customer"]["id"]

        # Generate AC Service license
        r = client.post("/api/v1/admin/licenses", json={"customer_id": cust_id, "product": "ac_service"}, headers=h)
        ac_key = r.json()["license"]["license_key"]
        assert ac_key.startswith("AC-")

        # Generate Furniture Billing license
        r = client.post("/api/v1/admin/licenses", json={"customer_id": cust_id, "product": "furniture_bill"}, headers=h)
        fb_key = r.json()["license"]["license_key"]
        assert fb_key.startswith("FB-")

        # Attempt activating AC license with Furniture Bill client -> MUST FAIL
        r = client.post("/api/v1/license/activate", json={
            "license_key": ac_key,
            "product": "furniture_bill",
            "device_fingerprint": "M" * 64,
        })
        assert r.status_code == 200 and not r.json()["success"]
        assert "not valid for this product" in r.json()["message"].lower()

        # Attempt activating Furniture license with AC Service client -> MUST FAIL
        r = client.post("/api/v1/license/activate", json={
            "license_key": fb_key,
            "product": "ac_service",
            "device_fingerprint": "M" * 64,
        })
        assert r.status_code == 200 and not r.json()["success"]
        assert "not valid for this product" in r.json()["message"].lower()

        # Activating AC license with AC Service client -> MUST SUCCEED
        r = client.post("/api/v1/license/activate", json={
            "license_key": ac_key,
            "product": "ac_service",
            "device_fingerprint": "M" * 64,
        })
        assert r.status_code == 200 and r.json()["success"]

        # Activating FB license with Furniture client on different device -> MUST SUCCEED
        r = client.post("/api/v1/license/activate", json={
            "license_key": fb_key,
            "product": "furniture_bill",
            "device_fingerprint": "N" * 64,
        })
        assert r.status_code == 200 and r.json()["success"]