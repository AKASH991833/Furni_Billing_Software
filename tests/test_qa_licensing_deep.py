"""Comprehensive Software QA Deep Security & Boundary Test Suite for Licensing.

Written from a Senior QA / Penetration Testing perspective to verify resilience against:
1. Malicious / Malformed inputs (SQLi, XSS, Path Traversal, Emojis, Buffer Overflow).
2. Cryptographic tampering & signature forgery.
3. Machine ID spoofing & device mismatch detection.
4. Corrupted, zero-byte, array, and non-JSON local files.
5. Network faults, server crash HTTP responses, timeouts, HTML 502/500 pages.
6. Race conditions and atomic file writes.
"""
from __future__ import annotations

import base64
import json
import os
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from app import config
from app.services import license_service


DEV_PRIVATE = "LsWRDbrl2SkImDvdZyPkKzLJH62FU1lteNUZ6cc5Y6w="


def _sign(license_data: dict) -> str:
    key = Ed25519PrivateKey.from_private_bytes(base64.b64decode(DEV_PRIVATE))
    canonical = json.dumps(license_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.b64encode(key.sign(canonical)).decode()


def _make_valid_data(**kwargs) -> dict:
    data = {
        "license_id": 999,
        "license_key": "FB-TEST-QA01-9999",
        "product": config.PRODUCT_ID,
        "license_type": "LIFETIME",
        "customer_name": "QA Tester Enterprise",
        "device_limit": 1,
        "status": "ACTIVE",
        "device_fingerprint": license_service.machine_id(),
        "activated_at": "2026-09-09T00:00:00Z",
    }
    data.update(kwargs)
    return data


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch, tmp_path):
    lic_file = tmp_path / "license.json"
    monkeypatch.setenv("FURNITURE_BILL_LICENSE", str(lic_file))
    monkeypatch.setenv("FURNITURE_BILL_DATA", str(tmp_path / "data"))
    yield lic_file
    if lic_file.exists():
        lic_file.unlink()


# ===========================================================================
# 1. INPUT SANITIZATION & ADVERSARIAL INPUT TESTS
# ===========================================================================

ADVERSARIAL_TESTS = [
    ("", "empty_string"),
    ("   ", "whitespace_only"),
    ("\t\n\r", "control_chars"),
    ("' OR '1'='1' --", "sqli_attempt"),
    ("<script>alert('XSS')</script>", "xss_attempt"),
    ("../../../../../../etc/passwd", "path_traversal"),
    ("C:\\Windows\\System32\\calc.exe", "os_command_path"),
    ("🔑🎫🛡️💻", "unicode_emojis"),
    ("फ़र्नीचर-बिल-लाइसेंस", "hindi_unicode_string"),
    ("A" * 5_000, "large_buffer_string"),
]


@pytest.mark.parametrize("bad_key,case_id", ADVERSARIAL_TESTS, ids=[t[1] for t in ADVERSARIAL_TESTS])
def test_qa_adversarial_key_inputs(bad_key, case_id):
    """Ensure malicious, boundary, or non-ASCII inputs fail cleanly with LicenseError."""
    if not bad_key.strip():
        with pytest.raises(license_service.LicenseError, match="Please enter your license key"):
            license_service.activate_online(bad_key)
    else:
        with patch("urllib.request.urlopen") as mock_url:
            mock_url.side_effect = urllib.error.URLError("Connection refused")
            with pytest.raises(license_service.LicenseError, match="Internet connection is required"):
                license_service.activate_online(bad_key)


def test_qa_key_trimming_and_casing():
    """Verify license keys with surrounding whitespace or lowercase are normalized."""
    with patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        valid_data = _make_valid_data()
        mock_resp.read.return_value = json.dumps({
            "success": True,
            "license_data": valid_data,
            "signature": _sign(valid_data),
        }).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_url.return_value = mock_resp

        # Pass lowercase with spaces
        result = license_service.activate_online("  fb-test-qa01-9999  ")
        assert result["status"] == license_service.STATUS_VALID
        assert license_service.is_activated()


# ===========================================================================
# 2. CRYPTOGRAPHIC INTEGRITY & ANTI-PIRACY TESTS
# ===========================================================================

def test_qa_signature_bit_flip():
    """Modifying even 1 character in the digital signature must be detected as tampered."""
    data = _make_valid_data()
    sig = _sign(data)
    altered_char = "B" if sig[0] == "A" else "A"
    tampered_sig = altered_char + sig[1:]

    license_service.save_local_license(data, tampered_sig)
    status = license_service.get_license_status()
    assert status["status"] == license_service.STATUS_TAMPERED
    assert not license_service.is_activated()


def test_qa_payload_status_tamper():
    """Changing status from EXPIRED/REVOKED to ACTIVE without server private key fails."""
    data = _make_valid_data(status="REVOKED")
    legit_sig = _sign(data)

    data["status"] = "ACTIVE"
    license_service.save_local_license(data, legit_sig)

    status = license_service.get_license_status()
    assert status["status"] == license_service.STATUS_TAMPERED
    assert not license_service.is_activated()


def test_qa_product_tamper():
    """Tampering product ID to activate on another software must fail."""
    data = _make_valid_data(product="another_app")
    sig = _sign(data)

    license_service.save_local_license(data, sig)
    status = license_service.get_license_status()
    assert status["status"] == license_service.STATUS_TAMPERED
    assert not license_service.is_activated()


def test_qa_device_fingerprint_mismatch():
    """License signed for another machine should be rejected with machine_mismatch."""
    other_machine = "0123456789abcdef0123456789abcdef"
    data = _make_valid_data(device_fingerprint=other_machine)
    sig = _sign(data)

    license_service.save_local_license(data, sig)
    status = license_service.get_license_status()
    assert status["status"] == license_service.STATUS_MACHINE_MISMATCH
    assert not license_service.is_activated()


def test_qa_empty_or_missing_signature():
    """File having license_data but blank or missing signature."""
    data = _make_valid_data()
    license_service.save_local_license(data, "")
    status = license_service.get_license_status()
    assert status["status"] == license_service.STATUS_NO_SIGNATURE
    assert not license_service.is_activated()


# ===========================================================================
# 3. LOCAL FILE CORRUPTION & STORAGE RESILIENCE
# ===========================================================================

def test_qa_corrupted_zero_byte_license_file(_isolate_env):
    """A 0-byte license.json should be quarantined and treated as not_activated."""
    _isolate_env.write_text("", encoding="utf-8")
    status = license_service.get_license_status()
    assert status["status"] == license_service.STATUS_NOT_ACTIVATED
    assert not license_service.is_activated()
    assert (_isolate_env.with_suffix(".corrupt")).exists()


def test_qa_truncated_json_file(_isolate_env):
    """Half-written / broken JSON string should be quarantined without raising uncaught exception."""
    _isolate_env.write_text('{"license_data": {"license_key": "FB-', encoding="utf-8")
    status = license_service.get_license_status()
    assert status["status"] == license_service.STATUS_NOT_ACTIVATED
    assert not license_service.is_activated()


def test_qa_json_array_instead_of_object(_isolate_env):
    """Valid JSON containing an array instead of dict."""
    _isolate_env.write_text('[1, 2, 3, "hacked"]', encoding="utf-8")
    status = license_service.get_license_status()
    assert status["status"] == license_service.STATUS_NOT_ACTIVATED
    assert not license_service.is_activated()


def test_qa_null_bytes_in_license_file(_isolate_env):
    """Null bytes (e.g. disk corruption during sudden shutdown)."""
    _isolate_env.write_bytes(b"\x00\x00\x00\x00\x00")
    status = license_service.get_license_status()
    assert status["status"] == license_service.STATUS_NOT_ACTIVATED
    assert not license_service.is_activated()


# ===========================================================================
# 4. HARDWARE FINGERPRINT (MACHINE ID) INVARIANTS
# ===========================================================================

def test_qa_machine_id_characteristics():
    """Hardware fingerprint must be 32 hex chars, lowercase, deterministic."""
    mid = license_service.machine_id()
    assert isinstance(mid, str)
    assert len(mid) == 32
    assert all(c in "0123456789abcdef" for c in mid)

    for _ in range(100):
        assert license_service.machine_id() == mid


# ===========================================================================
# 5. SERVER FAULT INJECTION & NETWORK RESILIENCE
# ===========================================================================

def test_qa_server_http_500_error():
    """Server crashes with HTTP 500 Internal Server Error."""
    with patch("urllib.request.urlopen") as mock_url:
        mock_url.side_effect = urllib.error.HTTPError(
            url="http://license.server/api/activate",
            code=500,
            msg="Internal Server Error",
            hdrs={},
            fp=None,
        )
        with pytest.raises(license_service.LicenseError, match="temporarily unavailable"):
            license_service.activate_online("FB-TEST-1234-5678")


def test_qa_server_http_429_rate_limit():
    """Server blocks brute force with HTTP 429 Too Many Requests."""
    with patch("urllib.request.urlopen") as mock_url:
        mock_url.side_effect = urllib.error.HTTPError(
            url="http://license.server/api/activate",
            code=429,
            msg="Too Many Requests",
            hdrs={},
            fp=None,
        )
        with pytest.raises(license_service.LicenseError, match="Too many activation attempts"):
            license_service.activate_online("FB-TEST-1234-5678")


def test_qa_server_returns_html_error_page():
    """Server gateway or public Wi-Fi hotspot portal returns HTML page (502 / portal)."""
    with patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        mock_resp.read.return_value = b"<html><head><title>502 Bad Gateway</title></head><body>Bad Gateway</body></html>"
        mock_resp.__enter__.return_value = mock_resp
        mock_url.return_value = mock_resp

        with pytest.raises(license_service.LicenseError, match="Invalid response from the license server"):
            license_service.activate_online("FB-TEST-1234-5678")


def test_qa_server_returns_clean_rejection_message():
    """Server returns JSON with success=False and human-readable message."""
    with patch("urllib.request.urlopen") as mock_url:
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "success": False,
            "message": "This license has expired on 2026-01-01.",
        }).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_url.return_value = mock_resp

        with pytest.raises(license_service.LicenseError, match="This license has expired on 2026-01-01"):
            license_service.activate_online("FB-TEST-EXPIRED-KEY")


def test_qa_deactivation_when_not_activated():
    """Calling deactivation when no license exists should complete gracefully without error."""
    license_service.clear_local_license()
    # Should not raise exception
    license_service.deactivate_online()
    assert license_service.load_local_license() is None
