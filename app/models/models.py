"""SQLAlchemy models.

Every model belongs to the app's own isolated database. Business-profile
values are always read from the database, never hardcoded, so each business
keeps its own data.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    invoices = relationship("Invoice", back_populates="customer")


class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True)
    customer_id = Column(Integer, ForeignKey("customers.id"), index=True)
    name = Column(String(150), nullable=False)
    site_address = Column(Text)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    customer = relationship("Customer")
    invoices = relationship("Invoice", back_populates="project")


class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False, index=True)
    area = Column(String(60), index=True)
    is_custom = Column(Boolean, default=True)
    is_system = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Area(Base):
    __tablename__ = "areas"
    id = Column(Integer, primary_key=True)
    name = Column(String(60), unique=True, nullable=False, index=True)
    is_system = Column(Boolean, default=False)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


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
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

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
    created_at = Column(DateTime, default=datetime.utcnow)

    invoice = relationship("Invoice", back_populates="payments")


class Setting(Base):
    __tablename__ = "settings"
    key = Column(String(120), primary_key=True)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


def _string_column(*args, **kwargs):
    return Column(String, *args, **kwargs)
