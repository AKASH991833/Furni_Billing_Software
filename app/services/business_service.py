"""Business profile service.

Every value comes from the database (never hardcoded), so each business
keeps its own editable profile.
"""
from __future__ import annotations

from app.database.database import get_session
from app.models.models import BusinessProfile


def get_profile() -> BusinessProfile | None:
    session = get_session()
    try:
        return session.query(BusinessProfile).order_by(BusinessProfile.id).first()
    finally:
        session.close()


def save_profile(data: dict) -> BusinessProfile:
    session = get_session()
    try:
        profile = session.query(BusinessProfile).order_by(BusinessProfile.id).first()
        if profile is None:
            profile = BusinessProfile()
            session.add(profile)
        for key in (
            "business_name", "owner_name", "business_type", "mobile",
            "alternate_mobile", "email", "address", "city", "state",
            "pincode", "gstin", "invoice_prefix", "logo_path",
            "terms_conditions", "signature_path", "show_gst",
            "default_gst_rate", "currency",
        ):
            if key in data:
                setattr(profile, key, data[key])
        session.commit()
        session.refresh(profile)
        return profile
    finally:
        session.close()


def get_invoice_prefix() -> str:
    profile = get_profile()
    return (profile.invoice_prefix if profile and profile.invoice_prefix else "INV").strip()
