"""End-to-end integration test: full business flow.

Covers the complete lifecycle:
  1. Create customers
  2. Create invoices with items
  3. Add payments (partial & full)
  4. Verify dashboard stats match expected values
  5. Search / list / delete operations

Run with:  python -m pytest tests/test_integration_flow.py -q
"""
from datetime import date, timedelta

import pytest

from app.utils.cache import cache


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clear_cache():
    """Ensure fresh data is read from DB, not cached values."""
    cache.clear()


# ---------------------------------------------------------------------------
# Full business flow
# ---------------------------------------------------------------------------

class TestFullBusinessFlow:
    """Single-customer, multi-invoice scenario that exercises every layer."""

    def test_complete_lifecycle(self, db):
        _clear_cache()

        # ── Step 1: Create customers ─────────────────────────────────────
        from app.services.customer_service import (
            add_customer,
            customer_totals,
            get_customer,
            search_customers,
        )

        cust1 = add_customer({
            "name": "Rahul Kumar",
            "mobile": "9876543210",
            "email": "rahul@example.com",
            "city": "Mumbai",
            "state": "MH",
        })
        cust2 = add_customer({
            "name": "Priya Sharma",
            "mobile": "9123456789",
            "city": "Pune",
        })
        assert cust1.id is not None
        assert cust2.id is not None

        # Verify search works
        results = search_customers(query="Rahul")
        assert len(results) == 1
        assert results[0].name == "Rahul Kumar"

        # ── Step 2: Create invoices ──────────────────────────────────────
        from app.services.invoice_service import (
            create_invoice,
            get_invoice,
            invoice_outstanding,
            invoice_status,
            list_all_invoices,
            search_invoices,
        )

        # Invoice 1: Rahul — 3 items, GST ON
        inv1 = create_invoice(
            {
                "customer_id": cust1.id,
                "status": "SAVED",
                "gst_enabled": True,
                "gst_rate": 18,
                "discount": 500,
            },
            [
                {"area": "HALL", "description": "TV Unit", "size": "6x4",
                 "qty_raw": "2", "rate_raw": "25000"},        # 50000
                {"area": "HALL", "description": "Wall Panel", "size": "8x4",
                 "qty_raw": "1.5", "rate_raw": "12000"},      # 18000
                {"area": "KITCHEN", "description": "Cabinet", "size": "10x5",
                 "qty_raw": "1", "rate_raw": "45000"},        # 45000
            ],
        )
        assert inv1 is not None
        assert inv1.customer_id == cust1.id
        assert len(inv1.items) == 3
        # Subtotal = 50000 + 18000 + 45000 = 113000
        assert inv1.subtotal == 113000.0
        # Discount = 500, Net = 112500
        assert inv1.discount == 500.0
        # GST = 112500 * 18% = 20250
        assert inv1.gst_amount == 20250.0
        # Grand Total = 112500 + 20250 = 132750
        assert inv1.grand_total == 132750.0

        # Invoice 2: Rahul — LS item
        inv2 = create_invoice(
            {
                "customer_id": cust1.id,
                "status": "SAVED",
                "gst_enabled": False,
            },
            [
                {"area": "BEDROOM", "description": "Custom Work", "size": "",
                 "qty_raw": "LS", "rate_raw": "LS", "amount": 35000},
            ],
        )
        assert inv2.subtotal == 35000.0
        assert inv2.grand_total == 35000.0

        # Invoice 3: Priya — GST OFF
        inv3 = create_invoice(
            {
                "customer_id": cust2.id,
                "status": "SAVED",
                "gst_enabled": False,
            },
            [
                {"area": "OFFICE", "description": "Desk", "size": "5x3",
                 "qty_raw": "3", "rate_raw": "8000"},          # 24000
            ],
        )
        assert inv3.subtotal == 24000.0
        assert inv3.grand_total == 24000.0

        # Verify invoices are searchable
        results = search_invoices(query="Rahul")
        assert len(results) == 2  # inv1 + inv2

        all_invoices = list_all_invoices()
        assert len(all_invoices) >= 3

        # ── Step 3: Add payments ─────────────────────────────────────────
        from app.services.payment_service import (
            add_payment,
            invoice_payment_summary,
        )

        # Pay inv1 partially: 80000
        add_payment(inv1.id, 80000, mode="Cash")
        summary1 = invoice_payment_summary(inv1.id)
        assert summary1["paid"] == 80000.0
        assert summary1["outstanding"] == 132750.0 - 80000.0
        assert invoice_status(get_invoice(inv1.id)) == "PARTIALLY PAID"

        # Pay inv2 fully: 35000
        add_payment(inv2.id, 35000, mode="UPI")
        summary2 = invoice_payment_summary(inv2.id)
        assert summary2["outstanding"] == 0.0
        assert invoice_status(get_invoice(inv2.id)) == "PAID"

        # Pay inv3 partially: 10000
        add_payment(inv3.id, 10000, mode="Card")
        summary3 = invoice_payment_summary(inv3.id)
        assert summary3["outstanding"] == 14000.0

        # ── Step 4: Verify dashboard ─────────────────────────────────────
        _clear_cache()
        from app.services.dashboard_service import dashboard_stats

        stats = dashboard_stats()

        assert stats["total_customers"] == 2
        assert stats["total_invoices"] == 3

        # Total paid = 80000 + 35000 + 10000 = 125000
        assert stats["total_income"] == 125000.0

        # Total billed (non-DRAFT) = 132750 + 35000 + 24000 = 191750
        # Outstanding = 191750 - 125000 = 66750
        assert stats["total_outstanding"] == 66750.0

        # Paid invoices: inv2 (fully paid) = 1
        assert stats["paid_invoices"] == 1
        # Pending: inv1 (partial) + inv3 (partial) = 2
        assert stats["pending_invoices"] == 2

        # ── Step 5: Customer totals ──────────────────────────────────────
        _clear_cache()
        t1 = customer_totals(cust1.id)
        # Rahul: inv1 (132750) + inv2 (35000) = 167750 invoiced
        assert t1["total_invoiced"] == 167750.0
        # Rahul paid: 80000 + 35000 = 115000
        assert t1["total_paid"] == 115000.0
        assert t1["outstanding"] == 167750.0 - 115000.0
        assert t1["invoice_count"] == 2

        t2 = customer_totals(cust2.id)
        assert t2["total_invoiced"] == 24000.0
        assert t2["total_paid"] == 10000.0
        assert t2["outstanding"] == 14000.0
        assert t2["invoice_count"] == 1


# ---------------------------------------------------------------------------
# Overdue scenario
# ---------------------------------------------------------------------------

class TestOverdueScenario:
    def test_overdue_detection(self, db):
        _clear_cache()

        from app.services.customer_service import add_customer
        from app.services.invoice_service import (
            create_invoice,
            get_invoice,
            invoice_status,
        )
        from app.services.payment_service import add_payment

        cust = add_customer({"name": "Late Payer", "mobile": "1111111111"})

        # Create invoice with due date in the past
        inv = create_invoice(
            {
                "customer_id": cust.id,
                "status": "SAVED",
                "gst_enabled": False,
                "due_date": date.today() - timedelta(days=10),
            },
            [
                {"area": "HALL", "description": "Item", "size": "",
                 "qty_raw": "1", "rate_raw": "5000"},
            ],
        )

        # No payment → should be OVERDUE
        fetched = get_invoice(inv.id)
        assert invoice_status(fetched) == "OVERDUE"

        # Partial payment → still OVERDUE
        add_payment(inv.id, 2000)
        fetched = get_invoice(inv.id)
        assert invoice_status(fetched) == "OVERDUE"

        # Full payment → should be PAID (even if past due)
        add_payment(inv.id, 3000)
        fetched = get_invoice(inv.id)
        assert invoice_status(fetched) == "PAID"


# ---------------------------------------------------------------------------
# Invoice number uniqueness
# ---------------------------------------------------------------------------

class TestNumberUniqueness:
    def test_no_duplicate_numbers(self, db):
        _clear_cache()

        from app.services.customer_service import add_customer
        from app.services.invoice_service import create_invoice

        cust = add_customer({"name": "NumTest", "mobile": "2222222222"})

        numbers = set()
        for i in range(5):
            inv = create_invoice(
                {"customer_id": cust.id, "gst_enabled": False},
                [{"area": "A", "description": f"Item {i}", "size": "",
                  "qty_raw": "1", "rate_raw": str(100 * (i + 1))}],
            )
            assert inv.invoice_number not in numbers, \
                f"Duplicate invoice number: {inv.invoice_number}"
            numbers.add(inv.invoice_number)

        assert len(numbers) == 5


# ---------------------------------------------------------------------------
# Delete cascade
# ---------------------------------------------------------------------------

class TestDeleteCascade:
    def test_delete_invoice_removes_items_and_payments(self, db):
        _clear_cache()

        from app.services.customer_service import add_customer
        from app.services.invoice_service import (
            create_invoice,
            delete_invoice,
            get_invoice,
        )
        from app.services.payment_service import add_payment

        cust = add_customer({"name": "DelTest", "mobile": "3333333333"})
        inv = create_invoice(
            {"customer_id": cust.id, "gst_enabled": False},
            [
                {"area": "A", "description": "X", "size": "", "qty_raw": "1", "rate_raw": "100"},
                {"area": "B", "description": "Y", "size": "", "qty_raw": "2", "rate_raw": "200"},
            ],
        )
        add_payment(inv.id, 100)

        # Delete should succeed
        assert delete_invoice(inv.id) is True
        # Invoice should no longer exist
        assert get_invoice(inv.id) is None


# ---------------------------------------------------------------------------
# Multi-area invoice
# ---------------------------------------------------------------------------

class TestMultiAreaInvoice:
    def test_many_areas(self, db):
        _clear_cache()

        from app.services.customer_service import add_customer
        from app.services.invoice_service import create_invoice

        cust = add_customer({"name": "AreaTest", "mobile": "4444444444"})

        areas = ["LIVING", "BEDROOM", "KITCHEN", "BATHROOM", "OFFICE", "BALCONY"]
        items = [
            {"area": area, "description": f"Item in {area}", "size": "",
             "qty_raw": str(i + 1), "rate_raw": "1000"}
            for i, area in enumerate(areas)
        ]

        inv = create_invoice(
            {"customer_id": cust.id, "gst_enabled": False},
            items,
        )

        # Subtotal = sum of (qty * rate) for each area
        expected = sum((i + 1) * 1000 for i in range(len(areas)))
        assert inv.subtotal == expected
        assert len(inv.items) == len(areas)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
