"""Payment entry service."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func

from app.database.database import get_session
from app.models.models import Invoice, Payment
from app.utils.cache import cache


def add_payment(invoice_id: int, amount, date_value=None, mode="Cash",
                reference="", notes="") -> Payment:
    session = get_session()
    try:
        inv = session.get(Invoice, invoice_id)
        if inv is None:
            raise ValueError("Invoice not found")
        total = float(inv.grand_total or 0)
        paid = (
            session.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(Payment.invoice_id == invoice_id)
            .scalar() or 0
        )
        outstanding = total - float(paid)
        if float(amount) > outstanding:
            raise ValueError(
                f"Cannot add \u20B9 {float(amount):,.2f}. "
                f"Outstanding balance is only \u20B9 {max(outstanding, 0):,.2f}."
            )
        p = Payment(
            invoice_id=invoice_id,
            amount=amount,
            date=date_value or datetime.now(tz=timezone.utc).date(),
            mode=mode,
            reference=reference,
            notes=notes,
        )
        session.add(p)
        session.commit()
        session.refresh(p)
        cache.invalidate("dashboard_stats")
        cache.invalidate("report_totals")
        cache.invalidate_prefix("payment_history:")
        cache.invalidate_prefix("recent_")
        cache.invalidate_prefix("monthly_")
        # Invalidate customer totals cache for the invoice's customer
        if inv.customer_id:
            cache.invalidate(f"cust_totals:{inv.customer_id}")
        return p
    finally:
        session.close()


def list_payments_for_invoice(invoice_id: int) -> list[Payment]:
    session = get_session()
    try:
        return (
            session.query(Payment)
            .filter(Payment.invoice_id == invoice_id)
            .order_by(Payment.date)
            .all()
        )
    finally:
        session.close()


def invoice_payment_summary(invoice_id: int) -> dict:
    session = get_session()
    try:
        inv = session.get(Invoice, invoice_id)
        total = float(inv.grand_total or 0) if inv else 0
        paid = (
            session.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(Payment.invoice_id == invoice_id)
            .scalar() or 0
        )
        return {
            "total": total,
            "paid": float(paid),
            "outstanding": max(total - float(paid), 0),
        }
    finally:
        session.close()


def delete_payment(payment_id: int) -> bool:
    session = get_session()
    try:
        p = session.get(Payment, payment_id)
        if p:
            # Look up the customer_id before deleting to invalidate cache
            inv = session.get(Invoice, p.invoice_id)
            cust_id = inv.customer_id if inv else None
            session.delete(p)
            session.commit()
            cache.invalidate("dashboard_stats")
            cache.invalidate("report_totals")
            cache.invalidate_prefix("payment_history:")
            cache.invalidate_prefix("recent_")
            cache.invalidate_prefix("monthly_")
            if cust_id:
                cache.invalidate(f"cust_totals:{cust_id}")
            return True
        return False
    finally:
        session.close()
