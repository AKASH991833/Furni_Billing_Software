"""Payment entry service."""
from __future__ import annotations

from datetime import date

from sqlalchemy import func

from app.database.database import get_session
from app.models.models import Invoice, Payment


def add_payment(invoice_id: int, amount, date_value=None, mode="Cash",
                reference="", notes="") -> Payment:
    session = get_session()
    try:
        p = Payment(
            invoice_id=invoice_id,
            amount=amount,
            date=date_value or date.today(),
            mode=mode,
            reference=reference,
            notes=notes,
        )
        session.add(p)
        session.commit()
        session.refresh(p)
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
        inv = session.query(Invoice).get(invoice_id)
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
        p = session.query(Payment).get(payment_id)
        if p:
            session.delete(p)
            session.commit()
            return True
        return False
    finally:
        session.close()
