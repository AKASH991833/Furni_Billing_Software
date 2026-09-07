"""Customer management service."""
from __future__ import annotations

from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload, selectinload

from app.database.database import get_session
from app.models.models import Customer, Invoice, Payment
from app.utils.cache import cache


def add_customer(data: dict) -> Customer:
    session = get_session()
    try:
        c = Customer(**data)
        session.add(c)
        session.commit()
        session.refresh(c)
        return c
    finally:
        session.close()


def update_customer(customer_id: int, data: dict) -> Customer:
    session = get_session()
    try:
        c = session.get(Customer, customer_id)
        if c:
            for k, v in data.items():
                setattr(c, k, v)
            session.commit()
        return c
    finally:
        session.close()


def delete_customer(customer_id: int) -> bool:
    session = get_session()
    try:
        c = session.get(Customer, customer_id)
        if c:
            session.delete(c)
            session.commit()
            cache.invalidate("dashboard_stats")
            cache.invalidate_prefix("recent_")
            cache.invalidate_prefix("monthly_")
            return True
        return False
    finally:
        session.close()


def get_customer(customer_id: int) -> Customer | None:
    session = get_session()
    try:
        return session.get(Customer, customer_id)
    finally:
        session.close()


def search_customers(query: str = "", limit: int = 200) -> list[Customer]:
    session = get_session()
    try:
        q = session.query(Customer)
        if query:
            pat = f"%{query}%"
            q = q.filter(
                or_(
                    Customer.name.ilike(pat),
                    Customer.mobile.ilike(pat),
                    Customer.email.ilike(pat),
                )
            )
        return q.order_by(Customer.name).limit(limit).all()
    finally:
        session.close()


def customer_invoices(customer_id: int) -> list[Invoice]:
    session = get_session()
    try:
        return (
            session.query(Invoice)
            .filter(Invoice.customer_id == customer_id)
            .options(selectinload(Invoice.payments))
            .order_by(Invoice.invoice_date.desc())
            .all()
        )
    finally:
        session.close()


def customer_totals(customer_id: int) -> dict:
    """Total invoiced, total paid, outstanding for a customer.

    Uses pure SQL aggregation — no objects loaded into Python.
    Results are cached for 30s to avoid repeated expensive queries.
    """
    cache_key = f"cust_totals:{customer_id}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached

    session = get_session()
    try:
        # Sum of all non-DRAFT invoice grand_totals for this customer
        total_invoiced = (
            session.query(func.coalesce(func.sum(Invoice.grand_total), 0))
            .filter(Invoice.customer_id == customer_id, Invoice.status != "DRAFT")
            .scalar() or 0
        )
        # Count of non-DRAFT invoices
        invoice_count = (
            session.query(func.count(Invoice.id))
            .filter(Invoice.customer_id == customer_id, Invoice.status != "DRAFT")
            .scalar() or 0
        )
        # Sum of all payments against this customer's invoices
        total_paid = (
            session.query(func.coalesce(func.sum(Payment.amount), 0))
            .join(Invoice, Payment.invoice_id == Invoice.id)
            .filter(Invoice.customer_id == customer_id, Invoice.status != "DRAFT")
            .scalar() or 0
        )
        total_invoiced_f = float(total_invoiced)
        total_paid_f = float(total_paid)
        result = {
            "total_invoiced": total_invoiced_f,
            "total_paid": total_paid_f,
            "outstanding": total_invoiced_f - total_paid_f,
            "invoice_count": int(invoice_count),
        }
        cache.set(cache_key, result, ttl=30)
        return result
    finally:
        session.close()


def customer_payments(customer_id: int) -> list[Payment]:
    session = get_session()
    try:
        return (
            session.query(Payment)
            .join(Invoice)
            .filter(Invoice.customer_id == customer_id)
            .options(joinedload(Payment.invoice))
            .order_by(Payment.date.desc())
            .all()
        )
    finally:
        session.close()
