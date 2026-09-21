"""Client-side license service: activation, local persistence, offline verify.

Only the PUBLIC verification key ships with the app (app/config.py). The
private signing key never exists on this machine.

Local license data is stored OUTSIDE the SQLite data folder so a backup or
restore of business data can never clone (or wipe) an activated license.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

import app.config as cfg
from app.utils.machine_id import get_machine_id
from app.utils.paths import data_dir

logger = logging.getLogger(__name__)

# Status strings returned by get_license_status()
STATUS_VALID = "valid"
STATUS_NOT_ACTIVATED = "not_activated"
STATUS_TAMPERED = "tampered"
STATUS_MACHINE_MISMATCH = "machine_mismatch"
STATUS_NO_SIGNATURE = "no_signature"


class LicenseError(Exception):
    """User-facing license error (message shown in the UI)."""


# ---------------------------------------------------------------------------
# Machine identity
# ---------------------------------------------------------------------------

def machine_id(seed: str | None = None) -> str:
    """Stable 32-hex-char fingerprint for the current machine."""
    return get_machine_id(seed)


# ---------------------------------------------------------------------------
# Local license persistence (atomic, tamper-evident)
# ---------------------------------------------------------------------------

def license_file_path() -> Path:
    """Location of the local license file (deliberately outside data_dir)."""
    env = os.environ.get("FURNITURE_BILL_LICENSE")
    if env:
        p = Path(env)
    else:
        p = data_dir().parent / "license.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def load_local_license() -> dict[str, Any] | None:
    """Return the persisted license dict, or None if absent/unreadable."""
    path = license_file_path()
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        os.replace(path, path.with_suffix(".corrupt"))  # quarantine corrupt file
        return None
    return data if isinstance(data, dict) else None


def save_local_license(license_data: dict[str, Any], signature: str) -> None:
    """Atomically persist a signed license to disk."""
    path = license_file_path()
    payload = {
        "license_data": license_data,
        "signature": signature,
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def clear_local_license() -> None:
    path = license_file_path()
    if path.exists():
        path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Offline signature verification (Ed25519 public key)
# ---------------------------------------------------------------------------

def _public_key() -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(base64.b64decode(cfg.LICENSE_PUBLIC_KEY))


def verify_signed_license(license_data: dict[str, Any], signature: str) -> bool:
    """Verify `signature` over `license_data` using the embedded public key."""
    if not signature or not license_data:
        return False
    try:
        canonical = json.dumps(license_data, sort_keys=True, separators=(",", ":")).encode("utf-8")
        _public_key().verify(base64.b64decode(signature), canonical)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Status evaluation (offline)
# ---------------------------------------------------------------------------

def get_license_status() -> dict[str, Any]:
    """Evaluate the local license. Never throws."""
    local = load_local_license()
    if local is None:
        return {"status": STATUS_NOT_ACTIVATED, "licenses": None}
    license_data = local.get("license_data") or {}
    signature = local.get("signature") or ""

    if not signature:
        return {"status": STATUS_NO_SIGNATURE, "licenses": license_data}

    if not verify_signed_license(license_data, signature):
        return {"status": STATUS_TAMPERED, "licenses": license_data}

    if license_data.get("device_fingerprint") != machine_id():
        return {"status": STATUS_MACHINE_MISMATCH, "licenses": license_data}

    if license_data.get("product") != cfg.PRODUCT_ID:
        return {"status": STATUS_TAMPERED, "licenses": license_data}

    if license_data.get("status") not in ("ACTIVE",):
        return {"status": STATUS_TAMPERED, "licenses": license_data}

    return {"status": STATUS_VALID, "licenses": license_data}


def is_activated() -> bool:
    return get_license_status()["status"] == STATUS_VALID


# ---------------------------------------------------------------------------
# Trial mode (optional, disabled by default)
# ---------------------------------------------------------------------------

def _trial_file_path() -> Path:
    return data_dir().parent / "trial.json"


def trial_remaining_days() -> int:
    """Days left in the trial, or 0 when disabled/expired/activated already."""
    if not cfg.TRIAL_DAYS or is_activated():
        return 0
    path = _trial_file_path()
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            first = datetime.fromisoformat(data["first_run"])
        else:
            first = datetime.now(timezone.utc)
            path.write_text(json.dumps({"first_run": first.isoformat()}), encoding="utf-8")
    except (OSError, ValueError, KeyError):
        first = datetime.now(timezone.utc)
        try:
            path.write_text(json.dumps({"first_run": first.isoformat()}), encoding="utf-8")
        except OSError:
            return 0
    elapsed = (datetime.now(timezone.utc) - first).days
    remaining = cfg.TRIAL_DAYS - elapsed
    return max(remaining, 0)


def can_start_without_license() -> bool:
    """True if a valid license exists OR the trial period is still running."""
    return is_activated() or trial_remaining_days() > 0


# ---------------------------------------------------------------------------
# Online activation / deactivation
# ---------------------------------------------------------------------------

def _post_json(url: str, body: dict[str, Any], timeout: float = 10.0) -> dict[str, Any]:
    """POST JSON, return parsed JSON. Raises LicenseError on transport errors."""
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            try:
                payload = json.loads(resp.read().decode("utf-8"))
            except (ValueError, UnicodeDecodeError) as parse_err:
                raise LicenseError("Invalid response from the license server.") from parse_err
    except urllib.error.HTTPError as exc:
        logger.warning("License server HTTP %s from %s", exc.code, url)
        try:
            raw = exc.read().decode("utf-8")
            err_data = json.loads(raw)
            if isinstance(err_data, dict):
                msg = err_data.get("message") or err_data.get("detail")
                if msg:
                    raise LicenseError(str(msg)) from exc
        except (LicenseError, Exception) as parse_exc:
            if isinstance(parse_exc, LicenseError):
                raise
        if exc.code == 429:
            raise LicenseError("Too many activation attempts. Please try again later.") from exc
        if exc.code >= 500:
            raise LicenseError("License server is temporarily unavailable. Please try again.") from exc
        raise LicenseError(f"Server error ({exc.code}). Please try again later.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        logger.warning("License server unreachable: %s", exc)
        raise LicenseError(
            "Internet connection is required for activation."
        ) from exc
    if not isinstance(payload, dict):
        raise LicenseError("Invalid response from the license server.")
    return payload


def activate_online(license_key: str, timeout: float = 10.0) -> dict[str, Any]:
    """Activate a key on this machine and persist the signed license.

    Raises LicenseError on a user-visible failure; returns the verification
    dict (status == "valid") on success.
    """
    key = license_key.strip().upper()
    if not key:
        raise LicenseError("Please enter your license key.")

    body = {
        "license_key": key,
        "product": cfg.PRODUCT_ID,
        "app_version": cfg.APP_VERSION,
        "device_fingerprint": machine_id(),
    }
    payload = _post_json(f"{cfg.LICENSE_SERVER_URL}/api/activate", body, timeout)

    if not payload.get("success"):
        raise LicenseError(payload.get("message") or "Activation failed.")

    license_data = payload.get("license_data")
    signature = payload.get("signature")
    if not license_data or not signature:
        raise LicenseError("The license server returned incomplete data.")

    if not verify_signed_license(license_data, signature):
        raise LicenseError("License verification failed. Contact support.")

    # Never persist anything that doesn't match this exact machine.
    if license_data.get("device_fingerprint") != machine_id():
        raise LicenseError("License does not match this computer.")

    save_local_license(license_data, signature)
    status = get_license_status()
    if status["status"] != STATUS_VALID:
        raise LicenseError("License could not be verified.")
    return status


def deactivate_online(timeout: float = 10.0, clear_local: bool = True) -> None:
    """Release this machine's license binding on the server (best effort),
    then remove the local license file.

    Raises LicenseError if the server is unreachable; the local license is
    still cleared when `clear_local` is True.
    """
    local = load_local_license()
    key = (local or {}).get("license_data", {}).get("license_key", "")
    server_ok = False
    if key:
        try:
            body = {"license_key": key, "device_fingerprint": machine_id()}
            payload = _post_json(f"{cfg.LICENSE_SERVER_URL}/api/deactivate", body, timeout)
            server_ok = bool(payload.get("success"))
        except LicenseError:
            if not clear_local:
                raise
    if clear_local:
        clear_local_license()
    if key and not server_ok and not clear_local:
        raise LicenseError("Could not contact the license server.")