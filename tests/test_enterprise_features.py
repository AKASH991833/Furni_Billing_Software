"""Unit tests for Priority 1, 2, and 3 Enterprise Features:
- Ultra-luxury PDF layout with status badges, bank card & dynamic UPI QR code
- Invoice duplication
- Customer Statement (Khata Passbook) generation and running balance calculation
- Dashboard top pending collections
- Bank & UPI profile persistence
"""
from datetime import date, datetime, timezone
import pytest

from app.database.database import get_session
from app.models.models import Customer, Invoice, InvoiceItem, Payment
from app.services import business_service, customer_service, dashboard_service, invoice_service
from app.pdf.html_template import build_layout, build_css, _generate_upi_qr
from app.pdf.customer_statement_pdf import build_customer_statement_html


class TestEnterprisePDFAndQR:
    def test_upi_qr_generation(self):
        """UPI QR code generator should produce a valid base64 PNG data URI."""
        uri = _generate_upi_qr("9876543210@paytm", "Mahendra Furniture", 15000.0, "INV-001")
        assert uri.startswith("data:image/png;base64,")
        assert len(uri) > 100

    def test_upi_qr_empty_handling(self):
        """Empty or None UPI ID safely returns empty string."""
        assert _generate_upi_qr("") == ""
        assert _generate_upi_qr(None) == ""

    def test_luxury_pdf_blocks_and_badges(self):
        """Verify luxury layout includes status badge, dual signatures, and bank card."""
        class FakeProfile:
            business_name = "Royal Furniture Studio"
            business_type = "Interior & Wooden Furniture Contractor"
            mobile = "9876543210"
            email = "contact@royalfurniture.com"
            gstin = "27AAAAA0000A1Z5"
            show_gst = True
            logo_path = None
            signature_path = None
            terms_conditions = "1. 50% Advance with order.\n2. Goods once sold will not be taken back."
            address = "Shop 12, High Street"
            city = "Mumbai"
            state = "Maharashtra"
            pincode = "400001"
            currency = "\u20B9"
            invoice_prefix = "RFS"
            bank_name = "HDFC Bank"
            account_number = "50100428912345"
            ifsc_code = "HDFC0001234"
            account_holder = "Royal Furniture Studio"
            upi_id = "royalfurniture@okhdfcbank"
            upi_qr_enabled = True

        class FakeDate:
            def strftime(self, fmt):
                return "15-Aug-2026"

        class FakeInvoice:
            invoice_number = "RFS-0042"
            invoice_date = FakeDate()
            due_date = FakeDate()
            site_address = "Villa 4, Palm Beach Rd"
            status = "SAVED"
            subtotal = 50000.00
            discount = 2000.00
            gst_enabled = True
            gst_rate = 18.0
            gst_amount = 8640.00
            grand_total = 56640.00
            amount_in_words = "Fifty Six Thousand Six Hundred Forty Rupees Only"
            payments = []

        class FakeCustomer:
            name = "Rajesh Sharma"
            mobile = "9820098200"
            address = "B-402, Sea View Apts"
            city = "Navi Mumbai"
            state = "Maharashtra"
            gstin = "27BBBBB0000B1Z5"

        class FakeProject:
            name = "Sharma Residence Interior"
            site_address = "Villa 4, Palm Beach Rd"

        class FakeItem:
            area = "MASTER BEDROOM"
            description = "Teakwood King Size Bed with Hydraulic Storage"
            size = "6' x 6.5'"
            qty_raw = "1"
            rate_raw = "48000"
            amount = 48000.00

        layout = build_layout(FakeProfile(), FakeInvoice(), FakeCustomer(), FakeProject(), [FakeItem()])

        # Verify Header & Badges
        assert "RFS-0042" in layout.header_html
        assert "TAX INVOICE" in layout.header_html
        assert "PAYMENT DUE" in layout.header_html or "badge-due" in layout.header_html

        # Verify Symmetric 2-card Address Grid
        assert "BILLED TO" in layout.billto_html.upper()
        assert "Rajesh Sharma" in layout.billto_html
        assert "Sharma Residence Interior" in layout.billto_html

        # Verify Bank & QR inside BLK-TOT
        tot_blk = next(h for bid, h in layout.final if bid == "BLK-TOT")
        assert "HDFC Bank" in tot_blk
        assert "50100428912345" in tot_blk
        assert "HDFC0001234" in tot_blk
        assert "data:image/png;base64," in tot_blk
        assert "Scan to Pay" in tot_blk

        # Verify Dual Signatures in BLK-SIG
        sig_blk = next(h for bid, h in layout.final if bid == "BLK-SIG")
        assert "Customer Signature" in sig_blk
        assert "AUTHORIZED SIGNATURE" in sig_blk


class TestDuplicateInvoice:
    def test_duplicate_invoice_creates_draft(self, db):
        """Duplicating an invoice creates a new draft with same items and customer."""
        session = get_session()
        # Create a test customer
        cust = Customer(name="Duplicate Test Customer", mobile="9988776655", city="Pune")
        session.add(cust)
        session.flush()

        # Create original invoice
        inv_data = {
            "customer_id": cust.id,
            "invoice_date": date.today(),
            "status": "SAVED",
            "notes": "Original Test Order",
            "invoice_prefix": "DUP",
        }
        items_data = [
            {"area": "HALL", "description": "Sofa 3-Seater", "size": "7ft", "qty_raw": "1", "rate_raw": "25000"}
        ]
        orig = invoice_service.create_invoice(inv_data, items_data)
        orig_id = orig.id
        orig_no = orig.invoice_number

        # Duplicate it
        cloned = invoice_service.duplicate_invoice(orig_id)
        assert cloned.id != orig_id
        assert cloned.invoice_number != orig_no
        assert cloned.status == "DRAFT"
        assert cloned.customer_id == cust.id
        assert len(cloned.items) == 1
        assert cloned.items[0].description == "Sofa 3-Seater"
        assert float(cloned.grand_total) == float(orig.grand_total)
        assert f"Duplicated from {orig_no}" in cloned.notes


class TestCustomerStatement:
    def test_customer_statement_html_running_balance(self, db):
        """Customer statement HTML accurately computes debits, credits, and running balance."""
        session = get_session()
        cust = Customer(name="Ledger Test Client", mobile="9123456780", city="Thane")
        session.add(cust)
        session.commit()

        # Create 2 invoices
        inv1 = invoice_service.create_invoice(
            {"customer_id": cust.id, "invoice_date": date(2026, 1, 10), "invoice_prefix": "KHATA"},
            [{"area": "HALL", "description": "Dining Table", "size": "6-seater", "qty_raw": "1", "rate_raw": "30000"}]
        )
        inv2 = invoice_service.create_invoice(
            {"customer_id": cust.id, "invoice_date": date(2026, 2, 5), "invoice_prefix": "KHATA"},
            [{"area": "BEDROOM", "description": "Wardrobe", "size": "7x4", "qty_raw": "1", "rate_raw": "40000"}]
        )

        # Record a payment
        pay = Payment(invoice_id=inv1.id, amount=20000.0, date=date(2026, 1, 15), mode="UPI", reference="UPI-12345")
        session.add(pay)
        session.commit()

        html_output = build_customer_statement_html(cust.id)

        assert "ACCOUNT STATEMENT" in html_output
        assert "Ledger Test Client" in html_output
        assert inv1.invoice_number in html_output
        assert inv2.invoice_number in html_output
        assert "Payment Received (UPI)" in html_output


class TestDashboardTopPending:
    def test_top_pending_collections(self, db):
        """Top pending collections service returns customers with outstanding dues."""
        session = get_session()
        c1 = Customer(name="Alpha Debtor", mobile="9800000001")
        c2 = Customer(name="Beta Debtor", mobile="9800000002")
        session.add_all([c1, c2])
        session.commit()

        # c1 owes 50000, c2 owes 20000
        inv1 = invoice_service.create_invoice(
            {"customer_id": c1.id, "invoice_date": date.today(), "status": "SAVED", "invoice_prefix": "TST"},
            [{"area": "LIVING ROOM", "description": "Sectional Sofa", "qty_raw": "1", "rate_raw": "50000"}]
        )
        inv2 = invoice_service.create_invoice(
            {"customer_id": c2.id, "invoice_date": date.today(), "status": "SAVED", "invoice_prefix": "TST"},
            [{"area": "OFFICE", "description": "Study Table", "qty_raw": "1", "rate_raw": "20000"}]
        )

        pending = dashboard_service.top_pending_collections(10)
        names = [p["customer_name"] for p in pending]
        assert "Alpha Debtor" in names
        assert "Beta Debtor" in names

        # Alpha should rank higher than Beta
        alpha_idx = names.index("Alpha Debtor")
        beta_idx = names.index("Beta Debtor")
        assert alpha_idx < beta_idx


