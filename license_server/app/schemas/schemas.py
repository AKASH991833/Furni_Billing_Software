"""Pydantic schemas for the license server API."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Activation (client-facing)
# ---------------------------------------------------------------------------

class ActivationRequest(BaseModel):
    license_key: str = Field(min_length=5, max_length=40)
    product: str = Field(default="furniture_bill", max_length=50)
    app_version: str = Field(default="", max_length=30)
    device_fingerprint: str = Field(min_length=16, max_length=128)
    device_label: str | None = Field(default=None, max_length=200)

    @field_validator("license_key")
    @classmethod
    def normalize_key(cls, v: str) -> str:
        return v.strip().upper()


class ActivationResponse(BaseModel):
    success: bool
    message: str = ""
    license_data: dict | None = None
    signature: str | None = None


class DeactivateResponse(BaseModel):
    success: bool
    message: str = ""


class ValidateRequest(BaseModel):
    license_key: str = Field(min_length=5, max_length=50)
    product: str = Field(default="furniture_bill", max_length=50)
    device_fingerprint: str = Field(min_length=16, max_length=128)

    @field_validator("license_key")
    @classmethod
    def normalize_key(cls, v: str) -> str:
        return v.strip().upper()


class ValidateResponse(BaseModel):
    valid: bool
    message: str = ""
    status: str = ""
    license_data: dict | None = None


class LicenseStatusResponse(BaseModel):
    status: str
    service: str = "license-server"
    version: str = "1.0.0"


# ---------------------------------------------------------------------------
# License management (admin)
# ---------------------------------------------------------------------------

class CustomerCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    mobile: str | None = Field(default=None, max_length=30)
    email: str | None = Field(default=None, max_length=150)
    notes: str | None = None


class CustomerOut(BaseModel):
    id: int
    name: str
    mobile: str | None = None
    email: str | None = None
    notes: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class LicenseOut(BaseModel):
    id: int
    license_key: str
    license_key_hash: str | None = None
    customer_id: int
    customer_name: str = ""
    product: str
    product_id: str = ""
    license_type: str
    device_limit: int
    status: str
    current_device: str | None = None
    current_device_id: str | None = None
    device_label: str | None = None
    created_at: datetime | None = None
    activated_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = {"from_attributes": True}


class LicenseEventOut(BaseModel):
    id: int
    license_id: int
    device_fingerprint: str | None = None
    action: str
    ip_address: str | None = None
    success: bool = True
    detail: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}


class LicenseCreate(BaseModel):
    customer_id: int
    product: str = Field(default="furniture_bill", max_length=50)
    license_type: str = Field(default="LIFETIME", pattern="^(LIFETIME)$")
    device_limit: int = Field(default=1, ge=1, le=10)


class LicenseUpdate(BaseModel):
    status: str | None = Field(default=None, pattern="^(ACTIVE|REVOKED|BLOCKED)$")


class ActionDetailRequest(BaseModel):
    reason: str | None = None


class DeactivateRequest(BaseModel):
    device_fingerprint: str | None = None


class ClientDeactivateRequest(BaseModel):
    license_key: str = Field(min_length=5, max_length=50)
    device_fingerprint: str = Field(min_length=16, max_length=128)

    @field_validator("license_key")
    @classmethod
    def normalize_key(cls, v: str) -> str:
        return v.strip().upper()


class CustomerSearch(BaseModel):
    query: str = Field(max_length=200)