"""Tests for payment_service — add, delete, summary, outstanding guard.

Run with:  python -m pytest tests/test_payment_service.py -q
"""
import itertools
from datetime import date

import pytest

from app.models.models import Customer, Invoice, Payment

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_counter = itertools.count(1)


def _add_customer(session, name="PayCust"):
    c = Customer(name=name, mobile="9000000000")
    session.add(c)
    session.commit()
    return c


def _add_invoice(session, customer_id, grand_total=1000.0):
    seq = next(_counter)
    inv = Invoice(
        invoice_number=f"PAY-INV-{seq:04d}",
        customer_id=customer_id,
        invoice_date=date.today(),
        status="SAVED",
        grand_total=grand_total,
        subtotal=grand_total,
        gst_enabled=False,
        gst_rate=0,
        gst_amount=0,
        amount_in_words="test",
    )
    session.add(inv)
    session.commit()
    return inv


# ---------------------------------------------------------------------------
# add_payment — happy path
# ---------------------------------------------------------------------------

class TestAddPayment:
    def test_add_payment(self, db):
        c = _add_customer(db)
        inv = _add_invoice(db, c.id, grand_total=5000)
        from app.services.payment_service import add_payment
        p = add_payment(inv.id, 2000, date_value=date.today(), mode="Cash")
        assert p.amount == 2000
        assert p.mode == "Cash"

    def test_add_multiple_payments(self, db):
        c = _add_customer(db)
        inv = _add_invoice(db, c.id, grand_total=5000)
        from app.services.payment_service import add_payment
        add_payment(inv.id, 1000, mode="Cash")
        add_payment(inv.id, 2000, mode="UPI")
        add_payment(inv.id, 2000, mode="Card")
        from app.services.payment_service import list_payments_for_invoice
        payments = list_payments_for_invoice(inv.id)
        assert len(payments) == 3

    def test_add_payment_full_amount(self, db):
        c = _add_customer(db)
        inv = _add_invoice(db, c.id, grand_total=3000)
        from app.services.payment_service import add_payment
        p = add_payment(inv.id, 3000)
        assert p.amount == 3000

    def test_add_payment_with_reference(self, db):
        c = _add_customer(db)
        inv = _add_invoice(db, c.id, grand_total=1000)
        from app.services.payment_service import add_payment
        p = add_payment(inv.id, 500, reference="Cheque-123", notes="Partial payment")
        assert p.reference == "Cheque-123"
        assert p.notes == "Partial payment"


# ---------------------------------------------------------------------------
# add_payment — outstanding balance guard
# ---------------------------------------------------------------------------

class TestPaymentGuard:
    def test_overpay_raises(self, db):
        c = _add_customer(db)
        inv = _add_invoice(db, c.id, grand_total=1000)
        from app.services.payment_service import add_payment
        with pytest.raises(ValueError, match="Outstanding balance"):
            add_payment(inv.id, 1500)

    def test_overpay_after_partial(self, db):
        c = _add_customer(db)
        inv = _add_invoice(db, c.id, grand_total=2000)
        from app.services.payment_service import add_payment
        add_payment(inv.id, 1000)
        with pytest.raises(ValueError, match="Outstanding balance"):
            add_payment(inv.id, 1500)

    def test_exact_outstanding_ok(self, db):
        c = _add_customer(db)
        inv = _add_invoice(db, c.id, grand_total=2000)
        from app.services.payment_service import add_payment
        add_payment(inv.id, 1000)
        p = add_payment(inv.id, 1000)
        assert p.amount == 1000

    def test_payment_to_nonexistent_invoice(self, db):
        from app.services.payment_service import add_payment
        with pytest.raises(ValueError, match="not found"):
            add_payment(99999, 100)


# ---------------------------------------------------------------------------
# invoice_payment_summary
# ---------------------------------------------------------------------------

class TestPaymentSummary:
    def test_no_payments(self, db):
        c = _add_customer(db)
        inv = _add_invoice(db, c.id, grand_total=5000)
        from app.services.payment_service import invoice_payment_summary
        s = invoice_payment_summary(inv.id)
        assert s["total"] == 5000.0
        assert s["paid"] == 0.0
        assert s["outstanding"] == 5000.0

    def test_partial_payments(self, db):
        c = _add_customer(db)
        inv = _add_invoice(db, c.id, grand_total=5000)
        from app.services.payment_service import add_payment, invoice_payment_summary
        add_payment(inv.id, 2000)
        add_payment(inv.id, 1000)
        s = invoice_payment_summary(inv.id)
        assert s["paid"] == 3000.0
        assert s["outstanding"] == 2000.0

    def test_fully_paid(self, db):
        c = _add_customer(db)
        inv = _add_invoice(db, c.id, grand_total=5000)
        from app.services.payment_service import add_payment, invoice_payment_summary
        add_payment(inv.id, 5000)
        s = invoice_payment_summary(inv.id)
        assert s["outstanding"] == 0.0


# ---------------------------------------------------------------------------
# delete_payment
# ---------------------------------------------------------------------------

class TestDeletePayment:
    def test_delete_existing(self, db):
        c = _add_customer(db)
        inv = _add_invoice(db, c.id, grand_total=1000)
        from app.services.payment_service import add_payment, delete_payment
        p = add_payment(inv.id, 500)
        assert delete_payment(p.id) is True
        from app.services.payment_service import list_payments_for_invoice
        assert len(list_payments_for_invoice(inv.id)) == 0

    def test_delete_nonexistent(self, db):
        from app.services.payment_service import delete_payment
        assert delete_payment(99999) is False

    def test_delete_restores_outstanding(self, db):
        c = _add_customer(db)
        inv = _add_invoice(db, c.id, grand_total=1000)
        from app.services.payment_service import add_payment, delete_payment, invoice_payment_summary
        p = add_payment(inv.id, 1000)
        s1 = invoice_payment_summary(inv.id)
        assert s1["outstanding"] == 0.0
        delete_payment(p.id)
        s2 = invoice_payment_summary(inv.id)
        assert s2["outstanding"] == 1000.0


# ---------------------------------------------------------------------------
# list_payments_for_invoice
# ---------------------------------------------------------------------------

class TestListPayments:
    def test_list_empty(self, db):
        c = _add_customer(db)
        inv = _add_invoice(db, c.id)
        from app.services.payment_service import list_payments_for_invoice
        assert list_payments_for_invoice(inv.id) == []

    def test_list_ordered_by_date(self, db):
        c = _add_customer(db)
        inv = _add_invoice(db, c.id, grand_total=5000)
        from app.services.payment_service import add_payment
        add_payment(inv.id, 100, date_value=date(2026, 1, 15))
        add_payment(inv.id, 200, date_value=date(2026, 3, 10))
        add_payment(inv.id, 300, date_value=date(2026, 2, 1))
        from app.services.payment_service import list_payments_for_invoice
        payments = list_payments_for_invoice(inv.id)
        dates = [p.date for p in payments]
        assert dates == sorted(dates)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
