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
        total = round(float(inv.grand_total or 0), 2)
        paid = round(float(
            session.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(Payment.invoice_id == invoice_id)
            .scalar() or 0
        ), 2)
        outstanding = round(max(total - paid, 0.0), 2)
        amount_f = round(float(amount or 0), 2)
        if amount_f <= 0:
            raise ValueError("Payment amount must be greater than zero.")
        if amount_f > round(outstanding + 0.009, 2):
            raise ValueError(
                f"Cannot add \u20B9 {amount_f:,.2f}. "
                f"Outstanding balance is only \u20B9 {outstanding:,.2f}."
            )
        actual_amount = min(amount_f, outstanding)
        p = Payment(
            invoice_id=invoice_id,
            amount=actual_amount,
            date=date_value or datetime.now(tz=timezone.utc).date(),
            mode=mode,
            reference=reference,
            notes=notes,
        )
        session.add(p)
        new_paid = round(paid + actual_amount, 2)
        if inv.status != "DRAFT":
            if new_paid >= total - 0.009:
                inv.status = "PAID"
            elif new_paid > 0:
                inv.status = "PARTIALLY PAID"
            else:
                inv.status = "UNPAID"
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


def settle_invoice_full(invoice_id: int, mode="Cash", reference="Full Settlement", notes="") -> Payment:
    """Convenience method to settle an invoice's entire outstanding balance in one step."""
    session = get_session()
    try:
        inv = session.get(Invoice, invoice_id)
        if inv is None:
            raise ValueError("Invoice not found")
        total = round(float(inv.grand_total or 0), 2)
        paid = round(float(
            session.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(Payment.invoice_id == invoice_id)
            .scalar() or 0
        ), 2)
        outstanding = round(max(total - paid, 0.0), 2)
        if outstanding <= 0:
            raise ValueError("Invoice is already fully paid.")
    finally:
        session.close()
    return add_payment(invoice_id, outstanding, mode=mode, reference=reference, notes=notes)


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
        total = round(float(inv.grand_total or 0), 2) if inv else 0.0
        paid = round(float(
            session.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(Payment.invoice_id == invoice_id)
            .scalar() or 0
        ), 2)
        return {
            "total": total,
            "paid": paid,
            "outstanding": round(max(total - paid, 0.0), 2),
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
            session.flush()
            if inv and inv.status != "DRAFT":
                total = round(float(inv.grand_total or 0), 2)
                rem_paid = round(float(
                    session.query(func.coalesce(func.sum(Payment.amount), 0))
                    .filter(Payment.invoice_id == inv.id)
                    .scalar() or 0
                ), 2)
                if rem_paid >= total - 0.009 and total > 0:
                    inv.status = "PAID"
                elif rem_paid > 0:
                    inv.status = "PARTIALLY PAID"
                else:
                    inv.status = "UNPAID"
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


# Ergonomic aliases
record_payment = add_payment
list_payments = list_payments_for_invoice

