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
                "INSERT OR REPLACE INTO _schema_migrations (version, name) VALUES (:v, :n)"
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


@_register(6, "add_bank_and_upi_details")
def _m006_add_bank_and_upi(engine: Engine):
    """Add bank account and UPI details to business_profile."""
    with engine.connect() as conn:
        bp_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(business_profile)"))]
        for col_name, col_type, default in [
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
        conn.commit()


@_register(7, "add_worker_attendance_and_payment_tables")
def _m007_add_worker_module(engine: Engine):
    """Create and align workers, attendance, expenses, adjustments, advances, and settlements tables."""
    ddls = [
        """
        CREATE TABLE IF NOT EXISTS workers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_code VARCHAR(30) NOT NULL,
            name VARCHAR(150) NOT NULL,
            mobile VARCHAR(30),
            work_type VARCHAR(80) DEFAULT 'Mistri',
            daily_rate NUMERIC(10, 2) DEFAULT 0.0,
            joining_date DATE,
            address TEXT DEFAULT '',
            is_active BOOLEAN DEFAULT 1,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS worker_attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER NOT NULL REFERENCES workers(id) ON DELETE CASCADE,
            attendance_date DATE NOT NULL,
            day_multiplier NUMERIC(4, 2) DEFAULT 1.0,
            status_label VARCHAR(30) DEFAULT 'Full Day',
            daily_rate NUMERIC(10, 2) NOT NULL,
            daily_earning NUMERIC(12, 2) NOT NULL,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS worker_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER NOT NULL REFERENCES workers(id) ON DELETE CASCADE,
            expense_date DATE NOT NULL,
            amount NUMERIC(12, 2) NOT NULL,
            category VARCHAR(60) DEFAULT 'Rickshaw',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS worker_adjustments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER NOT NULL REFERENCES workers(id) ON DELETE CASCADE,
            adjustment_date DATE NOT NULL,
            amount NUMERIC(12, 2) NOT NULL,
            adjustment_type VARCHAR(20) NOT NULL,
            category VARCHAR(60) DEFAULT 'Bonus',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS worker_advances (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER NOT NULL REFERENCES workers(id) ON DELETE CASCADE,
            advance_date DATE NOT NULL,
            amount NUMERIC(12, 2) NOT NULL,
            payment_method VARCHAR(30) DEFAULT 'Cash',
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS worker_settlements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            worker_id INTEGER NOT NULL REFERENCES workers(id) ON DELETE CASCADE,
            month_year VARCHAR(10) NOT NULL,
            total_units NUMERIC(6, 2) DEFAULT 0,
            total_work_earning NUMERIC(12, 2) DEFAULT 0,
            total_travel NUMERIC(12, 2) DEFAULT 0,
            total_additions NUMERIC(12, 2) DEFAULT 0,
            gross_payable NUMERIC(12, 2) DEFAULT 0,
            total_advances NUMERIC(12, 2) DEFAULT 0,
            total_deductions NUMERIC(12, 2) DEFAULT 0,
            net_payable NUMERIC(12, 2) DEFAULT 0,
            paid_amount NUMERIC(12, 2) DEFAULT 0,
            payment_date DATE,
            payment_method VARCHAR(30) DEFAULT 'Cash',
            is_settled BOOLEAN DEFAULT 1,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """,
    ]
    with engine.connect() as conn:
        for stmt in ddls:
            conn.execute(text(stmt.strip()))
        conn.commit()

        # Schema alignment for pre-existing tables if any
        # 1. workers
        w_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(workers)"))]
        if "worker_code" not in w_cols:
            conn.execute(text("ALTER TABLE workers ADD COLUMN worker_code VARCHAR(30)"))
        if "work_type" not in w_cols:
            conn.execute(text("ALTER TABLE workers ADD COLUMN work_type VARCHAR(80) DEFAULT 'Mistri'"))
        if "address" not in w_cols:
            conn.execute(text("ALTER TABLE workers ADD COLUMN address TEXT DEFAULT ''"))
        conn.execute(text(
            "UPDATE workers SET worker_code = 'W-' || substr('000' || id, -3, 3) WHERE worker_code IS NULL OR worker_code = ''"
        ))
        if "role" in w_cols:
            conn.execute(text(
                "UPDATE workers SET work_type = role WHERE (work_type IS NULL OR work_type = '') AND role IS NOT NULL"
            ))

        # 2. worker_attendance
        att_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(worker_attendance)"))]
        if "attendance_date" not in att_cols:
            conn.execute(text("ALTER TABLE worker_attendance ADD COLUMN attendance_date DATE"))
            if "date" in att_cols:
                conn.execute(text("UPDATE worker_attendance SET attendance_date = date WHERE attendance_date IS NULL"))
        if "day_multiplier" not in att_cols:
            conn.execute(text("ALTER TABLE worker_attendance ADD COLUMN day_multiplier NUMERIC(4, 2) DEFAULT 1.0"))
            if "day_value" in att_cols:
                conn.execute(text("UPDATE worker_attendance SET day_multiplier = day_value WHERE day_multiplier IS NULL"))
        if "status_label" not in att_cols:
            conn.execute(text("ALTER TABLE worker_attendance ADD COLUMN status_label VARCHAR(30) DEFAULT 'Full Day'"))
            conn.execute(text(
                "UPDATE worker_attendance SET status_label = CASE "
                "WHEN day_multiplier = 0 THEN 'Absent' "
                "WHEN day_multiplier = 0.5 THEN 'Half Day' "
                "WHEN day_multiplier = 1.5 THEN '1.5 Day' "
                "WHEN day_multiplier = 2.0 THEN 'Double Day' "
                "ELSE 'Full Day' END WHERE status_label IS NULL OR status_label = ''"
            ))
        if "daily_rate" not in att_cols:
            conn.execute(text("ALTER TABLE worker_attendance ADD COLUMN daily_rate NUMERIC(10, 2) DEFAULT 0.0"))
            conn.execute(text(
                "UPDATE worker_attendance SET daily_rate = (SELECT coalesce(workers.daily_rate, 0) FROM workers WHERE workers.id = worker_attendance.worker_id) WHERE daily_rate IS NULL OR daily_rate = 0"
            ))
        if "daily_earning" not in att_cols:
            conn.execute(text("ALTER TABLE worker_attendance ADD COLUMN daily_earning NUMERIC(12, 2) DEFAULT 0.0"))
            conn.execute(text(
                "UPDATE worker_attendance SET daily_earning = ROUND(daily_rate * day_multiplier, 2) WHERE daily_earning IS NULL OR daily_earning = 0"
            ))

        # 3. worker_advances
        adv_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(worker_advances)"))]
        if "advance_date" not in adv_cols:
            conn.execute(text("ALTER TABLE worker_advances ADD COLUMN advance_date DATE"))
            if "date" in adv_cols:
                conn.execute(text("UPDATE worker_advances SET advance_date = date WHERE advance_date IS NULL"))
        if "payment_method" not in adv_cols:
            conn.execute(text("ALTER TABLE worker_advances ADD COLUMN payment_method VARCHAR(30) DEFAULT 'Cash'"))
            if "payment_mode" in adv_cols:
                conn.execute(text("UPDATE worker_advances SET payment_method = payment_mode WHERE payment_method IS NULL OR payment_method = ''"))

        # 4. worker_expenses
        exp_cols = [r[1] for r in conn.execute(text("PRAGMA table_info(worker_expenses)"))]
        if "expense_date" not in exp_cols:
            conn.execute(text("ALTER TABLE worker_expenses ADD COLUMN expense_date DATE"))
            if "date" in exp_cols:
                conn.execute(text("UPDATE worker_expenses SET expense_date = date WHERE expense_date IS NULL"))

        # Indexes
        indexes = [
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_workers_worker_code ON workers(worker_code);",
            "CREATE INDEX IF NOT EXISTS ix_workers_name ON workers(name);",
            "CREATE INDEX IF NOT EXISTS ix_workers_mobile ON workers(mobile);",
            "CREATE INDEX IF NOT EXISTS ix_workers_work_type ON workers(work_type);",
            "CREATE INDEX IF NOT EXISTS ix_workers_is_active ON workers(is_active);",
            "CREATE UNIQUE INDEX IF NOT EXISTS ix_worker_att_worker_date ON worker_attendance(worker_id, attendance_date);",
            "CREATE INDEX IF NOT EXISTS ix_worker_attendance_worker_id ON worker_attendance(worker_id);",
            "CREATE INDEX IF NOT EXISTS ix_worker_attendance_date ON worker_attendance(attendance_date);",
            "CREATE INDEX IF NOT EXISTS ix_worker_expenses_worker_id ON worker_expenses(worker_id);",
            "CREATE INDEX IF NOT EXISTS ix_worker_expenses_date ON worker_expenses(expense_date);",
            "CREATE INDEX IF NOT EXISTS ix_worker_adjustments_worker_id ON worker_adjustments(worker_id);",
            "CREATE INDEX IF NOT EXISTS ix_worker_adjustments_date ON worker_adjustments(adjustment_date);",
            "CREATE INDEX IF NOT EXISTS ix_worker_advances_worker_id ON worker_advances(worker_id);",
            "CREATE INDEX IF NOT EXISTS ix_worker_advances_date ON worker_advances(advance_date);",
            "CREATE INDEX IF NOT EXISTS ix_worker_settlements_worker_id ON worker_settlements(worker_id);",
            "CREATE INDEX IF NOT EXISTS ix_worker_settlements_month_year ON worker_settlements(month_year);",
        ]
        for idx in indexes:
            conn.execute(text(idx))
        conn.commit()



