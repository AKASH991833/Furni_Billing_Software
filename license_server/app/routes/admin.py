"""Admin API for license & customer management.

Protected by a simple bearer token derived from ADMIN_USERNAME/ADMIN_PASSWORD_HASH
in settings. All responses are licensing metadata only.
"""
from __future__ import annotations

import hmac
import logging
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from pydantic import BaseModel

from app.core.config import get_settings
from app.schemas import (
    ActionDetailRequest,
    CustomerCreate,
    DeactivateRequest,
    LicenseCreate,
    LicenseEventOut,
    LicenseUpdate,
    ProductCreate,
    ProductOut,
    ProductUpdate,
)
from app.services.license_service import (
    block_license,
    create_customer,
    create_license,
    create_product,
    deactivate_device,
    get_license,
    get_license_events,
    list_customers,
    list_licenses,
    list_products,
    reactivate_license,
    reset_device,
    revoke_license,
    update_license_status,
    update_product,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["admin"])

# Cryptographically strong in-memory admin session tokens (revoked on restart/password change).
_admin_tokens: set[str] = set()
_admin_token_users: dict[str, str] = {}


class AdminLoginBody(BaseModel):
    username: str
    password: str


class ChangePasswordBody(BaseModel):
    current_password: str
    new_password: str


def _issue_token(username: str = "admin") -> str:
    token = secrets.token_urlsafe(48)
    _admin_tokens.add(token)
    _admin_token_users[token] = username
    return token


def _verify_token(token: str) -> bool:
    return token in _admin_tokens


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _handle_login(body: AdminLoginBody, request: Request):
    from app.services.license_service import verify_admin_credentials
    u = body.username.strip()
    client_ip = _get_client_ip(request)
    ok, msg = verify_admin_credentials(u, body.password, client_ip=client_ip)
    if not ok:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail=msg)
    return {"token": _issue_token(u), "username": u}


@router.post("/admin/login")
def admin_login(body: AdminLoginBody, request: Request):
    """Exchange admin credentials for a session token."""
    return _handle_login(body, request)


@router.post("/api/v1/admin/login")
def api_v1_admin_login(body: AdminLoginBody, request: Request):
    """Exchange admin credentials for a session token (v1)."""
    return _handle_login(body, request)


def require_admin(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authorized")
    token = authorization.removeprefix("Bearer ").strip()
    if not _verify_token(token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authorized")


def get_current_admin(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authorized")
    token = authorization.removeprefix("Bearer ").strip()
    if not _verify_token(token):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authorized")
    return _admin_token_users.get(token, "admin")


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


# --- Customer Management (Delete & Update) ---

@router.delete("/api/v1/admin/customers/{customer_id}", dependencies=[Depends(require_admin)])
def v1_delete_customer(customer_id: int):
    from app.services.license_service import delete_customer
    ok = delete_customer(customer_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")
    return {"success": True, "message": "Customer deleted successfully"}


@router.delete("/admin/customers/{customer_id}", dependencies=[Depends(require_admin)])
def admin_delete_customer(customer_id: int):
    return v1_delete_customer(customer_id)


@router.put("/api/v1/admin/customers/{customer_id}", dependencies=[Depends(require_admin)])
def v1_update_customer(customer_id: int, body: CustomerCreate):
    from app.services.license_service import update_customer
    res = update_customer(customer_id, body.name, body.mobile, body.email, body.notes)
    if res is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Customer not found")
    return {"success": True, "customer": res}


@router.put("/admin/customers/{customer_id}", dependencies=[Depends(require_admin)])
def admin_update_customer(customer_id: int, body: CustomerCreate):
    return v1_update_customer(customer_id, body)


# --- License Delete ---

@router.delete("/api/v1/admin/licenses/{license_id}", dependencies=[Depends(require_admin)])
def v1_delete_license(license_id: int):
    from app.services.license_service import delete_license
    ok = delete_license(license_id)
    if not ok:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "License not found")
    return {"success": True, "message": "License deleted successfully"}


@router.delete("/admin/licenses/{license_id}", dependencies=[Depends(require_admin)])
def admin_delete_license(license_id: int):
    return v1_delete_license(license_id)


# --- Admin Password Change ---

@router.post("/api/v1/admin/change-password", dependencies=[Depends(require_admin)])
def v1_change_password(body: ChangePasswordBody, admin_user: str = Depends(get_current_admin)):
    from app.services.license_service import change_admin_password
    ok, msg = change_admin_password(admin_user, body.current_password, body.new_password)
    if not ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, msg)
    # Revoke all existing session tokens on password change for security
    _admin_tokens.clear()
    _admin_token_users.clear()
    return {"success": True, "message": msg}


@router.post("/admin/change-password", dependencies=[Depends(require_admin)])
def admin_change_password(body: ChangePasswordBody, admin_user: str = Depends(get_current_admin)):
    return v1_change_password(body, admin_user)


# --- Products Catalog (Multi-Software Support) ---

@router.get("/api/v1/admin/products", dependencies=[Depends(require_admin)])
def v1_list_products(search: str = ""):
    """List all registered software products with aggregate stats."""
    return {"products": list_products(search=search)}


@router.get("/admin/products", dependencies=[Depends(require_admin)])
def admin_list_products(search: str = ""):
    return v1_list_products(search=search)


@router.post("/api/v1/admin/products", dependencies=[Depends(require_admin)])
def v1_create_product(body: ProductCreate):
    """Register a new software product in the catalog."""
    res = create_product(
        name=body.name,
        code=body.code,
        prefix=body.prefix,
        description=body.description,
        default_device_limit=body.default_device_limit,
    )
    if not res.get("success"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, res.get("message"))
    return res


@router.post("/admin/products", dependencies=[Depends(require_admin)])
def admin_create_product(body: ProductCreate):
    return v1_create_product(body)


@router.put("/api/v1/admin/products/{product_id}", dependencies=[Depends(require_admin)])
def v1_update_product(product_id: int, body: ProductUpdate):
    """Update or toggle software product status."""
    res = update_product(product_id, body.model_dump(exclude_unset=True))
    if res is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Product not found")
    return {"success": True, "product": res}


@router.put("/admin/products/{product_id}", dependencies=[Depends(require_admin)])
def admin_update_product(product_id: int, body: ProductUpdate):
    return v1_update_product(product_id, body)


@router.get("/admin/health")
def admin_health():
    return {"status": "ok"}