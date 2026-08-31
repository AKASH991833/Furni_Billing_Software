"""Reports service using aggregation queries."""
from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy import func

from app.database.database import get_session
from app.models.models import Customer, Invoice, Payment
from sqlalchemy.orm import joinedload


def date_filter_sql(start: date | None, end: date | None):
    """Return (filter_exprs: list) snippet helpers."""
    return {"start": start, "end": end}


def _date_range(period: str, start=None, end=None):
    today = date.today()
    if period == "today":
        return today, today
    if period == "week":
        monday = today - timedelta(days=today.weekday())
        return monday, today
    if period == "month":
        return today.replace(day=1), today
    if period == "year":
        return today.replace(month=1, day=1), today
    if period == "custom":
        return start, end
    return None, None


def income_summary(period="today", start=None, end=None) -> dict:
    s, e = _date_range(period, start, end)
    session = get_session()
    try:
        q = session.query(
            func.coalesce(func.sum(Payment.amount), 0),
            func.count(Payment.id),
        )
        if s:
            q = q.filter(Payment.date >= s)
        if e:
            q = q.filter(Payment.date <= e)
        income, count = q.one()
        return {"income": float(income or 0), "payment_count": count or 0, "start": s, "end": e}
    finally:
        session.close()


def totals_overview() -> dict:
    session = get_session()
    try:
        total_income = session.query(func.coalesce(func.sum(Payment.amount), 0)).scalar() or 0
        total_billed = (
            session.query(func.coalesce(func.sum(Invoice.grand_total), 0))
            .filter(Invoice.status != "DRAFT")
            .scalar() or 0
        )
        invoice_count = session.query(func.count(Invoice.id)).filter(Invoice.status != "DRAFT").scalar() or 0
        customer_count = session.query(func.count(Customer.id)).scalar() or 0
        return {
            "total_income": float(total_income or 0),
            "total_outstanding": float(max(total_billed - total_income, 0)),
            "invoice_count": invoice_count,
            "customer_count": customer_count,
            "total_billed": float(total_billed or 0),
        }
    finally:
        session.close()


def payment_history(limit=200):
    session = get_session()
    try:
        return (
            session.query(Payment)
            .join(Invoice)
            .options(joinedload(Payment.invoice))
            .order_by(Payment.date.desc(), Payment.id.desc())
            .limit(limit)
            .all()
        )
    finally:
        session.close()


def monthly_income(months=12) -> list[dict]:
    session = get_session()
    try:
        today = date.today()
        start = (today.replace(day=1) - timedelta(days=365)) if months >= 12 else today.replace(day=1)
        rows = (
            session.query(
                func.strftime("%Y-%m", Payment.date).label("month"),
                func.coalesce(func.sum(Payment.amount), 0).label("total"),
            )
            .filter(Payment.date >= start)
            .group_by("month")
            .order_by("month")
            .all()
        )
        return [{"month": r.month, "total": float(r[1])} for r in rows]
    finally:
        session.close()
