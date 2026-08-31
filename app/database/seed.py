"""Startup initialisation: create tables and seed default (editable) data.

Default data is only used for development convenience. All of it can be
edited by the user from within the application, and nothing is hardcoded
for a real business.
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.models import (
    Area,
    Base,
    BusinessProfile,
    Item,
    Invoice,
    Setting,
    User,
)
from app.database.database import get_engine, get_session

DEFAULT_AREAS = [
    "HALL",
    "LIVING ROOM",
    "MASTER BEDROOM",
    "BEDROOM",
    "KITCHEN",
    "DINING ROOM",
    "POOJA ROOM",
    "BATHROOM",
    "DRESSING ROOM",
    "OFFICE",
    "SHOP",
    "STORE ROOM",
    "OTHER",
]

DEFAULT_ITEMS = {
    "KITCHEN": [
        "Kitchen Cabinet", "Base Cabinet", "Wall Cabinet", "Tall Unit",
        "Drawer Unit", "Loft", "Shelf", "Sink Unit", "Platform",
    ],
    "HALL": [
        "TV Unit", "Crockery Unit", "Shoe Cabinet", "Wall Panel",
        "Partition", "Loft", "Main Door",
    ],
    "LIVING ROOM": [
        "TV Unit", "Crockery Unit", "Shoe Cabinet", "Wall Panel",
        "Partition", "Loft", "Main Door", "Sofa Sett",
    ],
    "MASTER BEDROOM": [
        "Bed", "Wardrobe", "Dressing Table", "Bedside Table", "Loft",
        "Headboard", "TV Unit",
    ],
    "BEDROOM": [
        "Bed", "Wardrobe", "Bedside Table", "Loft", "Headboard", "TV Unit",
    ],
    "KITCHEN_extra": None,
    "DINING ROOM": [
        "Dining Table", "Dining Chair", "Sideboard", "Pooja Shelf", "Loft",
    ],
    "POOJA ROOM": ["Pooja Shelf", "Pooja Mandir", "Cabinet", "Loft"],
    "BATHROOM": ["Cabinet", "Mirror", "Shelf", "Sink Unit"],
    "DRESSING ROOM": ["Dressing Table", "Wardrobe", "Mirror", "Shelf"],
    "OFFICE": ["Workstation", "Cabin", "File Cabinet", "Shelf", "Partition"],
    "SHOP": ["Counter", "Display Shelf", "Cabin", "Partition"],
    "STORE ROOM": ["Shelf", "Rack", "Cabin"],
    "OTHER": ["Custom Item"],
}


def create_all() -> None:
    Base.metadata.create_all(bind=get_engine())
    _migrate_schema()


def _migrate_schema() -> None:
    """Add columns introduced after the original schema was created.

    ``create_all`` does not alter existing tables, so lightweight additive
    migrations live here. Only additive, non-destructive changes are allowed.
    """
    engine = get_engine()
    from sqlalchemy import text
    with engine.connect() as conn:
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info(invoices)"))]
        if "gst_enabled" not in cols:
            conn.execute(
                text("ALTER TABLE invoices ADD COLUMN gst_enabled BOOLEAN DEFAULT 1 NOT NULL")
            )
        conn.commit()


def seed_default_data() -> None:
    session: Session = get_session()
    try:
        if session.query(User).count() == 0:
            session.add(User(
                username="admin",
                password_hash="",  # not used yet; replaced by auth if enabled
                full_name="Administrator",
            ))

        if session.query(BusinessProfile).count() == 0:
            session.add(BusinessProfile(
                business_name="My Furniture Business",
                owner_name="Owner Name",
                business_type="Furniture Contractor & Interior Work",
                mobile="",
                alternate_mobile="",
                email="",
                address="",
                city="",
                state="",
                pincode="",
                gstin="",
                invoice_prefix="INV",
                terms_conditions=(
                    "1. Advance of 50% required to confirm order.\n"
                    "2. Balance payable on completion.\n"
                    "3. Payment mode: Cash / UPI / Bank Transfer.\n"
                    "4. Warranty as per company policy."
                ),
                show_gst=False,
                default_gst_rate=18.0,
            ))

        if session.query(Setting).filter_by(key="setup_done").count() == 0:
            session.add(Setting(key="setup_done", value="1"))

        # Areas
        existing_areas = {a.name for a in session.query(Area).all()}
        for idx, name in enumerate(DEFAULT_AREAS):
            if name not in existing_areas:
                session.add(Area(name=name, is_system=True, sort_order=idx))

        # System (suggested) items
        for area, names in DEFAULT_ITEMS.items():
            if not names:
                continue
            for n in names:
                if not session.query(Item).filter_by(name=n, area=area).first():
                    session.add(Item(name=n, area=area, is_custom=False, is_system=True))

        session.commit()

        # Next invoice number
        _ensure_invoice_seq(session)
        session.commit()
    finally:
        session.close()


def _ensure_invoice_seq(session: Session) -> None:
    """Seed the invoice sequence so prefix-NNNN starts cleanly."""
    inv = session.query(Invoice).order_by(Invoice.id.desc()).first()
    current = 0
    if inv and inv.invoice_number:
        try:
            current = int(str(inv.invoice_number).rsplit("-", 1)[-1])
        except ValueError:
            current = 0
    if not session.query(Setting).filter_by(key="invoice_seq").first():
        session.add(Setting(key="invoice_seq", value=str(current)))


def init_app_data() -> None:
    """Call once at startup."""
    create_all()
    seed_default_data()
