"""Comprehensive tests for financial calculations, payments, and dashboard synchronization."""
from datetime import date
import pytest
from PySide6.QtWidgets import QApplication

from app.models.models import Customer, Invoice, Payment
from app.services import customer_service, dashboard_service, invoice_service, payment_service
from app.utils import calculations as calc

_app = QApplication.instance() or QApplication([])


def test_row_and_section_calculations():
    """Verify precision of row amounts, LS amounts, and area totals."""
    rows = [
        # Living room
        {"area": "LIVING ROOM", "qty_raw": "2", "rate_raw": "15000", "amount": None},
        {"area": "LIVING ROOM", "qty_raw": "1.5", "rate_raw": "8000", "amount": None},
        {"area": "LIVING ROOM", "qty_raw": "LS", "rate_raw": "LS", "amount": 4500.50},
        # Bedroom
        {"area": "BEDROOM", "qty_raw": "3", "rate_raw": "12500.25", "amount": None},
    ]

    computed, subtotal = calc.compute_rows(rows)
    assert computed[0] == 30000.00
    assert computed[1] == 12000.00
    assert computed[2] == 4500.50
    assert computed[3] == 37500.75
    # Subtotal: 30000 + 12000 + 4500.50 + 37500.75 = 84001.25
    assert subtotal == 84001.25

    area_totals = calc.compute_area_totals(rows)
    # Living Room total: 30000 + 12000 + 4500.50 = 46500.50
    assert area_totals["LIVING ROOM"] == 46500.50
    # Bedroom total: 37500.75
    assert area_totals["BEDROOM"] == 37500.75


def test_gst_and_discount_calculations():
    """Verify discount clamping, taxable amount, and GST calculation precision."""
    subtotal = 100000.00
    discount = 10000.00
    gst_rate = 18.0

    res = calc.apply_gst(subtotal, discount, gst_rate)
    assert res["subtotal"] == 100000.00
    assert res["discount"] == 10000.00
    assert res["gst_rate"] == 18.0
    # Taxable = 90,000; GST 18% = 16,200; Grand = 106,200
    assert res["gst_amount"] == 16200.00
    assert res["grand_total"] == 106200.00

    # Test excessive discount clamped to subtotal
    res_clamp = calc.apply_gst(1000.00, 1500.00, 18.0)
    assert res_clamp["discount"] == 1000.00
    assert res_clamp["grand_total"] == 0.00


def test_full_payment_settlement_and_status_transition(db):
    """Verify payment recording, status transition from UNPAID -> PARTIALLY PAID -> PAID."""
    cust = Customer(name="Priya Sharma", mobile="9820011223")
    db.add(cust)
    db.commit()

    inv_data = {
        "customer_id": cust.id,
        "invoice_date": date.today(),
        "status": "SAVED",
        "notes": "Payment Test",
    }
    items = [
        {"area": "HALL", "description": "Sofa Set", "qty_raw": "1", "rate_raw": "40000", "amount": 40000.0},
        {"area": "HALL", "description": "Center Table", "qty_raw": "1", "rate_raw": "10000", "amount": 10000.0},
    ]
    inv = invoice_service.create_invoice(inv_data, items)
    assert float(inv.grand_total) == 50000.00
    assert inv.status == "SAVED"

    # Status without payments should be UNPAID
    st = invoice_service.invoice_status(inv)
    assert st == "UNPAID"

    # 1. Partial payment of 20,000
    p1 = payment_service.add_payment(inv.id, 20000.00, mode="UPI")
    assert float(p1.amount) == 20000.00

    summary1 = payment_service.invoice_payment_summary(inv.id)
    assert summary1["total"] == 50000.00
    assert summary1["paid"] == 20000.00
    assert summary1["outstanding"] == 30000.00

    # Invoice status in DB and computed should be PARTIALLY PAID
    inv_db1 = invoice_service.get_invoice(inv.id)
    assert inv_db1.status == "PARTIALLY PAID"
    assert invoice_service.invoice_status(inv_db1) == "PARTIALLY PAID"

    # 2. Settle remaining 30,000 in full
    p2 = payment_service.settle_invoice_full(inv.id, mode="Bank Transfer")
    assert float(p2.amount) == 30000.00

    summary2 = payment_service.invoice_payment_summary(inv.id)
    assert summary2["total"] == 50000.00
    assert summary2["paid"] == 50000.00
    assert summary2["outstanding"] == 0.00

    # Invoice status in DB and computed should be PAID
    inv_db2 = invoice_service.get_invoice(inv.id)
    assert inv_db2.status == "PAID"
    assert invoice_service.invoice_status(inv_db2) == "PAID"


def test_floating_point_exact_payment_tolerance(db):
    """Verify that floating point fractional differences (e.g. 70.50 vs 70.499999) don't block payment."""
    cust = Customer(name="Ramesh Patel", mobile="9899112233")
    db.add(cust)
    db.commit()

    inv = invoice_service.create_invoice(
        {"customer_id": cust.id, "status": "SAVED"},
        [{"area": "KITCHEN", "description": "Cabinets", "qty_raw": "1", "rate_raw": "105.70", "amount": 105.70}]
    )
    # Partial payment of 35.20 -> exact remaining is 70.50
    payment_service.add_payment(inv.id, 35.20)
    summary = payment_service.invoice_payment_summary(inv.id)
    assert summary["outstanding"] == 70.50

    # Paying exact 70.50 must succeed without throwing ValueError
    p_full = payment_service.add_payment(inv.id, 70.50)
    assert float(p_full.amount) == 70.50

    summary_final = payment_service.invoice_payment_summary(inv.id)
    assert summary_final["outstanding"] == 0.00


def test_dashboard_and_customer_totals_synchronization(db):
    """Verify Dashboard and Customer totals match invoice payments perfectly."""
    cust = Customer(name="Kavita Mehta", mobile="9811223344")
    db.add(cust)
    db.commit()

    inv = invoice_service.create_invoice(
        {"customer_id": cust.id, "status": "SAVED"},
        [{"area": "ROOM", "description": "Desk", "qty_raw": "1", "rate_raw": "25000", "amount": 25000.0}]
    )

    # Check Customer totals before payment
    c_tot1 = customer_service.customer_totals(cust.id)
    assert c_tot1["total_invoiced"] == 25000.00
    assert c_tot1["total_paid"] == 0.00
    assert c_tot1["outstanding"] == 25000.00

    # Check Dashboard stats before payment
    d_stats1 = dashboard_service.dashboard_stats()
    assert d_stats1["total_billed"] >= 25000.00
    assert d_stats1["total_outstanding"] >= 25000.00

    # Check Pending collections list contains customer
    pending1 = dashboard_service.top_pending_collections(10)
    cust_entry = next((item for item in pending1 if item["customer_id"] == cust.id), None)
    assert cust_entry is not None
    assert cust_entry["outstanding"] == 25000.00
    assert cust_entry["primary_invoice_id"] == inv.id

    # Settle full payment
    payment_service.settle_invoice_full(inv.id, mode="Cash")

    # Check Customer totals after payment
    c_tot2 = customer_service.customer_totals(cust.id)
    assert c_tot2["total_paid"] == 25000.00
    assert c_tot2["outstanding"] == 0.00

    # Check Dashboard stats after payment
    d_stats2 = dashboard_service.dashboard_stats()
    assert d_stats2["total_income"] >= 25000.00

    # Check Pending collections list no longer contains fully paid customer
    pending2 = dashboard_service.top_pending_collections(10)
    assert not any(item["customer_id"] == cust.id for item in pending2)


def test_payment_dialog_full_settlement(db, monkeypatch):
    """Test 1-click full payment settlement in PaymentDialog UI."""
    from PySide6.QtWidgets import QMessageBox
    from app.ui.pages.payment_dialog import PaymentDialog

    cust = Customer(name="Anoop Verma", mobile="9833001122")
    db.add(cust)
    db.commit()

    inv = invoice_service.create_invoice(
        {"customer_id": cust.id, "status": "SAVED"},
        [{"area": "HALL", "description": "TV Unit", "qty_raw": "1", "rate_raw": "18000", "amount": 18000.0}]
    )

    dlg = PaymentDialog(inv)
    assert dlg.btn_full_pay.isEnabled()
    assert "18,000.00" in dlg.btn_full_pay.text()

    # Confirm dialog prompt
    monkeypatch.setattr(QMessageBox, "question", lambda *args, **kwargs: QMessageBox.Yes)

    dlg._pay_full_balance()

    summary = payment_service.invoice_payment_summary(inv.id)
    assert summary["paid"] == 18000.00
    assert summary["outstanding"] == 0.00
    assert not dlg.btn_full_pay.isEnabled()
    assert "Fully Settled" in dlg.info.text()

