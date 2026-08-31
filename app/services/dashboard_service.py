"""Dashboard aggregation service.

Uses indexed, aggregated SQL queries so the dashboard stays fast and does
not load entire tables into memory.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import joinedload, selectinload

from app.database.database import get_session
from app.models.models import Customer, Invoice, Payment


def _today() -> date:
    return date.today()


def dashboard_stats() -> dict:
    session = get_session()
    try:
        today = _today()

        total_customers = session.query(func.count(Customer.id)).scalar() or 0
        total_invoices = session.query(func.count(Invoice.id)).scalar() or 0

        total_income = (
            session.query(func.coalesce(func.sum(Payment.amount), 0))
            .scalar() or 0
        )

        today_income = (
            session.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(Payment.date == today)
            .scalar() or 0
        )

        month_start = today.replace(day=1)
        monthly_income = (
            session.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(Payment.date >= month_start)
            .scalar() or 0
        )

        total_billed = (
            session.query(func.coalesce(func.sum(Invoice.grand_total), 0))
            .filter(Invoice.status != "DRAFT")
            .scalar() or 0
        )

        total_outstanding = max(total_billed - total_income, 0)

        paid_invoices = (
            session.query(func.count(Invoice.id))
            .filter(Invoice.status != "DRAFT", Invoice.grand_total > 0)
            .all()
        )

        # Paid invoice count: invoices whose payments cover grand total
        from sqlalchemy import select
        paid_count = 0
        pending_count = 0
        sub = (
            select(
                Invoice.id,
                Invoice.grand_total,
                func.coalesce(func.sum(Payment.amount), 0).label("paid"),
            )
            .outerjoin(Payment, Payment.invoice_id == Invoice.id)
            .filter(Invoice.status != "DRAFT")
            .group_by(Invoice.id, Invoice.grand_total)
        )
        rows = session.execute(sub).all()
        for r in rows:
            if float(r.paid or 0) >= float(r.grand_total or 0):
                paid_count += 1
            else:
                pending_count += 1

        return {
            "total_customers": total_customers,
            "total_invoices": total_invoices,
            "today_income": today_income,
            "monthly_income": monthly_income,
            "total_income": total_income,
            "total_outstanding": total_outstanding,
            "paid_invoices": paid_count,
            "pending_invoices": pending_count,
        }
    finally:
        session.close()


def recent_invoices(limit: int = 6):
    session = get_session()
    try:
        return (
            session.query(Invoice)
            .options(joinedload(Invoice.customer), selectinload(Invoice.payments))
            .order_by(Invoice.invoice_date.desc(), Invoice.id.desc())
            .limit(limit)
            .all()
        )
    finally:
        session.close()


def recent_payments(limit: int = 6):
    session = get_session()
    try:
        return (
            session.query(Payment)
            .options(joinedload(Payment.invoice))
            .order_by(Payment.date.desc(), Payment.id.desc())
            .limit(limit)
            .all()
        )
    finally:
        session.close()


def monthly_income_for_year(months: int = 12) -> list[dict]:
    """Return income summed per month for charting (recent N months)."""
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
        return [{"month": r.month, "total": float(r.total or 0)} for r in rows]
    finally:
        session.close()
