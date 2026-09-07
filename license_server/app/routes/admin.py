"""Admin API for license & customer management.

Protected by a simple bearer token derived from ADMIN_USERNAME/ADMIN_PASSWORD_HASH
in settings. All responses are licensing metadata only.
"""
from __future__ import annotations

import hmac
import logging
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel

from app.core.config import get_settings
from app.schemas import (
    ActionDetailRequest,
    CustomerCreate,
    DeactivateRequest,
    LicenseCreate,
    LicenseEventOut,
    LicenseUpdate,
)
from app.services.license_service import (
    block_license,
    create_customer,
    create_license,
    deactivate_device,
    get_license,
    get_license_events,
    list_customers,
    list_licenses,
    reactivate_license,
    reset_device,
    revoke_license,
    update_license_status,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin"])

# Simple in-memory admin session tokens (revoked on restart).
_admin_tokens: set[str] = set()


class AdminLoginBody(BaseModel):
    username: str
    password: str


def _issue_token() -> str:
    token = secrets.token_urlsafe(32)
    _admin_tokens.add(token)
    return token


def _verify_token(token: str) -> bool:
    return token in _admin_tokens


def _handle_login(body: AdminLoginBody):
    settings = get_settings()
    username_ok = hmac.compare_digest(body.username.strip(), settings.admin_username)
    password_ok = settings.admin_password_ok(body.password)
    if not (username_ok and password_ok):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid credentials")
    return {"token": _issue_token()}


@router.post("/admin/login")
def admin_login(body: AdminLoginBody):
    """Exchange admin credentials for a session token."""
    return _handle_login(body)


@router.post("/api/v1/admin/login")
def api_v1_admin_login(body: AdminLoginBody):
    """Exchange admin credentials for a session token (v1)."""
    return _handle_login(body)


def require_admin(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authorized")
    token = authorization.removeprefix("Bearer ").strip()
    if not _verify_token(token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authorized")


# --- Customers ---

def _create_customer(body: CustomerCreate):
    result = create_customer(body.name, body.mobile, body.email, body.notes)
    if not result.get("success"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, result.get("message"))
    return result


@router.post("/api/v1/admin/customers", response_model=dict, dependencies=[Depends(require_admin)])
def v1_create_customer(body: CustomerCreate):
    return _create_customer(body)


@router.post("/admin/customers", response_model=dict, dependencies=[Depends(require_admin)])
def admin_create_customer(body: CustomerCreate):
    return _create_customer(body)


@router.get("/api/v1/admin/customers", dependencies=[Depends(require_admin)])
def v1_list_customers(search: str = ""):
    return {"customers": list_customers(search)}


@router.get("/admin/customers", dependencies=[Depends(require_admin)])
def admin_list_customers(search: str = ""):
    return {"customers": list_customers(search)}


# --- Licenses ---

def _create_license(body: LicenseCreate):
    result = create_license(body.customer_id, body.product, body.license_type, body.device_limit)
    if not result.get("success"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, result.get("message"))
    return result


@router.post("/api/v1/admin/licenses", response_model=dict, dependencies=[Depends(require_admin)])
def v1_create_license(body: LicenseCreate):
    return _create_license(body)


@router.post("/admin/licenses", response_model=dict, dependencies=[Depends(require_admin)])
def admin_create_license(body: LicenseCreate):
    return _create_license(body)


@router.get("/api/v1/admin/licenses", dependencies=[Depends(require_admin)])
def v1_list_licenses(search: str = ""):
    return {"licenses": list_licenses(search)}


@router.get("/admin/licenses", dependencies=[Depends(require_admin)])
def admin_list_licenses(search: str = ""):
    return {"licenses": list_licenses(search)}


@router.get("/api/v1/admin/licenses/{license_id}", dependencies=[Depends(require_admin)])
def v1_get_license(license_id: int):
    lic = get_license(license_id)
    if lic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "License not found")
    return {"license": lic}


@router.get("/admin/licenses/{license_id}", dependencies=[Depends(require_admin)])
def admin_get_license(license_id: int):
    lic = get_license(license_id)
    if lic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "License not found")
    return {"license": lic}


# --- Device Reset & Actions ---

@router.post("/api/v1/admin/licenses/{license_id}/reset-device", dependencies=[Depends(require_admin)])
def v1_reset_device(license_id: int, body: ActionDetailRequest | None = None):
    reason = body.reason if body and body.reason else "Admin device reset"
    result = reset_device(license_id, reason=reason)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "License not found")
    return {"license": result}


@router.post("/admin/licenses/{license_id}/reset-device", dependencies=[Depends(require_admin)])
def admin_reset_device(license_id: int, body: ActionDetailRequest | None = None):
    reason = body.reason if body and body.reason else "Admin device reset"
    result = reset_device(license_id, reason=reason)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "License not found")
    return {"license": result}


@router.post("/admin/licenses/{license_id}/deactivate", dependencies=[Depends(require_admin)])
def admin_deactivate_device(license_id: int, body: DeactivateRequest | None = None):
    result = deactivate_device(license_id)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "License not found")
    return {"license": result}


@router.post("/api/v1/admin/licenses/{license_id}/revoke", dependencies=[Depends(require_admin)])
def v1_revoke_license(license_id: int, body: ActionDetailRequest | None = None):
    reason = body.reason if body and body.reason else "Admin revoked"
    result = revoke_license(license_id, reason=reason)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "License not found")
    return {"license": result}


@router.post("/api/v1/admin/licenses/{license_id}/block", dependencies=[Depends(require_admin)])
def v1_block_license(license_id: int, body: ActionDetailRequest | None = None):
    reason = body.reason if body and body.reason else "Admin blocked"
    result = block_license(license_id, reason=reason)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "License not found")
    return {"license": result}


@router.post("/api/v1/admin/licenses/{license_id}/reactivate", dependencies=[Depends(require_admin)])
def v1_reactivate_license(license_id: int, body: ActionDetailRequest | None = None):
    reason = body.reason if body and body.reason else "Admin reactivated"
    result = reactivate_license(license_id, reason=reason)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "License not found")
    return {"license": result}


@router.put("/admin/licenses/{license_id}/status", dependencies=[Depends(require_admin)])
def admin_update_status(license_id: int, body: LicenseUpdate):
    result = update_license_status(license_id, body.status)
    if result is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "License not found")
    return {"license": result}


# --- Audit Events ---

@router.get("/api/v1/admin/licenses/{license_id}/events", dependencies=[Depends(require_admin)])
def v1_license_events(license_id: int):
    lic = get_license(license_id)
    if lic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "License not found")
    events = get_license_events(license_id)
    return {"events": events}


@router.get("/admin/licenses/{license_id}/events", dependencies=[Depends(require_admin)])
def admin_license_events(license_id: int):
    lic = get_license(license_id)
    if lic is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "License not found")
    events = get_license_events(license_id)
    return {"events": events}


@router.get("/admin/health")
def admin_health():
    return {"status": "ok"}