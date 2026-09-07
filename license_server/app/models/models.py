"""Database ORM models for the license server.

These are entirely separate from the client's business models.
The server stores ONLY licensing metadata — never customer billing data.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Customer(Base):
    """A purchasing customer (licensing metadata only)."""

    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    mobile: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(150))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    licenses: Mapped[list[License]] = relationship(
        back_populates="customer", cascade="all, delete-orphan"
    )


class License(Base):
    __tablename__ = "licenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    license_key: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    license_key_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    customer_id: Mapped[int] = mapped_column(
        ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product: Mapped[str] = mapped_column(String(50), default="furniture_bill", index=True)
    license_type: Mapped[str] = mapped_column(String(20), default="LIFETIME")
    device_limit: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", index=True)  # ACTIVE/REVOKED/BLOCKED
    current_device: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)  # hashed device fingerprint
    device_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    features_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    customer: Mapped[Customer] = relationship(back_populates="licenses")
    activation_log: Mapped[list[ActivationLog]] = relationship(
        back_populates="license", cascade="all, delete-orphan", order_by="desc(ActivationLog.id)"
    )

    @property
    def current_device_id(self) -> str | None:
        return self.current_device

    @property
    def product_id(self) -> str:
        return self.product

    @product_id.setter
    def product_id(self, val: str) -> None:
        self.product = val

    @property
    def customer_name(self) -> str:
        return self.customer.name if self.customer else ""


class ActivationLog(Base):
    __tablename__ = "activation_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    license_id: Mapped[int] = mapped_column(
        ForeignKey("licenses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    device_fingerprint: Mapped[str | None] = mapped_column(String(64), nullable=True)
    action: Mapped[str] = mapped_column(String(30))  # ACTIVATE/DEACTIVATE/RESET_DEVICE/REVOKE/BLOCK/REACTIVATE/CREATE
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    detail: Mapped[str | None] = mapped_column(String(300), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)

    license: Mapped[License] = relationship(back_populates="activation_log")
