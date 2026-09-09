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


def get_customers_with_summary(query: str = "", limit: int = 300) -> list[dict]:
    """Batch-fetch customers with their aggregated invoices, payments, and balances.

    Performs batched aggregation in 3 queries, completely avoiding N+1 overhead.
    """
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
                    Customer.city.ilike(pat),
                    Customer.gstin.ilike(pat),
                )
            )
        customers = q.order_by(Customer.name).limit(limit).all()

        # Batch query invoice totals grouped by customer_id
        inv_rows = (
            session.query(
                Invoice.customer_id,
                func.coalesce(func.sum(Invoice.grand_total), 0),
                func.count(Invoice.id),
            )
            .filter(Invoice.status != "DRAFT")
            .group_by(Invoice.customer_id)
            .all()
        )
        inv_map = {row[0]: (float(row[1]), int(row[2])) for row in inv_rows}

        # Batch query payment totals grouped by invoice.customer_id
        pay_rows = (
            session.query(
                Invoice.customer_id,
                func.coalesce(func.sum(Payment.amount), 0),
            )
            .join(Payment, Payment.invoice_id == Invoice.id)
            .filter(Invoice.status != "DRAFT")
            .group_by(Invoice.customer_id)
            .all()
        )
        pay_map = {row[0]: float(row[1]) for row in pay_rows}

        results = []
        for c in customers:
            inv_total, inv_count = inv_map.get(c.id, (0.0, 0))
            paid_total = pay_map.get(c.id, 0.0)
            due = max(inv_total - paid_total, 0.0)
            results.append({
                "id": c.id,
                "customer": c,
                "name": c.name or "Unnamed Client",
                "mobile": c.mobile or "-",
                "email": c.email or "-",
                "city": c.city or "-",
                "state": c.state or "-",
                "gstin": c.gstin or "",
                "total_invoiced": inv_total,
                "invoice_count": inv_count,
                "total_paid": paid_total,
                "outstanding": due,
                "is_settled": due <= 0.01,
                "has_gstin": bool(c.gstin and c.gstin.strip()),
            })
        return results
    finally:
        session.close()


def customers_kpi_overview() -> dict:
    """Directory-wide metrics: total clients, active, receivables, settled."""
    session = get_session()
    try:
        total_customers = session.query(func.count(Customer.id)).scalar() or 0

        # Total billed across non-draft invoices
        total_billed = (
            session.query(func.coalesce(func.sum(Invoice.grand_total), 0))
            .filter(Invoice.status != "DRAFT")
            .scalar() or 0
        )
        # Total collected across non-draft invoices
        total_paid = (
            session.query(func.coalesce(func.sum(Payment.amount), 0))
            .join(Invoice, Payment.invoice_id == Invoice.id)
            .filter(Invoice.status != "DRAFT")
            .scalar() or 0
        )
        receivables = max(float(total_billed) - float(total_paid), 0.0)

        # Clients with at least one non-draft invoice
        active_clients = (
            session.query(func.count(func.distinct(Invoice.customer_id)))
            .filter(Invoice.status != "DRAFT")
            .scalar() or 0
        )

        return {
            "total_customers": int(total_customers),
            "active_clients": int(active_clients),
            "total_receivables": float(receivables),
            "total_billed": float(total_billed),
            "total_paid": float(total_paid),
        }
    finally:
        session.close()

