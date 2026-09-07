"""Tests for invoice_service — CRUD, status logic, numbering, search, delete.

Run with:  python -m pytest tests/test_invoice_service.py -q
"""
import itertools
from datetime import date, datetime, timedelta, timezone

import pytest

from app.models.models import Customer, Invoice, InvoiceItem, Payment, Setting

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_inv_counter = itertools.count(1)


def _add_customer(session, name="Test Customer", mobile="9000000000"):
    c = Customer(name=name, mobile=mobile)
    session.add(c)
    session.commit()
    return c


def _add_invoice(session, customer_id, status="SAVED", grand_total=1000.0,
                 invoice_number=None):
    seq = next(_inv_counter)
    inv = Invoice(
        invoice_number=invoice_number or f"INV-TEST-{seq:04d}",
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
# invoice_status
# ---------------------------------------------------------------------------

class TestInvoiceStatus:
    def test_unpaid_no_payments(self, db):
        c = _add_customer(db, "A")
        inv = _add_invoice(db, c.id, status="SAVED", grand_total=1000)
        from app.services.invoice_service import invoice_status
        assert invoice_status(inv) == "UNPAID"

    def test_paid_in_full(self, db):
        c = _add_customer(db, "B")
        inv = _add_invoice(db, c.id, status="SAVED", grand_total=1000)
        p = Payment(invoice_id=inv.id, amount=1000, date=date.today(), mode="Cash")
        db.add(p)
        db.commit()
        db.refresh(inv)
        from app.services.invoice_service import invoice_status
        assert invoice_status(inv) == "PAID"

    def test_partially_paid(self, db):
        c = _add_customer(db, "C")
        inv = _add_invoice(db, c.id, status="SAVED", grand_total=2000)
        p = Payment(invoice_id=inv.id, amount=500, date=date.today(), mode="Cash")
        db.add(p)
        db.commit()
        db.refresh(inv)
        from app.services.invoice_service import invoice_status
        assert invoice_status(inv) == "PARTIALLY PAID"

    def test_overdue_no_payment(self, db):
        c = _add_customer(db, "D")
        inv = _add_invoice(db, c.id, status="SAVED", grand_total=1000)
        inv.due_date = date.today() - timedelta(days=5)
        db.commit()
        db.refresh(inv)
        from app.services.invoice_service import invoice_status
        assert invoice_status(inv) == "OVERDUE"

    def test_overdue_partially_paid(self, db):
        c = _add_customer(db, "E")
        inv = _add_invoice(db, c.id, status="SAVED", grand_total=2000)
        inv.due_date = date.today() - timedelta(days=3)
        p = Payment(invoice_id=inv.id, amount=500, date=date.today(), mode="Cash")
        db.add(p)
        db.commit()
        db.refresh(inv)
        from app.services.invoice_service import invoice_status
        assert invoice_status(inv) == "OVERDUE"

    def test_draft_status(self, db):
        c = _add_customer(db, "F")
        inv = _add_invoice(db, c.id, status="DRAFT", grand_total=0)
        from app.services.invoice_service import invoice_status
        assert invoice_status(inv) == "DRAFT"

    def test_zero_total_no_draft(self, db):
        c = _add_customer(db, "G")
        inv = _add_invoice(db, c.id, status="SAVED", grand_total=0)
        from app.services.invoice_service import invoice_status
        assert invoice_status(inv) == "UNPAID"


# ---------------------------------------------------------------------------
# invoice_outstanding
# ---------------------------------------------------------------------------

class TestInvoiceOutstanding:
    def test_no_payments(self, db):
        c = _add_customer(db, "X")
        inv = _add_invoice(db, c.id, grand_total=5000)
        from app.services.invoice_service import invoice_outstanding
        assert invoice_outstanding(inv) == 5000.0

    def test_partial_payment(self, db):
        c = _add_customer(db, "Y")
        inv = _add_invoice(db, c.id, grand_total=5000)
        p = Payment(invoice_id=inv.id, amount=2000, date=date.today(), mode="Cash")
        db.add(p)
        db.commit()
        db.refresh(inv)
        from app.services.invoice_service import invoice_outstanding
        assert invoice_outstanding(inv) == 3000.0

    def test_full_payment(self, db):
        c = _add_customer(db, "Z")
        inv = _add_invoice(db, c.id, grand_total=5000)
        p = Payment(invoice_id=inv.id, amount=5000, date=date.today(), mode="Cash")
        db.add(p)
        db.commit()
        db.refresh(inv)
        from app.services.invoice_service import invoice_outstanding
        assert invoice_outstanding(inv) == 0.0

    def test_overpayment_clamped_to_zero(self, db):
        c = _add_customer(db, "OV")
        inv = _add_invoice(db, c.id, grand_total=1000)
        p = Payment(invoice_id=inv.id, amount=1500, date=date.today(), mode="Cash")
        db.add(p)
        db.commit()
        db.refresh(inv)
        from app.services.invoice_service import invoice_outstanding
        assert invoice_outstanding(inv) == 0.0


# ---------------------------------------------------------------------------
# _customer_slug
# ---------------------------------------------------------------------------

class TestCustomerSlug:
    def test_simple_name(self):
        from app.services.invoice_service import _customer_slug
        assert _customer_slug("Akash") == "Akash"

    def test_spaces_to_hyphens(self):
        from app.services.invoice_service import _customer_slug
        assert _customer_slug("Akash Vishwakarma") == "Akash-Vishwakarma"

    def test_special_chars_removed(self):
        from app.services.invoice_service import _customer_slug
        assert _customer_slug("John & Co.") == "John-Co"

    def test_empty_returns_empty(self):
        from app.services.invoice_service import _customer_slug
        assert _customer_slug("") == ""
        assert _customer_slug(None) == ""

    def test_whitespace_only(self):
        from app.services.invoice_service import _customer_slug
        # Whitespace-only → empty after strip → regex leaves "" → falls back to CUSTOMER
        assert _customer_slug("   ") == "CUSTOMER"


# ---------------------------------------------------------------------------
# _compose_number
# ---------------------------------------------------------------------------

class TestComposeNumber:
    def test_default_format(self, db):
        from app.services.invoice_service import _compose_number
        result = _compose_number("INV", None, None, 5)
        assert result == "INV-0005"

    def test_with_customer(self, db):
        from app.services.invoice_service import _compose_number
        result = _compose_number("INV", "Akash", 2026, 3)
        assert result == "Akash-INV-2026-0003"

    def test_custom_format_template(self, db):
        from app.services.business_service import save_profile
        save_profile({
            "business_name": "Test",
            "invoice_format": "{PREFIX}/{YEAR}/{SEQ}",
            "invoice_sequence_digits": 3,
        })
        from app.services.invoice_service import _compose_number
        result = _compose_number("INV", None, 2026, 10)
        assert result == "INV/2026/010"

    def test_customer_custom_format(self, db):
        from app.services.business_service import save_profile
        save_profile({
            "business_name": "Test",
            "invoice_format": "{CUSTOMER}-{PREFIX}-{YEAR}-{SEQ}",
            "invoice_sequence_digits": 5,
        })
        from app.services.invoice_service import _compose_number
        result = _compose_number("INV", "Rahul Kumar", 2025, 7)
        assert result == "Rahul-Kumar-INV-2025-00007"


# ---------------------------------------------------------------------------
# next_invoice_number
# ---------------------------------------------------------------------------

class TestNextInvoiceNumber:
    def test_first_number(self, db):
        from app.services.invoice_service import next_invoice_number
        num = next_invoice_number("INV")
        assert num.startswith("INV-")
        assert "0001" in num

    def test_increments(self, db):
        from app.services.invoice_service import next_invoice_number
        n1 = next_invoice_number("INV")
        n2 = next_invoice_number("INV")
        assert n1 != n2

    def test_customer_scoped(self, db):
        from app.services.invoice_service import next_invoice_number
        n1 = next_invoice_number("INV", customer_name="Akash")
        n2 = next_invoice_number("INV", customer_name="Akash")
        assert n1 != n2
        assert "Akash" in n1

    def test_different_customers_independent(self, db):
        from app.services.invoice_service import next_invoice_number
        n1 = next_invoice_number("INV", customer_name="Akash")
        n2 = next_invoice_number("INV", customer_name="Rahul")
        assert "Akash" in n1
        assert "Rahul" in n2


# ---------------------------------------------------------------------------
# create_invoice
# ---------------------------------------------------------------------------

class TestCreateInvoice:
    def test_create_basic(self, db):
        c = _add_customer(db, "Cust1")
        from app.services.invoice_service import create_invoice
        inv = create_invoice(
            {"customer_id": c.id, "status": "SAVED", "gst_enabled": False},
            [{"area": "HALL", "description": "TV Unit", "size": "5x4",
              "qty_raw": "2", "rate_raw": "1000"}],
        )
        assert inv is not None
        assert inv.invoice_number  # has a generated number
        assert inv.grand_total == 2000.0
        assert len(inv.items) == 1

    def test_create_with_gst(self, db):
        c = _add_customer(db, "Cust2")
        from app.services.invoice_service import create_invoice
        inv = create_invoice(
            {"customer_id": c.id, "gst_enabled": True, "gst_rate": 18},
            [{"area": "HALL", "description": "Item", "size": "",
              "qty_raw": "1", "rate_raw": "1000"}],
        )
        assert inv.gst_enabled is True
        assert inv.gst_amount == 180.0
        assert inv.grand_total == 1180.0

    def test_create_with_discount(self, db):
        c = _add_customer(db, "Cust3")
        from app.services.invoice_service import create_invoice
        inv = create_invoice(
            {"customer_id": c.id, "discount": 500, "gst_enabled": False},
            [{"area": "HALL", "description": "Item", "size": "",
              "qty_raw": "2", "rate_raw": "1000"}],
        )
        assert inv.subtotal == 2000.0
        assert inv.discount == 500.0
        assert inv.grand_total == 1500.0

    def test_create_multiple_items(self, db):
        c = _add_customer(db, "Cust4")
        items = [
            {"area": "HALL", "description": "A", "size": "", "qty_raw": "1", "rate_raw": "100"},
            {"area": "KITCHEN", "description": "B", "size": "", "qty_raw": "2", "rate_raw": "200"},
        ]
        from app.services.invoice_service import create_invoice
        inv = create_invoice(
            {"customer_id": c.id, "gst_enabled": False},
            items,
        )
        assert inv.subtotal == 500.0
        assert len(inv.items) == 2

    def test_duplicate_number_retries(self, db):
        c = _add_customer(db, "Cust5")
        from app.services.invoice_service import create_invoice
        inv1 = create_invoice(
            {"customer_id": c.id, "invoice_number": "DUP-001", "gst_enabled": False},
            [{"area": "HALL", "description": "X", "size": "", "qty_raw": "1", "rate_raw": "100"}],
        )
        inv2 = create_invoice(
            {"customer_id": c.id, "invoice_number": "DUP-001", "gst_enabled": False},
            [{"area": "HALL", "description": "Y", "size": "", "qty_raw": "1", "rate_raw": "200"}],
        )
        assert inv1.invoice_number != inv2.invoice_number


# ---------------------------------------------------------------------------
# update_invoice
# ---------------------------------------------------------------------------

class TestUpdateInvoice:
    def test_update_basic(self, db):
        c = _add_customer(db, "Upd1")
        from app.services.invoice_service import create_invoice, update_invoice
        inv = create_invoice(
            {"customer_id": c.id, "gst_enabled": False},
            [{"area": "HALL", "description": "Old", "size": "",
              "qty_raw": "1", "rate_raw": "100"}],
        )
        updated = update_invoice(
            inv.id,
            {"customer_id": c.id, "gst_enabled": False},
            [{"area": "HALL", "description": "New", "size": "",
              "qty_raw": "2", "rate_raw": "500"}],
        )
        assert updated.items[0].description == "New"
        assert updated.subtotal == 1000.0

    def test_update_nonexistent_raises(self, db):
        from app.services.invoice_service import update_invoice
        with pytest.raises(ValueError, match="not found"):
            update_invoice(99999, {"gst_enabled": False}, [])

    def test_update_replaces_items(self, db):
        c = _add_customer(db, "Upd2")
        from app.services.invoice_service import create_invoice, update_invoice
        inv = create_invoice(
            {"customer_id": c.id, "gst_enabled": False},
            [
                {"area": "A", "description": "X", "size": "", "qty_raw": "1", "rate_raw": "100"},
                {"area": "B", "description": "Y", "size": "", "qty_raw": "1", "rate_raw": "200"},
            ],
        )
        updated = update_invoice(
            inv.id,
            {"customer_id": c.id, "gst_enabled": False},
            [{"area": "C", "description": "Z", "size": "", "qty_raw": "3", "rate_raw": "50"}],
        )
        assert len(updated.items) == 1
        assert updated.items[0].area == "C"


# ---------------------------------------------------------------------------
# delete_invoice
# ---------------------------------------------------------------------------

class TestDeleteInvoice:
    def test_delete_existing(self, db):
        c = _add_customer(db, "Del1")
        from app.services.invoice_service import create_invoice, delete_invoice
        inv = create_invoice(
            {"customer_id": c.id, "gst_enabled": False},
            [{"area": "HALL", "description": "X", "size": "", "qty_raw": "1", "rate_raw": "100"}],
        )
        assert delete_invoice(inv.id) is True
        from app.services.invoice_service import get_invoice
        assert get_invoice(inv.id) is None

    def test_delete_nonexistent(self, db):
        from app.services.invoice_service import delete_invoice
        assert delete_invoice(99999) is False


# ---------------------------------------------------------------------------
# get_invoice / search_invoices
# ---------------------------------------------------------------------------

class TestGetAndSearch:
    def test_get_invoice(self, db):
        c = _add_customer(db, "Get1")
        from app.services.invoice_service import create_invoice, get_invoice
        inv = create_invoice(
            {"customer_id": c.id, "gst_enabled": False},
            [{"area": "HALL", "description": "X", "size": "", "qty_raw": "1", "rate_raw": "100"}],
        )
        fetched = get_invoice(inv.id)
        assert fetched is not None
        assert fetched.invoice_number == inv.invoice_number

    def test_get_nonexistent(self, db):
        from app.services.invoice_service import get_invoice
        assert get_invoice(99999) is None

    def test_search_by_customer_name(self, db):
        c = _add_customer(db, "Searchable Corp")
        from app.services.invoice_service import create_invoice, search_invoices
        create_invoice(
            {"customer_id": c.id, "gst_enabled": False},
            [{"area": "HALL", "description": "X", "size": "", "qty_raw": "1", "rate_raw": "100"}],
        )
        results = search_invoices(query="Searchable")
        assert len(results) >= 1

    def test_search_by_invoice_number(self, db):
        c = _add_customer(db, "Srch2")
        from app.services.invoice_service import create_invoice, search_invoices
        inv = create_invoice(
            {"customer_id": c.id, "invoice_number": "FIND-ME-001", "gst_enabled": False},
            [{"area": "HALL", "description": "X", "size": "", "qty_raw": "1", "rate_raw": "100"}],
        )
        results = search_invoices(query="FIND-ME")
        assert any(r.invoice_number == "FIND-ME-001" for r in results)

    def test_search_by_status(self, db):
        c = _add_customer(db, "Status1")
        from app.services.invoice_service import create_invoice, search_invoices
        create_invoice(
            {"customer_id": c.id, "status": "DRAFT", "invoice_number": "DRAFT-001", "gst_enabled": False},
            [{"area": "HALL", "description": "X", "size": "", "qty_raw": "1", "rate_raw": "100"}],
        )
        create_invoice(
            {"customer_id": c.id, "status": "SAVED", "invoice_number": "SAVED-001", "gst_enabled": False},
            [{"area": "HALL", "description": "Y", "size": "", "qty_raw": "1", "rate_raw": "200"}],
        )
        drafts = search_invoices(status="DRAFT")
        saved = search_invoices(status="SAVED")
        assert len(drafts) >= 1
        assert len(saved) >= 1

    def test_search_no_match(self, db):
        from app.services.invoice_service import search_invoices
        results = search_invoices(query="ZZZNONEXISTENT")
        assert results == []


# ---------------------------------------------------------------------------
# list_all_invoices
# ---------------------------------------------------------------------------

class TestListAll:
    def test_list_all(self, db):
        c = _add_customer(db, "List1")
        from app.services.invoice_service import create_invoice, list_all_invoices
        create_invoice(
            {"customer_id": c.id, "invoice_number": "LIST-001", "gst_enabled": False},
            [{"area": "HALL", "description": "X", "size": "", "qty_raw": "1", "rate_raw": "100"}],
        )
        create_invoice(
            {"customer_id": c.id, "invoice_number": "LIST-002", "gst_enabled": False},
            [{"area": "HALL", "description": "Y", "size": "", "qty_raw": "1", "rate_raw": "200"}],
        )
        all_inv = list_all_invoices()
        assert len(all_inv) >= 2

    def test_list_all_empty(self, db):
        from app.services.invoice_service import list_all_invoices
        result = list_all_invoices()
        assert len(result) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
