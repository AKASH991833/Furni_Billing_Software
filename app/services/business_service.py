"""Business profile service.

Every value comes from the database (never hardcoded), so each business
keeps its own editable profile. Results are cached for speed, and the cache is
invalidated on every save so changes take effect immediately (no restart).

A lightweight observer list lets the UI react to profile changes in real time,
mirroring how a web page reloads after a settings save.
"""
from __future__ import annotations

from app.database.database import get_session
from app.models.models import BusinessProfile
from app.utils.cache import cache

_PROFILE_KEY = "business_profile"

# Observers registered to be called (with no args) right after a profile save,
# so open pages / the header can refresh their profile-derived UI immediately.
_observers = []


def on_profile_changed(callback) -> None:
    """Register ``callback()`` to run after every save_profile()."""
    _observers.append(callback)


def _notify_changed() -> None:
    for cb in _observers:
        try:
            cb()
        except Exception:  # noqa: BLE001, S110
            pass

def get_profile() -> BusinessProfile | None:
    cached_profile = cache.get(_PROFILE_KEY)
    if cached_profile is not None:
        return cached_profile
    session = get_session()
    try:
        profile = session.query(BusinessProfile).order_by(BusinessProfile.id).first()
        cache.set(_PROFILE_KEY, profile, ttl=60)
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
            "default_font_family", "default_font_size",
            "default_font_bold", "default_font_underline",
            # Invoice numbering format
            "invoice_format", "invoice_sequence_digits",
            "next_sequence_number",
            # PDF / print customization
            "pdf_paper_size", "pdf_margin_top", "pdf_margin_bottom",
            "pdf_margin_left", "pdf_margin_right",
            "pdf_primary_color", "pdf_secondary_color",
            "pdf_theme",
        ):
            if key in data:
                setattr(profile, key, data[key])
        session.commit()
        session.refresh(profile)
        cache.invalidate(_PROFILE_KEY)  # Bust cache after save
        _notify_changed()
        return profile
    finally:
        session.close()


def get_invoice_prefix() -> str:
    profile = get_profile()
    return (profile.invoice_prefix if profile and profile.invoice_prefix else "INV").strip()
