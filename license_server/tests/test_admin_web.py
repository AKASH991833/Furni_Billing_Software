"""Smoke-test for the admin web tool SPA."""
from __future__ import annotations

import hashlib
import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["PRIVATE_SIGNING_KEY"] = "LsWRDbrl2SkImDvdZyPkKzLJH62FU1lteNUZ6cc5Y6w="
os.environ["ADMIN_PASSWORD_HASH"] = hashlib.sha256(b"admin123").hexdigest()
os.environ["SECRET_KEY"] = "test-secret-key"

from fastapi.testclient import TestClient

from admin_web.main import app


def test_homepage_serves_index_html():
    c = TestClient(app)
    r = c.get("/")
    assert r.status_code == 200
    assert "License Admin" in r.text
    assert "/app.js" in r.text


def test_admin_login_and_customer_crud():
    c = TestClient(app)
    # login
    r = c.post("/admin/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    token = r.json()["token"]
    h = {"Authorization": f"Bearer {token}"}

    # create customer
    r = c.post("/admin/customers", json={"name": "Test User", "mobile": "9999999999"}, headers=h)
    assert r.status_code == 200 and r.json()["success"]

    # list customers
    r = c.get("/admin/customers", headers=h)
    assert r.status_code == 200
    assert r.json()["customers"][0]["name"] == "Test User"

    # create license
    cid = r.json()["customers"][0]["id"]
    r = c.post("/admin/licenses", json={"customer_id": cid, "license_type": "LIFETIME"}, headers=h)
    assert r.status_code == 200
    key = r.json()["license"]["license_key"]

    # activate on device A
    r = c.post("/api/activate", json={
        "license_key": key,
        "product": "furniture_bill",
        "app_version": "1.0.0",
        "device_fingerprint": "X" * 64,
    })
    assert r.json()["success"]

    # list licenses shows the active device
    r = c.get("/admin/licenses", headers=h)
    assert any(l["current_device"] for l in r.json()["licenses"])

    # revoke
    lid = r.json()["licenses"][0]["id"]
    r = c.put(f"/admin/licenses/{lid}/status", json={"status": "REVOKED"}, headers=h)
    assert r.status_code == 200 and r.json()["license"]["status"] == "REVOKED"

    # update customer
    r = c.put(f"/admin/customers/{cid}", json={"name": "Updated User", "mobile": "8888888888", "email": "up@ex.com", "notes": "VIP"}, headers=h)
    assert r.status_code == 200
    assert r.json()["customer"]["name"] == "Updated User"

    # delete license
    r = c.delete(f"/admin/licenses/{lid}", headers=h)
    assert r.status_code == 200
    assert r.json()["success"]

    # delete customer
    r = c.delete(f"/admin/customers/{cid}", headers=h)
    assert r.status_code == 200
    assert r.json()["success"]


def test_admin_password_change_flow():
    c = TestClient(app)
    # 1. Login with initial password
    r = c.post("/admin/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 200
    token = r.json()["token"]
    h = {"Authorization": f"Bearer {token}"}

    # 2. Try changing with wrong current password
    r = c.post("/admin/change-password", json={"current_password": "wrongpassword", "new_password": "newpassword123"}, headers=h)
    assert r.status_code == 400

    # 3. Change password successfully
    r = c.post("/admin/change-password", json={"current_password": "admin123", "new_password": "newpassword123"}, headers=h)
    assert r.status_code == 200
    assert r.json()["success"]

    # 4. Try login with old password (must fail)
    r = c.post("/admin/login", json={"username": "admin", "password": "admin123"})
    assert r.status_code == 401

    # 5. Login with new password (must succeed)
    r = c.post("/admin/login", json={"username": "admin", "password": "newpassword123"})
    assert r.status_code == 200
    assert "token" in r.json()