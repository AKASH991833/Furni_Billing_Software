"""Input validation utilities.

Provides reusable validators for common Indian business data:
  - Mobile numbers (10-digit Indian)
  - Email addresses
  - GSTIN (15-character Indian GST identification number)
  - Pincode (6-digit Indian)
  - Business name / customer name
"""
from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class ValidationError:
    field: str
    message: str


def validate_mobile(value: str) -> str | None:
    """Validate Indian mobile number. Returns error message or None."""
    v = value.strip()
    if not v:
        return None  # mobile is optional
    digits = re.sub(r"[^0-9]", "", v)
    if len(digits) == 10 and digits[0] in "6789":
        return None
    if len(digits) == 12 and digits.startswith("91") and digits[2] in "6789":
        return None
    return "Enter a valid 10-digit mobile number (e.g. 9876543210)"


def validate_email(value: str) -> str | None:
    """Validate email format. Returns error message or None."""
    v = value.strip()
    if not v:
        return None  # email is optional
    pattern = r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$"
    if re.match(pattern, v):
        return None
    return "Enter a valid email address (e.g. name@example.com)"


def validate_gstin(value: str) -> str | None:
    """Validate Indian GSTIN format. Returns error message or None.

    GSTIN format: 2-digit state code + PAN (10 chars) + 1 digit entity + Z + checksum
    Total: 15 characters, alphanumeric.
    """
    v = value.strip().upper()
    if not v:
        return None  # GSTIN is optional
    if len(v) != 15:
        return f"GSTIN must be 15 characters (got {len(v)})"
    pattern = r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$"
    if re.match(pattern, v):
        return None
    return "Invalid GSTIN format (e.g. 22AABCB1234F1Z5)"


def validate_pincode(value: str) -> str | None:
    """Validate Indian pincode. Returns error message or None."""
    v = value.strip()
    if not v:
        return None  # pincode is optional
    digits = re.sub(r"[^0-9]", "", v)
    if len(digits) == 6:
        return None
    return "Pincode must be 6 digits"


def validate_name(value: str, field_name: str = "Name") -> str | None:
    """Validate that name is not empty. Returns error message or None."""
    v = value.strip()
    if not v:
        return f"{field_name} is required"
    if len(v) < 2:
        return f"{field_name} must be at least 2 characters"
    return None


def validate_customer(data: dict) -> list[ValidationError]:
    """Validate all customer fields. Returns list of errors (empty = valid)."""
    errors = []

    name_err = validate_name(data.get("name", ""), "Customer name")
    if name_err:
        errors.append(ValidationError("name", name_err))

    mobile_err = validate_mobile(data.get("mobile", ""))
    if mobile_err:
        errors.append(ValidationError("mobile", mobile_err))

    alt_mobile_err = validate_mobile(data.get("alternate_mobile", ""))
    if alt_mobile_err:
        errors.append(ValidationError("alternate_mobile", alt_mobile_err))

    email_err = validate_email(data.get("email", ""))
    if email_err:
        errors.append(ValidationError("email", email_err))

    gstin_err = validate_gstin(data.get("gstin", ""))
    if gstin_err:
        errors.append(ValidationError("gstin", gstin_err))

    pincode_err = validate_pincode(data.get("pincode", ""))
    if pincode_err:
        errors.append(ValidationError("pincode", pincode_err))

    return errors


def validate_business_profile(data: dict) -> list[ValidationError]:
    """Validate business profile fields. Returns list of errors (empty = valid)."""
    errors = []

    name_err = validate_name(data.get("business_name", ""), "Business name")
    if name_err:
        errors.append(ValidationError("business_name", name_err))

    mobile_err = validate_mobile(data.get("mobile", ""))
    if mobile_err:
        errors.append(ValidationError("mobile", mobile_err))

    email_err = validate_email(data.get("email", ""))
    if email_err:
        errors.append(ValidationError("email", email_err))

    gstin_err = validate_gstin(data.get("gstin", ""))
    if gstin_err:
        errors.append(ValidationError("gstin", gstin_err))

    pincode_err = validate_pincode(data.get("pincode", ""))
    if pincode_err:
        errors.append(ValidationError("pincode", pincode_err))

    return errors
