"""Lightweight database migration framework.

Tracks schema version using SQLite's PRAGMA user_version and a migrations
table. Each migration is a callable that runs DDL statements. Migrations
are idempotent and run in order on startup.

This is a simpler alternative to Alembic — perfect for a desktop app that
owns its own SQLite database.
"""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Engine


@dataclass
class Migration:
    version: int
    name: str
    up: Callable[[Engine], None]


# Registry of all migrations in order
_MIGRATIONS: list[Migration] = []


def _register(version: int, name: str):
    """Decorator to register a migration function."""
    def decorator(fn: Callable[[Engine], None]):
        _MIGRATIONS.append(Migration(version=version, name=name, up=fn))
        return fn
    return decorator


def get_current_version(engine: Engine) -> int:
    """Read the current schema version from user_version pragma."""
    with engine.connect() as conn:
        result = conn.execute(text("PRAGMA user_version"))
        return result.scalar() or 0


def get_applied_migrations(engine: Engine) -> list[str]:
    """Get list of applied migration names from the migrations table."""
    with engine.connect() as conn:
        # Ensure migrations table exists
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS _schema_migrations (
                version INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.commit()
        result = conn.execute(text("SELECT name FROM _schema_migrations ORDER BY version"))
        return [row[0] for row in result]


def run_migrations(engine: Engine) -> list[str]:
    """Run all pending migrations. Returns list of applied migration names."""
    applied = set(get_applied_migrations(engine))
    newly_applied = []

    for migration in sorted(_MIGRATIONS, key=lambda m: m.version):
        if migration.name in applied:
            continue

        # Run the migration
        migration.up(engine)

        # Record it
        with engine.connect() as conn:
            conn.execute(text(
                "INSERT INTO _schema_migrations (version, name) VALUES (:v, :n)"
            ), {"v": migration.version, "n": migration.name})
            conn.execute(text(f"PRAGMA user_version={migration.version}"))
            conn.commit()

        newly_applied.append(migration.name)

    return newly_applied


# ---------------------------------------------------------------------------
# Migrations
# ---------------------------------------------------------------------------

@_register(1, "add_gst_enabled_to_invoices")
def _m001_add_gst_enabled(engine: Engine):
    """Add gst_enabled column to invoices table."""
    with engine.connect() as conn:
        cols = [r[1] for r in conn.execute(text("PRAGMA table_info(invoices)"))]
        if "gst_enabled" not in cols:
            conn.execute(text(
                "ALTER TABLE invoices ADD COLUMN gst_enabled BOOLEAN DEFAULT 1 NOT NULL"
            ))
        conn.commit()


@_register(2, "add_cell_formatting_defaults")
def _m002_add_cell_formatting(engine: Engine):
    """Add cell formatting default columns to business_profile."""
    with engine.connect() as conn:
        bp_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(business_profile)"))]
        for col_name, col_type, default in [
            ("default_font_family", "VARCHAR(60)", "''"),
            ("default_font_size", "INTEGER", "13"),
            ("default_font_bold", "BOOLEAN", "0"),
            ("default_font_underline", "BOOLEAN", "0"),
        ]:
            if col_name not in bp_cols:
                conn.execute(text(
                    f"ALTER TABLE business_profile ADD COLUMN {col_name} {col_type} DEFAULT {default}"
                ))
        if "default_area_fonts" not in bp_cols:
            conn.execute(text(
                "ALTER TABLE business_profile ADD COLUMN default_area_fonts TEXT DEFAULT '{}'"
            ))
        conn.commit()


@_register(3, "add_invoice_numbering")
def _m003_add_invoice_numbering(engine: Engine):
    """Add invoice numbering format columns."""
    with engine.connect() as conn:
        bp_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(business_profile)"))]
        for col_name, col_type, default in [
            ("invoice_format", "VARCHAR(60)", "'PREFIX-SEQ'"),
            ("invoice_sequence_digits", "INTEGER", "4"),
            ("next_sequence_number", "INTEGER", "1"),
        ]:
            if col_name not in bp_cols:
                conn.execute(text(
                    f"ALTER TABLE business_profile ADD COLUMN {col_name} {col_type} DEFAULT {default}"
                ))
        conn.commit()


@_register(4, "add_pdf_customization")
def _m004_add_pdf_customization(engine: Engine):
    """Add PDF/print customization columns."""
    with engine.connect() as conn:
        bp_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(business_profile)"))]
        for col_name, col_type, default in [
            ("pdf_paper_size", "VARCHAR(10)", "'A4'"),
            ("pdf_margin_top", "NUMERIC(4,1)", "15.0"),
            ("pdf_margin_bottom", "NUMERIC(4,1)", "15.0"),
            ("pdf_margin_left", "NUMERIC(4,1)", "15.0"),
            ("pdf_margin_right", "NUMERIC(4,1)", "15.0"),
            ("pdf_primary_color", "VARCHAR(12)", "''"),
            ("pdf_secondary_color", "VARCHAR(12)", "''"),
            ("pdf_theme", "VARCHAR(30)", "'colour'"),
        ]:
            if col_name not in bp_cols:
                conn.execute(text(
                    f"ALTER TABLE business_profile ADD COLUMN {col_name} {col_type} DEFAULT {default}"
                ))
        conn.commit()


@_register(5, "add_performance_indexes")
def _m005_add_indexes(engine: Engine):
    """Create composite indexes for hot query paths."""
    indexes = [
        "CREATE INDEX IF NOT EXISTS ix_invoices_cust_status ON invoices(customer_id, status)",
        "CREATE INDEX IF NOT EXISTS ix_invoices_date_id ON invoices(invoice_date DESC, id DESC)",
        "CREATE INDEX IF NOT EXISTS ix_payments_invoice_date ON payments(invoice_id, date)",
        "CREATE INDEX IF NOT EXISTS ix_payments_date_id ON payments(date DESC, id DESC)",
        "CREATE INDEX IF NOT EXISTS ix_items_area_name ON items(area, name)",
        "CREATE INDEX IF NOT EXISTS ix_invoice_items_inv_sort ON invoice_items(invoice_id, sort_order)",
        "CREATE INDEX IF NOT EXISTS ix_settings_key ON settings(key)",
    ]
    with engine.connect() as conn:
        for stmt in indexes:
            conn.execute(text(stmt))
        conn.commit()
