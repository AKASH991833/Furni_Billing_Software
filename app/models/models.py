"""SQLAlchemy models.

Every model belongs to the app's own isolated database. Business-profile
values are always read from the database, never hardcoded, so each business
keeps its own data.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(120))
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))


class BusinessProfile(Base):
    __tablename__ = "business_profile"
    id = Column(Integer, primary_key=True)
    business_name = Column(String(200), nullable=False)
    owner_name = Column(String(120))
    business_type = Column(String(120))
    mobile = Column(String(30))
    alternate_mobile = Column(String(30))
    email = Column(String(120))
    address = Column(Text)
    city = Column(String(80))
    state = Column(String(80))
    pincode = Column(String(20))
    gstin = Column(String(30))
    invoice_prefix = Column(String(20), default="INV")
    logo_path = Column(String(500))
    terms_conditions = Column(Text)
    signature_path = Column(String(500))
    show_gst = Column(Boolean, default=True)
    default_gst_rate = Column(Numeric(5, 2), default=18.0)
    currency = Column(String(10), default="₹")
    # Invoice cell formatting defaults
    default_font_family = Column(String(60), default="")
    default_font_size = Column(Integer, default=13)
    default_font_bold = Column(Boolean, default=False)
    default_font_underline = Column(Boolean, default=False)
    # Per-area font overrides (JSON): {"HALL": {"font_family": "Arial", ...}, ...}
    default_area_fonts = Column(Text, default="{}")
    # Invoice numbering format
    invoice_format = Column(String(60), default="PREFIX-SEQ")  # e.g. PREFIX-SEQ, PREFIX-YEAR-SEQ, PREFIX-SEQ-YEAR
    invoice_sequence_digits = Column(Integer, default=4)         # zero-pad width: 4 → 0001
    next_sequence_number = Column(Integer, default=1)            # manual reset point
    # PDF / print customization
    pdf_paper_size = Column(String(10), default="A4")           # A4, A5, LETTER
    pdf_margin_top = Column(Numeric(4, 1), default=15.0)        # mm
    pdf_margin_bottom = Column(Numeric(4, 1), default=15.0)
    pdf_margin_left = Column(Numeric(4, 1), default=15.0)
    pdf_margin_right = Column(Numeric(4, 1), default=15.0)
    pdf_primary_color = Column(String(12), default="")          # hex like #173560; empty = theme default
    pdf_secondary_color = Column(String(12), default="")        # hex like #C8A24B; empty = theme default
    pdf_theme = Column(String(30), default="colour")           # colour, classic, modern, minimal, elegant
    # Bank & UPI Details
    bank_name = Column(String(120), default="")
    account_number = Column(String(60), default="")
    ifsc_code = Column(String(30), default="")
    account_holder = Column(String(120), default="")
    upi_id = Column(String(100), default="")
    upi_qr_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))


class Customer(Base):
    __tablename__ = "customers"
    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False, index=True)
    mobile = Column(String(30), index=True)
    alternate_mobile = Column(String(30))
    email = Column(String(120))
    address = Column(Text)
    city = Column(String(80))
    state = Column(String(80))
    gstin = Column(String(30))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    invoices = relationship("Invoice", back_populates="customer")


class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), index=True)
    name = Column(String(150), nullable=False)
    site_address = Column(Text)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    customer = relationship("Customer")
    invoices = relationship("Invoice", back_populates="project")


class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False, index=True)
    area = Column(String(60), index=True)
    is_custom = Column(Boolean, default=True)
    is_system = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class Area(Base):
    __tablename__ = "areas"
    id = Column(Integer, primary_key=True)
    name = Column(String(60), unique=True, nullable=False, index=True)
    is_system = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))


class Invoice(Base):
    __tablename__ = "invoices"
    id = Column(Integer, primary_key=True)
    invoice_number = Column(String(60), nullable=False, index=True, unique=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True, index=True)
    invoice_date = Column(Date, nullable=False, index=True)
    due_date = Column(Date, nullable=True)
    site_address = Column(Text)
    status = Column(String(20), default="DRAFT", index=True)  # DRAFT / SAVED
    subtotal = Column(Numeric(14, 2), default=0)
    discount = Column(Numeric(14, 2), default=0)
    gst_enabled = Column(Boolean, default=True, server_default="1")
    gst_rate = Column(Numeric(5, 2), default=0)
    gst_amount = Column(Numeric(14, 2), default=0)
    grand_total = Column(Numeric(14, 2), default=0)
    amount_in_words = Column(String(500))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    customer = relationship("Customer", back_populates="invoices")
    project = relationship("Project", back_populates="invoices")
    items = relationship(
        "InvoiceItem", back_populates="invoice", order_by="InvoiceItem.sort_order",
        cascade="all, delete-orphan",
    )
    payments = relationship(
        "Payment", back_populates="invoice", cascade="all, delete-orphan"
    )


class InvoiceItem(Base):
    __tablename__ = "invoice_items"
    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), index=True)
    area = Column(String(60), index=True)
    description = Column(String(300))
    size = Column(String(60))
    qty_raw = Column(Text)          # preserve LS / 10.5 / etc.
    rate_raw = Column(Text)         # preserve LS / 800 / etc.
    qty = Column(Numeric(12, 3), nullable=True)
    rate = Column(Numeric(12, 2), nullable=True)
    amount = Column(Numeric(14, 2), nullable=True)
    sort_order = Column(Integer, default=0)

    invoice = relationship("Invoice", back_populates="items")

    @property
    def is_ls(self) -> bool:
        return _is_num(self.qty) is False or _is_num(self.rate) is False


def _is_num(v) -> bool:
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


class Payment(Base):
    __tablename__ = "payments"
    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"), index=True)
    amount = Column(Numeric(14, 2), nullable=False)
    date = Column(Date, nullable=False, index=True)
    mode = Column(String(30), default="Cash")
    reference = Column(String(120))
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    invoice = relationship("Invoice", back_populates="payments")


class Setting(Base):
    __tablename__ = "settings"
    key = Column(String(120), primary_key=True)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))


class Worker(Base):
    """Staff/Worker entity (Mistri, Carpenter, Labour, Helper, etc.)."""
    __tablename__ = "workers"

    id = Column(Integer, primary_key=True)
    worker_code = Column(String(30), unique=True, nullable=False, index=True)
    name = Column(String(150), nullable=False, index=True)
    mobile = Column(String(30), index=True)
    work_type = Column(String(80), default="Mistri", index=True)
    daily_rate = Column(Numeric(10, 2), default=0.0)
    joining_date = Column(Date, default=datetime.now(timezone.utc).date)
    address = Column(Text, default="")
    is_active = Column(Boolean, default=True, index=True)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    attendances = relationship("WorkerAttendance", back_populates="worker", cascade="all, delete-orphan")
    expenses = relationship("WorkerExpense", back_populates="worker", cascade="all, delete-orphan")
    adjustments = relationship("WorkerAdjustment", back_populates="worker", cascade="all, delete-orphan")
    advances = relationship("WorkerAdvance", back_populates="worker", cascade="all, delete-orphan")
    settlements = relationship("WorkerSettlement", back_populates="worker", cascade="all, delete-orphan")


class WorkerAttendance(Base):
    """Daily attendance entry with preserved rate and calculated earning.
    
    Guarantees:
      - (worker_id, attendance_date) is unique in DB.
      - daily_rate is frozen at recording time to preserve rate history.
      - daily_earning = daily_rate * day_multiplier.
    """
    __tablename__ = "worker_attendance"

    id = Column(Integer, primary_key=True)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False, index=True)
    attendance_date = Column(Date, nullable=False, index=True)
    day_multiplier = Column(Numeric(4, 2), default=1.0)
    status_label = Column(String(30), default="Full Day")
    daily_rate = Column(Numeric(10, 2), nullable=False)
    daily_earning = Column(Numeric(12, 2), nullable=False)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    __table_args__ = (
        UniqueConstraint("worker_id", "attendance_date", name="uq_worker_attendance_date"),
    )

    worker = relationship("Worker", back_populates="attendances")


class WorkerExpense(Base):
    """Travel / Rickshaw / Site expenses incurred by worker (added to gross payable)."""
    __tablename__ = "worker_expenses"

    id = Column(Integer, primary_key=True)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False, index=True)
    expense_date = Column(Date, nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    category = Column(String(60), default="Rickshaw")
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    worker = relationship("Worker", back_populates="expenses")


class WorkerAdjustment(Base):
    """Other additions (Bonus, Food) or deductions (Penalty) explicitly separated."""
    __tablename__ = "worker_adjustments"

    id = Column(Integer, primary_key=True)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False, index=True)
    adjustment_date = Column(Date, nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    adjustment_type = Column(String(20), nullable=False)  # ADDITION or DEDUCTION
    category = Column(String(60), default="Bonus")
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    worker = relationship("Worker", back_populates="adjustments")


class WorkerAdvance(Base):
    """Advance payment taken by worker (deducted from settlement, history preserved)."""
    __tablename__ = "worker_advances"

    id = Column(Integer, primary_key=True)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False, index=True)
    advance_date = Column(Date, nullable=False, index=True)
    amount = Column(Numeric(12, 2), nullable=False)
    payment_method = Column(String(30), default="Cash")
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))

    worker = relationship("Worker", back_populates="advances")


class WorkerSettlement(Base):
    """Monthly settlement record preserving calculation snapshot and payment status."""
    __tablename__ = "worker_settlements"

    id = Column(Integer, primary_key=True)
    worker_id = Column(Integer, ForeignKey("workers.id"), nullable=False, index=True)
    month_year = Column(String(10), nullable=False, index=True)  # e.g. "2026-09"
    total_units = Column(Numeric(6, 2), default=0)
    total_work_earning = Column(Numeric(12, 2), default=0)
    total_travel = Column(Numeric(12, 2), default=0)
    total_additions = Column(Numeric(12, 2), default=0)
    gross_payable = Column(Numeric(12, 2), default=0)
    total_advances = Column(Numeric(12, 2), default=0)
    total_deductions = Column(Numeric(12, 2), default=0)
    net_payable = Column(Numeric(12, 2), default=0)
    paid_amount = Column(Numeric(12, 2), default=0)
    voucher_no = Column(String(30), nullable=True, index=True)
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    payment_date = Column(Date, nullable=True)
    payment_method = Column(String(30), default="Cash")
    is_settled = Column(Boolean, default=True)
    notes = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=datetime.now(timezone.utc), onupdate=datetime.now(timezone.utc))

    worker = relationship("Worker", back_populates="settlements")



