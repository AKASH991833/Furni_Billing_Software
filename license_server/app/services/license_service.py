"""License service: generation, activation, validation.

All server-side license logic lives here. The service never sees or stores
customer billing data — only licensing metadata.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.crypto.ed25519 import private_key_from_base64, sign_payload
from app.crypto.license_keys import generate_license_key, is_valid_format
from app.models import ActivationLog, AdminUser, Customer, License

logger = logging.getLogger(__name__)

PRODUCT = "furniture_bill"
LICENSE_TYPE = "LIFETIME"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def hash_license_key(key: str) -> str:
    """Compute SHA-256 hex digest of the normalized uppercase license key."""
    return hashlib.sha256(key.strip().upper().encode("utf-8")).hexdigest()


def normalize_product(p: str | None) -> str:
    """Normalize product identifier strings."""
    if not p:
        return "furniture_bill"
    norm = p.strip().lower().replace("-", "_").replace(" ", "_")
    if norm in ("furniture_billing", "furniture_bill"):
        return "furniture_bill"
    return norm


def _get_private_key():
    settings = get_settings()
    if not settings.private_signing_key:
        raise RuntimeError("PRIVATE_SIGNING_KEY is not configured on the server")
    return private_key_from_base64(settings.private_signing_key)


def _build_signed_payload(license_: License, device_fingerprint: str) -> tuple[dict[str, Any], str]:
    """Build the signed license payload returned to the client."""
    payload: dict[str, Any] = {
        "license_id": license_.id,
        "license_key": license_.license_key,
        "product": license_.product,
        "license_type": license_.license_type,
        "customer_name": license_.customer.name if license_.customer else "",
        "device_limit": license_.device_limit,
        "status": license_.status,
        "device_fingerprint": device_fingerprint,
        "activated_at": license_.activated_at.isoformat() if license_.activated_at else None,
    }
    signature = sign_payload(_get_private_key(), payload)
    return payload, signature


def _log_activation(session: Session, license_: License, device: str | None,
                    action: str, ip: str | None, success: bool, detail: str = "") -> None:
    session.add(
        ActivationLog(
            license_id=license_.id,
            device_fingerprint=device,
            action=action,
            ip_address=ip,
            success=success,
            detail=detail,
        )
    )


def _generic_error() -> str:
    """Generic, safe error message — never leaks server/db internals."""
    return "Activation failed. Please check your license key and try again."


# ---------------------------------------------------------------------------
# Activation (client-facing)
# ---------------------------------------------------------------------------

def activate_license(
    license_key: str,
    product: str,
    app_version: str,
    device_fingerprint: str,
    device_label: str | None,
    ip_address: str | None = None,
) -> dict[str, Any]:
    """Validate and bind a license to a device. Returns an ActivationResponse dict."""
    session = None
    try:
        if not is_valid_format(license_key):
            return {"success": False, "message": _generic_error()}

        session = _get_session()
        key_norm = license_key.strip().upper()
        key_hash = hash_license_key(key_norm)

        license_: License | None = session.execute(
            select(License).where(
                or_(License.license_key == key_norm, License.license_key_hash == key_hash)
            )
        ).scalar_one_or_none()

        if license_ is None:
            return {"success": False, "message": "Invalid license key."}

        # Status check
        if license_.status == "REVOKED":
            _log_activation(session, license_, device_fingerprint, "ACTIVATE", ip_address, False, "license_revoked")
            session.commit()
            return {"success": False, "message": "This license has been revoked."}

        if license_.status == "BLOCKED":
            _log_activation(session, license_, device_fingerprint, "ACTIVATE", ip_address, False, "license_blocked")
            session.commit()
            return {"success": False, "message": "This license has been blocked."}

        if license_.status != "ACTIVE":
            _log_activation(session, license_, device_fingerprint, "ACTIVATE", ip_address, False, "license_not_active")
            session.commit()
            return {"success": False, "message": "This license is not active."}

        # Multi-product validation: License product must match the client application product
        if normalize_product(license_.product) != normalize_product(product):
            _log_activation(session, license_, device_fingerprint, "ACTIVATE", ip_address, False, "product_mismatch")
            session.commit()
            return {"success": False, "message": "This license is not valid for this product."}

        # Device binding policy: one device at a time by default
        if license_.current_device and license_.current_device != device_fingerprint:
            _log_activation(session, license_, device_fingerprint, "ACTIVATE", ip_address,
                            False, "device_mismatch")
            session.commit()
            return {
                "success": False,
                "message": "This license is already activated on another device.",
            }

        # Same device re-activation OR first activation
        license_.current_device = device_fingerprint
        license_.device_label = device_label or license_.device_label
        if not license_.activated_at:
            license_.activated_at = _now()
        license_.updated_at = _now()

        _log_activation(session, license_, device_fingerprint, "ACTIVATE", ip_address, True)
        session.commit()

        payload, signature = _build_signed_payload(license_, device_fingerprint)
        return {
            "success": True,
            "message": "License activated.",
            "license_data": payload,
            "signature": signature,
        }
    except Exception:
        logger.exception("Activation failed")
        return {"success": False, "message": _generic_error()}
    finally:
        if session is not None:
            session.close()


def validate_license(license_key: str, product: str, device_fingerprint: str) -> dict[str, Any]:
    """Check online if a license and device binding are currently valid."""
    session = None
    try:
        session = _get_session()
        key_norm = license_key.strip().upper()
        key_hash = hash_license_key(key_norm)

        license_: License | None = session.execute(
            select(License).where(
                or_(License.license_key == key_norm, License.license_key_hash == key_hash)
            )
        ).scalar_one_or_none()

        if license_ is None:
            return {"valid": False, "message": "License not found.", "status": "NOT_FOUND"}

        if license_.status != "ACTIVE":
            return {"valid": False, "message": f"License is {license_.status.lower()}.", "status": license_.status}

        if normalize_product(license_.product) != normalize_product(product):
            return {"valid": False, "message": "Wrong product.", "status": "WRONG_PRODUCT"}

        if license_.current_device != device_fingerprint:
            return {"valid": False, "message": "Device not bound to this license.", "status": "DEVICE_MISMATCH"}

        return {
            "valid": True,
            "message": "License is valid and active.",
            "status": license_.status,
            "license_data": _license_dict(session, license_),
        }
    except Exception:
        logger.exception("Validation query failed")
        return {"valid": False, "message": "Validation check failed.", "status": "ERROR"}
    finally:
        if session is not None:
            session.close()


def deactivate_license(license_key: str, device_fingerprint: str, ip_address: str | None = None) -> dict[str, Any]:
    """Client-facing deactivation: only the bound device may release a license."""
    session = None
    try:
        if not is_valid_format(license_key):
            return {"success": False, "message": _generic_error()}
        session = _get_session()
        key_norm = license_key.strip().upper()
        key_hash = hash_license_key(key_norm)

        license_: License | None = session.execute(
            select(License).where(
                or_(License.license_key == key_norm, License.license_key_hash == key_hash)
            )
        ).scalar_one_or_none()

        if license_ is None:
            return {"success": False, "message": "Invalid license key."}
        if license_.current_device is None:
            return {"success": False, "message": "This license is not bound to a device."}
        if license_.current_device != device_fingerprint:
            _log_activation(session, license_, device_fingerprint, "DEACTIVATE", ip_address, False, "device_mismatch")
            session.commit()
            return {"success": False, "message": "This device is not the bound device."}

        license_.current_device = None
        license_.device_label = None
        license_.updated_at = _now()
        _log_activation(session, license_, device_fingerprint, "DEACTIVATE", ip_address, True)
        session.commit()
        return {"success": True, "message": "License deactivated."}
    except Exception:
        logger.exception("Deactivation failed")
        return {"success": False, "message": _generic_error()}
    finally:
        if session is not None:
            session.close()


# ---------------------------------------------------------------------------
# License management (admin)
# ---------------------------------------------------------------------------

def create_license(
    customer_id: int,
    product: str = "furniture_bill",
    license_type: str = "LIFETIME",
    device_limit: int = 1,
) -> dict[str, Any]:
    """Create a new unique license for an existing customer."""
    session = None
    try:
        session = _get_session()
        customer = session.get(Customer, customer_id)
        if customer is None:
            return {"success": False, "message": "Customer not found."}

        norm_product = normalize_product(product)
        key = generate_license_key(product=norm_product)
        key_hash = hash_license_key(key)

        license_ = License(
            license_key=key,
            license_key_hash=key_hash,
            customer_id=customer_id,
            product=norm_product,
            license_type=license_type,
            device_limit=device_limit,
            status="ACTIVE",
        )
        session.add(license_)
        session.flush()

        _log_activation(session, license_, None, "CREATE", None, True, f"Created for {customer.name}")
        session.commit()
        session.refresh(license_)
        return {"success": True, "license": _license_dict(session, license_)}
    except Exception:
        logger.exception("License creation failed")
        return {"success": False, "message": "Failed to create license."}
    finally:
        if session is not None:
            session.close()


def list_licenses(search: str = "") -> list[dict[str, Any]]:
    """List all licenses, optionally filtering by key/customer."""
    session = None
    try:
        session = _get_session()
        stmt = select(License).join(License.customer)
        if search.strip():
            like = f"%{search.strip().upper()}%"
            stmt = stmt.where(
                or_(License.license_key.ilike(like), Customer.name.ilike(like))
            )
        licenses = session.execute(stmt.order_by(License.id.desc())).scalars().all()
        return [_license_dict(session, lic) for lic in licenses]
    finally:
        if session is not None:
            session.close()


def get_license(license_id: int) -> dict[str, Any] | None:
    session = None
    try:
        session = _get_session()
        license_ = session.get(License, license_id)
        if license_ is None:
            return None
        return _license_dict(session, license_)
    finally:
        if session is not None:
            session.close()


def update_license_status(license_id: int, status: str, detail: str = "") -> dict[str, Any] | None:
    """Set status: ACTIVE / REVOKED / BLOCKED."""
    session = None
    try:
        session = _get_session()
        license_ = session.get(License, license_id)
        if license_ is None:
            return None
        action_map = {"ACTIVE": "REACTIVATE", "REVOKED": "REVOKE", "BLOCKED": "BLOCK"}
        action = action_map.get(status, "STATUS")
        license_.status = status
        license_.updated_at = _now()
        _log_activation(session, license_, license_.current_device, action, None, True, detail=detail or status)
        session.commit()
        return _license_dict(session, license_)
    finally:
        if session is not None:
            session.close()


def reset_device(license_id: int, reason: str = "Admin reset") -> dict[str, Any] | None:
    """Clear the device binding so another device can activate (admin-controlled reset)."""
    session = None
    try:
        session = _get_session()
        license_ = session.get(License, license_id)
        if license_ is None:
            return None
        old_device = license_.current_device
        license_.current_device = None
        license_.device_label = None
        license_.updated_at = _now()
        _log_activation(session, license_, old_device, "RESET_DEVICE", None, True, detail=reason)
        session.commit()
        return _license_dict(session, license_)
    finally:
        if session is not None:
            session.close()


def deactivate_device(license_id: int) -> dict[str, Any] | None:
    """Alias for reset_device to maintain backward compatibility."""
    return reset_device(license_id, reason="Admin deactivate")


def revoke_license(license_id: int, reason: str = "Admin revoked") -> dict[str, Any] | None:
    """Revoke a license."""
    return update_license_status(license_id, "REVOKED", detail=reason)


def block_license(license_id: int, reason: str = "Admin blocked") -> dict[str, Any] | None:
    """Block a license."""
    return update_license_status(license_id, "BLOCKED", detail=reason)


def reactivate_license(license_id: int, reason: str = "Admin reactivated") -> dict[str, Any] | None:
    """Reactivate a revoked or blocked license."""
    return update_license_status(license_id, "ACTIVE", detail=reason)


def get_license_events(license_id: int) -> list[dict[str, Any]]:
    """Return all audit events for a license."""
    session = None
    try:
        session = _get_session()
        stmt = select(ActivationLog).where(ActivationLog.license_id == license_id).order_by(ActivationLog.id.desc())
        events = session.execute(stmt).scalars().all()
        return [_event_dict(e) for e in events]
    finally:
        if session is not None:
            session.close()


# ---------------------------------------------------------------------------
# Customers
# ---------------------------------------------------------------------------

def create_customer(name: str, mobile: str | None, email: str | None, notes: str | None) -> dict[str, Any]:
    session = None
    try:
        session = _get_session()
        customer = Customer(name=name, mobile=mobile, email=email, notes=notes)
        session.add(customer)
        session.commit()
        session.refresh(customer)
        return {"success": True, "customer": _customer_dict(customer)}
    except Exception:
        logger.exception("Customer creation failed")
        return {"success": False, "message": "Failed to create customer."}
    finally:
        if session is not None:
            session.close()


def list_customers(search: str = "") -> list[dict[str, Any]]:
    session = None
    try:
        session = _get_session()
        stmt = select(Customer).order_by(Customer.id.desc())
        if search.strip():
            like = f"%{search.strip()}%"
            stmt = stmt.where(or_(Customer.name.ilike(like), Customer.mobile.ilike(like), Customer.email.ilike(like)))
        customers = session.execute(stmt).scalars().all()
        return [_customer_dict(c) for c in customers]
    finally:
        if session is not None:
            session.close()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_session() -> Session:
    from app.models.database import get_session as _gs
    return _gs()


def _now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc)


def _customer_dict(c: Customer):
    return {
        "id": c.id,
        "name": c.name,
        "mobile": c.mobile,
        "email": c.email,
        "notes": c.notes,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


def _license_dict(session, lic: License) -> dict[str, Any]:
    return {
        "id": lic.id,
        "license_key": lic.license_key,
        "license_key_hash": lic.license_key_hash,
        "customer_id": lic.customer_id,
        "customer_name": lic.customer.name if lic.customer else "",
        "product": lic.product,
        "product_id": lic.product,
        "license_type": lic.license_type,
        "device_limit": lic.device_limit,
        "status": lic.status,
        "current_device": lic.current_device,
        "current_device_id": lic.current_device,
        "device_label": lic.device_label,
        "created_at": lic.created_at.isoformat() if lic.created_at else None,
        "activated_at": lic.activated_at.isoformat() if lic.activated_at else None,
        "updated_at": lic.updated_at.isoformat() if lic.updated_at else None,
    }


def _event_dict(e: ActivationLog) -> dict[str, Any]:
    cat = getattr(e, "created_at", None)
    return {
        "id": e.id,
        "license_id": e.license_id,
        "device_fingerprint": e.device_fingerprint,
        "action": e.action,
        "ip_address": e.ip_address,
        "success": e.success,
        "detail": e.detail,
        "created_at": cat.isoformat() if cat else None,
    }


def delete_customer(customer_id: int) -> bool:
    """Delete a customer and all their associated licenses and logs."""
    session = None
    try:
        session = _get_session()
        customer = session.get(Customer, customer_id)
        if not customer:
            return False
        session.delete(customer)
        session.commit()
        return True
    finally:
        if session is not None:
            session.close()


def update_customer(customer_id: int, name: str, mobile: str | None, email: str | None, notes: str | None) -> dict[str, Any] | None:
    """Update customer details."""
    session = None
    try:
        session = _get_session()
        customer = session.get(Customer, customer_id)
        if not customer:
            return None
        customer.name = name.strip()
        customer.mobile = mobile.strip() if mobile else None
        customer.email = email.strip() if email else None
        customer.notes = notes.strip() if notes else None
        session.commit()
        session.refresh(customer)
        return _customer_dict(customer)
    finally:
        if session is not None:
            session.close()


def delete_license(license_id: int) -> bool:
    """Delete a license from the database."""
    session = None
    try:
        session = _get_session()
        lic = session.get(License, license_id)
        if not lic:
            return False
        session.delete(lic)
        session.commit()
        return True
    finally:
        if session is not None:
            session.close()


def verify_admin_credentials(username: str, password: str) -> bool:
    """Verify admin login against the DB AdminUser or fallback to config."""
    session = None
    try:
        session = _get_session()
        stmt = select(AdminUser).where(AdminUser.username == username.strip())
        admin_user = session.execute(stmt).scalars().first()
        hashed = hashlib.sha256(password.encode("utf-8")).hexdigest()
        if admin_user:
            return admin_user.password_hash == hashed
        
        # Fallback to config settings
        settings = get_settings()
        import hmac
        if hmac.compare_digest(username.strip(), settings.admin_username) and settings.admin_password_ok(password):
            # Seed the AdminUser into DB automatically
            try:
                new_admin = AdminUser(username=username.strip(), password_hash=hashed)
                session.add(new_admin)
                session.commit()
            except Exception:
                session.rollback()
            return True
        return False
    finally:
        if session is not None:
            session.close()


def change_admin_password(username: str, current_password: str, new_password: str) -> tuple[bool, str]:
    """Change admin password and persist to database."""
    if not new_password or len(new_password) < 6:
        return False, "New password must be at least 6 characters long."
    if not verify_admin_credentials(username, current_password):
        return False, "Current password does not match."
    
    session = None
    try:
        session = _get_session()
        stmt = select(AdminUser).where(AdminUser.username == username.strip())
        admin_user = session.execute(stmt).scalars().first()
        new_hash = hashlib.sha256(new_password.encode("utf-8")).hexdigest()
        if admin_user:
            admin_user.password_hash = new_hash
            admin_user.updated_at = _now()
        else:
            admin_user = AdminUser(username=username.strip(), password_hash=new_hash)
            session.add(admin_user)
        session.commit()
        return True, "Password changed successfully."
    finally:
        if session is not None:
            session.close()