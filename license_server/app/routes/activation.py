"""Client-facing license activation API.

The desktop application only ever talks to these endpoints.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request

from app.core.config import get_settings
from app.core.rate_limit import rate_limiter
from app.schemas import (
    ActivationRequest,
    ActivationResponse,
    ClientDeactivateRequest,
    DeactivateResponse,
    LicenseStatusResponse,
    ValidateRequest,
    ValidateResponse,
)
from app.services.license_service import (
    activate_license,
    deactivate_license,
    validate_license,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["activation"])


def _handle_activate(req: ActivationRequest, request: Request) -> ActivationResponse:
    rate_limit = get_settings().rate_limit_activation_per_min
    rate_limiter.max_per_minute = max(1, rate_limit)

    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown"

    if not rate_limiter.is_allowed(client_ip):
        return ActivationResponse(
            success=False,
            message="Too many activation attempts. Please try again later.",
        )

    result = activate_license(
        license_key=req.license_key,
        product=req.product,
        app_version=req.app_version,
        device_fingerprint=req.device_fingerprint,
        device_label=req.device_label,
        ip_address=client_ip,
    )
    return ActivationResponse(**result)


def _handle_deactivate(req: ClientDeactivateRequest, request: Request) -> DeactivateResponse:
    result = deactivate_license(
        license_key=req.license_key,
        device_fingerprint=req.device_fingerprint,
        ip_address=request.client.host if request.client else None,
    )
    return DeactivateResponse(**result)


# --- v1 API ---
@router.post("/api/v1/license/activate", response_model=ActivationResponse)
def api_v1_activate(req: ActivationRequest, request: Request):
    """Activate a license on a device (v1)."""
    return _handle_activate(req, request)


@router.post("/api/v1/license/deactivate", response_model=DeactivateResponse)
def api_v1_deactivate(req: ClientDeactivateRequest, request: Request):
    """Deactivate a license from a device (v1)."""
    return _handle_deactivate(req, request)


@router.post("/api/v1/license/validate", response_model=ValidateResponse)
def api_v1_validate(req: ValidateRequest):
    """Validate active status of a license for a specific device and product."""
    result = validate_license(
        license_key=req.license_key,
        product=req.product,
        device_fingerprint=req.device_fingerprint,
    )
    return ValidateResponse(**result)


@router.get("/api/v1/license/status", response_model=LicenseStatusResponse)
def api_v1_status():
    """Check licensing service status."""
    return LicenseStatusResponse(status="online", service="license-server", version="1.0.0")


# --- Legacy /api endpoints (backward compatibility) ---
@router.post("/api/activate", response_model=ActivationResponse)
def activate(req: ActivationRequest, request: Request):
    """Activate a license on a device (legacy route)."""
    return _handle_activate(req, request)


@router.post("/api/deactivate", response_model=DeactivateResponse)
def deactivate(req: ClientDeactivateRequest, request: Request):
    """Release a license from the bound device so it can be used elsewhere (legacy route)."""
    return _handle_deactivate(req, request)