"""Dashboard aggregation service — optimized for speed.

Uses batched SQL queries (single session), subqueries to reduce
round-trips, and in-memory caching so the dashboard loads fast even
with large datasets.

Performance improvements:
  - Multiple aggregation queries combined into a single session
  - Subqueries for paid/pending counts avoid a second full scan
  - Selective cache TTLs: stats=60s, charts=120s, lists=30s
  - selectinload for related objects avoids N+1 queries
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func
from sqlalchemy.orm import joinedload, selectinload

from app.database.database import get_session
from app.models.models import Customer, Invoice, Payment
from app.utils.cache import cache


def _today() -> date:
    return datetime.now(tz=timezone.utc).date()


def dashboard_stats() -> dict:
    """Compute all dashboard stats in a single DB session with minimal queries."""
    # Check cache first (60s TTL — stats are aggregated, short delay is fine)
    cached_stats = cache.get("dashboard_stats")
    if cached_stats is not None:
        return cached_stats

    session = get_session()
    try:
        today = _today()
        month_start = today.replace(day=1)

        # Use separate count queries to avoid a Cartesian product.
        # A single SELECT across two un-joined tables inflates counts
        # (customers × invoices) which is incorrect.
        total_customers = session.query(func.count(Customer.id)).scalar() or 0
        total_invoices = session.query(func.count(Invoice.id)).scalar() or 0

        total_income = session.query(
            func.coalesce(func.sum(Payment.amount), 0)).scalar() or 0
        today_income = session.query(
            func.coalesce(func.sum(Payment.amount), 0)).filter(
            Payment.date == today).scalar() or 0
        monthly_income = session.query(
            func.coalesce(func.sum(Payment.amount), 0)).filter(
            Payment.date >= month_start).scalar() or 0

        total_billed = session.query(
            func.coalesce(func.sum(Invoice.grand_total), 0)).filter(
            Invoice.status != "DRAFT").scalar() or 0
        total_outstanding = max(float(total_billed) - float(total_income), 0)

        # --- Paid vs pending count (single JOIN query, no correlated subquery) ---
        # LEFT JOIN + GROUP BY is faster than a correlated subquery for
        # large datasets because SQLite can use a hash/group strategy.
        paid_pending_rows = (
            session.query(
                Invoice.id,
                Invoice.grand_total,
                func.coalesce(func.sum(Payment.amount), 0).label("paid"),
            )
            .outerjoin(Payment, Payment.invoice_id == Invoice.id)
            .filter(Invoice.status != "DRAFT")
            .group_by(Invoice.id)
            .all()
        )
        paid_count = sum(
            1 for r in paid_pending_rows
            if float(r.paid or 0) >= float(r.grand_total or 0)
        )
        pending_count = len(paid_pending_rows) - paid_count

        result = {
            "total_customers": total_customers,
            "total_invoices": total_invoices,
            "today_income": float(today_income),
            "monthly_income": float(monthly_income),
            "total_income": float(total_income),
            "total_outstanding": total_outstanding,
            "paid_invoices": paid_count,
            "pending_invoices": pending_count,
        }
        # Cache for 60s — dashboard stats are aggregated and don't need instant freshness
        cache.set("dashboard_stats", result, ttl=60)
        return result
    finally:
        session.close()


def recent_invoices(limit: int = 6):
    """Fetch recent invoices with customer + payments in single query."""
    cache_key = f"recent_invoices:{limit}"
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return cached_data

    session = get_session()
    try:
        rows = (
            session.query(Invoice)
            .options(joinedload(Invoice.customer), selectinload(Invoice.payments))
            .order_by(Invoice.invoice_date.desc(), Invoice.id.desc())
            .limit(limit)
            .all()
        )
        result = [
            {
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "customer_name": inv.customer.name if inv.customer else None,
                "grand_total": float(inv.grand_total or 0),
                "paid": sum(float(p.amount or 0) for p in (inv.payments or [])),
                "invoice_date": inv.invoice_date,
                "due_date": inv.due_date,
                "status": inv.status,
            }
            for inv in rows
        ]
        cache.set(cache_key, result, ttl=30)  # 30s for lists
        return result
    finally:
        session.close()


def recent_payments(limit: int = 6):
    """Fetch recent payments with invoice in single query."""
    cache_key = f"recent_payments:{limit}"
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return cached_data

    session = get_session()
    try:
        rows = (
            session.query(Payment)
            .options(joinedload(Payment.invoice))
            .order_by(Payment.date.desc(), Payment.id.desc())
            .limit(limit)
            .all()
        )
        result = [
            {
                "id": p.id,
                "amount": float(p.amount or 0),
                "date": p.date,
                "mode": p.mode,
                "reference": p.reference,
                "invoice_number": p.invoice.invoice_number if p.invoice else None,
            }
            for p in rows
        ]
        cache.set(cache_key, result, ttl=30)
        return result
    finally:
        session.close()


def monthly_income_for_year(months: int = 12) -> list[dict]:
    """Return income summed per month for charting (cached)."""
    cache_key = f"monthly_income:{months}"
    cached_data = cache.get(cache_key)
    if cached_data is not None:
        return cached_data

    session = get_session()
    try:
        today = _today()
        start = (today.replace(day=1) - timedelta(days=365)) if months >= 12 else today.replace(day=1)
        rows = (
            session.query(
                func.strftime("%Y-%m", Payment.date).label("month"),
                func.sum(Payment.amount).label("total"),
            )
            .filter(Payment.date >= start)
            .group_by("month")
            .order_by("month")
            .all()
        )
        result = [{"month": r.month, "total": float(r.total or 0)} for r in rows]
        cache.set(cache_key, result, ttl=120)  # Chart data changes rarely
        return result
    finally:
        session.close()
