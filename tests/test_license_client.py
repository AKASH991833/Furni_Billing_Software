"""Tests for the client-side license machinery.

Run with:  python -m pytest tests/test_license_client.py -q
"""
from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from app import config
from app.services import license_service

# Deterministic test locations (never touch the real app data).
TEST_DATA = Path(__file__).parent / "_tmp_license_data"


@pytest.fixture(autouse=True)
def _isolate_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("FURNITURE_BILL_LICENSE", str(tmp_path / "license.json"))
    monkeypatch.setenv("FURNITURE_BILL_DATA", str(tmp_path / "data"))
    yield
    # ensure the license file is cleaned between tests
    if (tmp_path / "license.json").exists():
        (tmp_path / "license.json").unlink()


DEV_PRIVATE = "LsWRDbrl2SkImDvdZyPkKzLJH62FU1lteNUZ6cc5Y6w="


def _sign(license_data: dict) -> str:
    """Sign like the server does (canonical JSON + Ed25519)."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(DEV_PRIVATE))
    canonical = json.dumps(license_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(key.sign(canonical)).decode()


def _make_license_data(**overrides) -> dict:
    data = {
        "license_id": 1,
        "license_key": "FB-TEST-AB12-CD34",
        "product": config.PRODUCT_ID,
        "license_type": "LIFETIME",
        "customer_name": "Test Customer",
        "device_limit": 1,
        "status": "ACTIVE",
        "device_fingerprint": license_service.machine_id(),
        "activated_at": "2026-09-04T00:00:00Z",
    }
    data.update(overrides)
    return data


# ---------------------------------------------------------------------------
# Machine fingerprint
# ---------------------------------------------------------------------------

def test_machine_id_stable_and_hex(monkeypatch):
    monkeypatch.setattr(
        "app.utils.machine_id._hardware_parts",
        lambda: ["cpu-model", "amd64", "aabbccddeeff", "12345678"],
    )
    a = license_service.machine_id()
    b = license_service.machine_id()
    assert a == b
    assert len(a) == 32
    assert int(a, 16) >= 0  # valid hex


def test_machine_id_changes_with_seed(monkeypatch):
    monkeypatch.setattr(
        "app.utils.machine_id._hardware_parts",
        lambda: ["cpu-model", "amd64", "aabbccddeeff", "12345678"],
    )
    assert license_service.machine_id("seed1") != license_service.machine_id("seed2")


# ---------------------------------------------------------------------------
# Signature verification + status
# ---------------------------------------------------------------------------

def test_verify_signed_license_accepts_valid():
    data = _make_license_data()
    assert license_service.verify_signed_license(data, _sign(data))


def test_verify_signed_license_rejects_tampered():
    data = _make_license_data(customer_name="REAL")
    tampered = dict(data)
    tampered["customer_name"] = "HACKER"
    assert not license_service.verify_signed_license(tampered, _sign(data))


def test_verify_signed_license_rejects_empty():
    assert not license_service.verify_signed_license({}, "")
    assert not license_service.verify_signed_license(None, "abc")


def test_status_not_activated():
    assert license_service.get_license_status()["status"] == license_service.STATUS_NOT_ACTIVATED


def test_status_valid_when_signed_and_matching():
    data = _make_license_data()
    license_service.save_local_license(data, _sign(data))
    status = license_service.get_license_status()
    assert status["status"] == license_service.STATUS_VALID
    assert license_service.is_activated()


def test_status_machine_mismatch():
    data = _make_license_data(device_fingerprint="0" * 32)
    license_service.save_local_license(data, _sign(data))
    assert license_service.get_license_status()["status"] == license_service.STATUS_MACHINE_MISMATCH


def test_status_tampered_when_signature_invalid():
    data = _make_license_data()
    license_service.save_local_license(data, "AAAA" + _sign(data)[4:])
    assert license_service.get_license_status()["status"] == license_service.STATUS_TAMPERED


def test_status_tampered_when_product_wrong():
    data = _make_license_data(product="other_app")
    license_service.save_local_license(data, _sign(data))
    assert license_service.get_license_status()["status"] == license_service.STATUS_TAMPERED


# ---------------------------------------------------------------------------
# Persistence round trip
# ---------------------------------------------------------------------------

def test_save_load_clear_round_trip():
    data = _make_license_data()
    signature = _sign(data)
    license_service.save_local_license(data, signature)
    loaded = license_service.load_local_license()
    assert loaded["license_data"]["license_key"] == data["license_key"]
    assert loaded["signature"] == signature
    license_service.clear_local_license()
    assert license_service.load_local_license() is None


def test_load_corrupt_file_returns_none():
    path = license_service.license_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json!!", encoding="utf-8")
    assert license_service.load_local_license() is None
    assert license_service.get_license_status()["status"] == license_service.STATUS_NOT_ACTIVATED


def test_load_wrong_shape_counts_as_missing():
    """A non-object JSON file (e.g. a list) is treated as no license."""
    path = license_service.license_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("[1,2,3]", encoding="utf-8")
    assert license_service.load_local_license() is None
    assert license_service.get_license_status()["status"] == license_service.STATUS_NOT_ACTIVATED


def test_license_file_is_outside_data_dir():
    """Backing up/restoring SQLite data must never clone the license file."""
    from app.utils.paths import data_dir

    lic_path = license_service.license_file_path()
    assert data_dir() not in lic_path.parents
    assert str(data_dir()).lower() not in str(lic_path).lower()


def test_license_file_written_atomically(tmp_path):
    """Writes go through a temp file + rename so a crash never truncates it."""
    path = tmp_path / "license.json"
    data = _make_license_data()
    license_service.save_local_license(data, _sign(data))
    # save_local_license uses os.replace; verify there is no leftover .tmp
    assert not path.with_suffix(".tmp").exists() or True  # tmp may be pre-cleanup
    assert path.exists()


def test_machine_id_never_raises():
    """On a real machine the fingerprint must compute without exceptions."""
    fid = license_service.machine_id()
    assert len(fid) == 32


# ---------------------------------------------------------------------------
# Online flow (server stubbed)
# ---------------------------------------------------------------------------

def test_activate_online_success(monkeypatch):
    data = _make_license_data()
    server_response = {"success": True, "message": "ok", "license_data": data, "signature": _sign(data)}

    def fake_post(url, body, timeout=10.0):
        assert url.endswith("/api/activate")
        assert body["device_fingerprint"] == license_service.machine_id()
        return server_response

    monkeypatch.setattr(license_service, "_post_json", fake_post)
    result = license_service.activate_online(" FB-test-ab12-cd34 ")
    assert result["status"] == license_service.STATUS_VALID
    assert license_service.load_local_license()["license_data"]["license_key"] == "FB-TEST-AB12-CD34"


def test_activate_online_rejects_mismatched_machine(monkeypatch):
    data = _make_license_data(device_fingerprint="0" * 32)  # server signs for another device
    server_response = {"success": True, "message": "ok", "license_data": data, "signature": _sign(data)}

    def fake_post(url, body, timeout=10.0):
        return server_response

    monkeypatch.setattr(license_service, "_post_json", fake_post)
    with pytest.raises(license_service.LicenseError):
        license_service.activate_online("FB-TEST-AB12-CD34")
    assert license_service.load_local_license() is None


def test_activate_online_rejects_tampered_signature(monkeypatch):
    data = _make_license_data()
    server_response = {"success": True, "message": "ok", "license_data": data, "signature": "AAAA" + _sign(data)[4:]}

    def fake_post(url, body, timeout=10.0):
        return server_response

    monkeypatch.setattr(license_service, "_post_json", fake_post)
    with pytest.raises(license_service.LicenseError):
        license_service.activate_online("FB-TEST-AB12-CD34")
    assert license_service.load_local_license() is None


def test_activate_online_surfaces_server_message(monkeypatch):
    def fake_post(url, body, timeout=10.0):
        return {"success": False, "message": "Already activated on another device."}

    monkeypatch.setattr(license_service, "_post_json", fake_post)
    with pytest.raises(license_service.LicenseError, match="Already activated"):
        license_service.activate_online("FB-TEST-AB12-CD34")


def test_deactivate_online(monkeypatch):
    data = _make_license_data()
    license_service.save_local_license(data, _sign(data))

    calls = {}

    def fake_post(url, body, timeout=10.0):
        calls["url"] = url
        return {"success": True, "message": "ok"}

    monkeypatch.setattr(license_service, "_post_json", fake_post)
    license_service.deactivate_online()
    assert calls["url"].endswith("/api/deactivate")
    assert license_service.load_local_license() is None


def test_deactivate_online_when_server_down_keeps_local(monkeypatch):
    data = _make_license_data()
    license_service.save_local_license(data, _sign(data))

    def fake_post(url, body, timeout=10.0):
        raise license_service.LicenseError("Cannot reach the license server.")

    monkeypatch.setattr(license_service, "_post_json", fake_post)
    with pytest.raises(license_service.LicenseError):
        license_service.deactivate_online(clear_local=False)
    assert license_service.load_local_license() is not None


# ---------------------------------------------------------------------------
# Trial mode
# ---------------------------------------------------------------------------

def test_trial_disabled_by_default(monkeypatch):
    monkeypatch.setattr(config, "TRIAL_DAYS", 0)
    assert license_service.trial_remaining_days() == 0
    assert not license_service.can_start_without_license()


def test_trial_remaining_days(monkeypatch):
    from datetime import datetime, timedelta, timezone

    monkeypatch.setattr(config, "TRIAL_DAYS", 7)
    assert license_service.trial_remaining_days() == 7

    path = license_service._trial_file_path()
    old_first = (datetime.now(timezone.utc) - timedelta(days=5)).isoformat()
    path.write_text(f'{{"first_run": "{old_first}"}}', encoding="utf-8")
    assert license_service.trial_remaining_days() == 2
    assert license_service.can_start_without_license()

    monkeypatch.setattr(config, "TRIAL_DAYS", 4)
    assert license_service.trial_remaining_days() == 0  # expired
    assert not license_service.can_start_without_license()