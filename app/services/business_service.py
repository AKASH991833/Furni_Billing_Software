"""Business profile service.

Every value comes from the database (never hardcoded), so each business
keeps its own editable profile. Results are cached for speed.
"""
from __future__ import annotations

from app.database.database import get_session
from app.models.models import BusinessProfile
from app.utils.cache import cache


def get_profile() -> BusinessProfile | None:
    cached_profile = cache.get("business_profile")
    if cached_profile is not None:
        return cached_profile
    session = get_session()
    try:
        profile = session.query(BusinessProfile).order_by(BusinessProfile.id).first()
        cache.set("business_profile", profile, ttl=60)  # Cache for 60s
        return profile
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
        cache.invalidate("business_profile")  # Bust cache after save
        return profile
    finally:
        session.close()


def get_invoice_prefix() -> str:
    profile = get_profile()
    return (profile.invoice_prefix if profile and profile.invoice_prefix else "INV").strip()
