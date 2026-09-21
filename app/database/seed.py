"""Startup initialisation: create tables and seed default (editable) data.

Default data is only used for development convenience. All of it can be
edited by the user from within the application, and nothing is hardcoded
for a real business.

Performance: composite indexes are created for the most common query
patterns (invoice lookups by customer/status, payment lookups by
invoice, etc.).
"""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.database.database import get_engine, get_session
from app.models.models import (
    Area,
    Base,
    BusinessProfile,
    Invoice,
    Item,
    Setting,
    User,
)

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
    # Run tracked migrations for any schema changes
    from app.database.migrations import run_migrations
    run_migrations(get_engine())


def _migrate_schema() -> None:
    """Add columns introduced after the original schema was created.

    ``create_all`` does not alter existing tables, so lightweight additive
    migrations live here. Only additive, non-destructive changes are allowed.
    """
    engine = get_engine()
    from sqlalchemy import text
    with engine.connect() as conn:
        # --- Invoice GST columns ---
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info(invoices)"))]
        if "gst_enabled" not in cols:
            conn.execute(
                text("ALTER TABLE invoices ADD COLUMN gst_enabled BOOLEAN DEFAULT 1 NOT NULL")
            )

        # --- Invoice cell formatting defaults ---
        bp_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(business_profile)"))]
        for col_name, col_type, default in [
            ("default_font_family", "VARCHAR(60)", "''"),
            ("default_font_size", "INTEGER", '13'),
            ("default_font_bold", "BOOLEAN", '0'),
            ("default_font_underline", "BOOLEAN", '0'),
        ]:
            if col_name not in bp_cols:
                conn.execute(text(
                    f"ALTER TABLE business_profile ADD COLUMN {col_name} {col_type} DEFAULT {default}"
                ))
        # Per-area font overrides (JSON text)
        if "default_area_fonts" not in bp_cols:
            conn.execute(text(
                "ALTER TABLE business_profile ADD COLUMN default_area_fonts TEXT DEFAULT '{}'"
            ))
        # Invoice numbering format
        for col_name, col_type, default in [
            ("invoice_format", "VARCHAR(60)", "'PREFIX-SEQ'"),
            ("invoice_sequence_digits", "INTEGER", '4'),
            ("next_sequence_number", "INTEGER", '1'),
        ]:
            if col_name not in bp_cols:
                conn.execute(text(
                    f"ALTER TABLE business_profile ADD COLUMN {col_name} {col_type} DEFAULT {default}"
                ))
        # PDF / print customization
        for col_name, col_type, default in [
            ("pdf_paper_size", "VARCHAR(10)", "'A4'"),
            ("pdf_margin_top", "NUMERIC(4,1)", '15.0'),
            ("pdf_margin_bottom", "NUMERIC(4,1)", '15.0'),
            ("pdf_margin_left", "NUMERIC(4,1)", '15.0'),
            ("pdf_margin_right", "NUMERIC(4,1)", '15.0'),
            ("pdf_primary_color", "VARCHAR(12)", "''"),
            ("pdf_secondary_color", "VARCHAR(12)", "''"),
            ("pdf_theme", "VARCHAR(30)", "'colour'"),
            ("bank_name", "VARCHAR(120)", "''"),
            ("account_number", "VARCHAR(60)", "''"),
            ("ifsc_code", "VARCHAR(30)", "''"),
            ("account_holder", "VARCHAR(120)", "''"),
            ("upi_id", "VARCHAR(100)", "''"),
            ("upi_qr_enabled", "BOOLEAN", "1"),
        ]:
            if col_name not in bp_cols:
                conn.execute(text(
                    f"ALTER TABLE business_profile ADD COLUMN {col_name} {col_type} DEFAULT {default}"
                ))
        # --- Worker Settlement date-range & voucher columns ---
        ws_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(worker_settlements)"))]
        for col_name, col_type in [
            ("voucher_no", "VARCHAR(30)"),
            ("start_date", "DATE"),
            ("end_date", "DATE"),
        ]:
            if col_name not in ws_cols:
                conn.execute(text(f"ALTER TABLE worker_settlements ADD COLUMN {col_name} {col_type}"))

        conn.commit()


def _create_performance_indexes() -> None:
    """Create composite indexes for hot query paths.

    These are created with IF NOT EXISTS so they're safe to call on every
    startup.  The indexes target the most common read patterns:
      - invoices filtered by customer + status (customer page, dashboard)
      - invoices ordered by date (list views, search)
      - payments filtered by invoice (payment list, summaries)
      - payments ordered by date (recent payments, reports)
      - items filtered by area (item suggestions, catalog)
    """
    engine = get_engine()
    from sqlalchemy import text
    indexes = [
        # invoices: customer_id + status (customer totals, dashboard pending)
        "CREATE INDEX IF NOT EXISTS ix_invoices_cust_status ON invoices(customer_id, status)",
        # invoices: date ordering (list views, search)
        "CREATE INDEX IF NOT EXISTS ix_invoices_date_id ON invoices(invoice_date DESC, id DESC)",
        # payments: invoice_id + date (per-invoice payment list, summaries)
        "CREATE INDEX IF NOT EXISTS ix_payments_invoice_date ON payments(invoice_id, date)",
        # payments: date ordering (recent payments, reports)
        "CREATE INDEX IF NOT EXISTS ix_payments_date_id ON payments(date DESC, id DESC)",
        # items: area + name (item suggestions, catalog lookup)
        "CREATE INDEX IF NOT EXISTS ix_items_area_name ON items(area, name)",
        # invoice_items: invoice_id + sort_order (line item loading)
        "CREATE INDEX IF NOT EXISTS ix_invoice_items_inv_sort ON invoice_items(invoice_id, sort_order)",
        # settings: key lookups (invoice_seq, setup_done)
        "CREATE INDEX IF NOT EXISTS ix_settings_key ON settings(key)",
    ]
    with engine.connect() as conn:
        for stmt in indexes:
            conn.execute(text(stmt))
        conn.commit()


def seed_default_data() -> None:
    session: Session = get_session()
    try:
        if session.query(User).count() == 0:
            from app.services.auth_service import _hash_pin
            session.add(User(
                username="admin",
                password_hash=_hash_pin("1234"),
                full_name="Administrator",
            ))
        else:
            # Ensure admin has a PIN set (handles upgrade from old DB)
            admin = session.query(User).filter_by(username="admin").first()
            if admin and not admin.password_hash:
                from app.services.auth_service import _hash_pin
                admin.password_hash = _hash_pin("1234")

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
