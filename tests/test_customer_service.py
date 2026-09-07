"""Tests for customer_service — CRUD, search, totals, payments.

Run with:  python -m pytest tests/test_customer_service.py -q
"""
import itertools
from datetime import date

import pytest

from app.models.models import Customer, Invoice, InvoiceItem, Payment

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_counter = itertools.count(1)


def _add_customer(session, name="TestCust", mobile="9000000000"):
    c = Customer(name=name, mobile=mobile)
    session.add(c)
    session.commit()
    return c


def _add_invoice(session, customer_id, grand_total=1000.0, status="SAVED"):
    seq = next(_counter)
    inv = Invoice(
        invoice_number=f"CUST-INV-{seq:04d}",
        customer_id=customer_id,
        invoice_date=date.today(),
        status=status,
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
# add_customer
# ---------------------------------------------------------------------------

class TestAddCustomer:
    def test_add_customer(self, db):
        from app.services.customer_service import add_customer
        c = add_customer({"name": "New Customer", "mobile": "1234567890"})
        assert c.id is not None
        assert c.name == "New Customer"
        assert c.mobile == "1234567890"

    def test_add_customer_with_all_fields(self, db):
        from app.services.customer_service import add_customer
        c = add_customer({
            "name": "Full Customer",
            "mobile": "1111111111",
            "email": "test@example.com",
            "address": "123 Main St",
            "city": "Mumbai",
            "state": "MH",
            "gstin": "22AAAAA0000A1Z5",
        })
        assert c.email == "test@example.com"
        assert c.city == "Mumbai"


# ---------------------------------------------------------------------------
# get_customer / update_customer / delete_customer
# ---------------------------------------------------------------------------

class TestCRUD:
    def test_get_customer(self, db):
        c = _add_customer(db, "GetMe")
        from app.services.customer_service import get_customer
        fetched = get_customer(c.id)
        assert fetched is not None
        assert fetched.name == "GetMe"

    def test_get_nonexistent(self, db):
        from app.services.customer_service import get_customer
        assert get_customer(99999) is None

    def test_update_customer(self, db):
        c = _add_customer(db, "Old Name")
        from app.services.customer_service import update_customer, get_customer
        updated = update_customer(c.id, {"name": "New Name", "email": "a@b.com"})
        assert updated.name == "New Name"
        assert updated.email == "a@b.com"

    def test_delete_customer(self, db):
        c = _add_customer(db, "ToDelete")
        from app.services.customer_service import delete_customer, get_customer
        assert delete_customer(c.id) is True
        assert get_customer(c.id) is None

    def test_delete_nonexistent(self, db):
        from app.services.customer_service import delete_customer
        assert delete_customer(99999) is False


# ---------------------------------------------------------------------------
# search_customers
# ---------------------------------------------------------------------------

class TestSearch:
    def test_search_by_name(self, db):
        _add_customer(db, "Acme Corp")
        _add_customer(db, "Beta LLC")
        from app.services.customer_service import search_customers
        results = search_customers(query="Acme")
        assert len(results) == 1
        assert results[0].name == "Acme Corp"

    def test_search_by_mobile(self, db):
        _add_customer(db, "MobileGuy", mobile="5551234567")
        from app.services.customer_service import search_customers
        results = search_customers(query="555123")
        assert len(results) == 1

    def test_search_by_email(self, db):
        c = _add_customer(db, "EmailFolk")
        c.email = "special@test.com"
        db.commit()
        from app.services.customer_service import search_customers
        results = search_customers(query="special")
        assert len(results) == 1

    def test_search_no_match(self, db):
        _add_customer(db, "Real Corp")
        from app.services.customer_service import search_customers
        assert search_customers(query="ZZZNOMATCH") == []

    def test_search_empty_query_returns_all(self, db):
        _add_customer(db, "A")
        _add_customer(db, "B")
        _add_customer(db, "C")
        from app.services.customer_service import search_customers
        assert len(search_customers()) == 3


# ---------------------------------------------------------------------------
# customer_totals
# ---------------------------------------------------------------------------

class TestCustomerTotals:
    def test_no_invoices(self, db):
        c = _add_customer(db, "EmptyTotals")
        from app.services.customer_service import customer_totals
        t = customer_totals(c.id)
        assert t["total_invoiced"] == 0
        assert t["total_paid"] == 0
        assert t["outstanding"] == 0
        assert t["invoice_count"] == 0

    def test_invoiced_and_paid(self, db):
        c = _add_customer(db, "Totals1")
        inv1 = _add_invoice(db, c.id, grand_total=5000)
        inv2 = _add_invoice(db, c.id, grand_total=3000)
        db.add(Payment(invoice_id=inv1.id, amount=5000, date=date.today(), mode="Cash"))
        db.add(Payment(invoice_id=inv2.id, amount=1000, date=date.today(), mode="UPI"))
        db.commit()
        from app.services.customer_service import customer_totals
        t = customer_totals(c.id)
        assert t["total_invoiced"] == 8000.0
        assert t["total_paid"] == 6000.0
        assert t["outstanding"] == 2000.0
        assert t["invoice_count"] == 2

    def test_draft_excluded(self, db):
        c = _add_customer(db, "DraftExcl")
        _add_invoice(db, c.id, grand_total=1000, status="DRAFT")
        _add_invoice(db, c.id, grand_total=2000, status="SAVED")
        from app.services.customer_service import customer_totals
        t = customer_totals(c.id)
        assert t["total_invoiced"] == 2000.0
        assert t["invoice_count"] == 1


# ---------------------------------------------------------------------------
# customer_invoices
# ---------------------------------------------------------------------------

class TestCustomerInvoices:
    def test_returns_invoices(self, db):
        c = _add_customer(db, "InvCust")
        _add_invoice(db, c.id, grand_total=100)
        _add_invoice(db, c.id, grand_total=200)
        from app.services.customer_service import customer_invoices
        invs = customer_invoices(c.id)
        assert len(invs) == 2

    def test_returns_empty(self, db):
        c = _add_customer(db, "NoInv")
        from app.services.customer_service import customer_invoices
        assert customer_invoices(c.id) == []


# ---------------------------------------------------------------------------
# customer_payments
# ---------------------------------------------------------------------------

class TestCustomerPayments:
    def test_returns_payments(self, db):
        c = _add_customer(db, "PayCust")
        inv = _add_invoice(db, c.id, grand_total=5000)
        db.add(Payment(invoice_id=inv.id, amount=1000, date=date.today(), mode="Cash"))
        db.add(Payment(invoice_id=inv.id, amount=2000, date=date.today(), mode="UPI"))
        db.commit()
        from app.services.customer_service import customer_payments
        payments = customer_payments(c.id)
        assert len(payments) == 2
        total = sum(float(p.amount) for p in payments)
        assert total == 3000.0

    def test_empty_payments(self, db):
        c = _add_customer(db, "NoPay")
        from app.services.customer_service import customer_payments
        assert customer_payments(c.id) == []


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
