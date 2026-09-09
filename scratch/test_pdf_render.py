"""Verify actual PDF file generation with QtWebEngine."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtWidgets import QApplication
from app.database.database import init_db, get_session
from app.models.models import Customer, Invoice, InvoiceItem, BusinessProfile
from app.services import invoice_service, business_service
from app.pdf.pdf_service import _write_pdf_sync
from app.pdf.customer_statement_pdf import save_customer_statement_pdf

app = QApplication.instance() or QApplication(sys.argv)
init_db()

# Setup test profile with Bank & UPI details
session = get_session()
profile = session.query(BusinessProfile).first()
if profile:
    profile.bank_name = "State Bank of India"
    profile.account_number = "123456789012"
    profile.ifsc_code = "SBIN0001234"
    profile.account_holder = "Furni Crafts India"
    profile.upi_id = "furnicrafts@upi"
    profile.upi_qr_enabled = True
    session.commit()

# Create test invoice
cust = session.query(Customer).first()
if not cust:
    cust = Customer(name="Sample Client", mobile="9876543210", city="Mumbai")
    session.add(cust)
    session.commit()

inv = invoice_service.create_invoice(
    {"customer_id": cust.id, "invoice_prefix": "LUX", "status": "SAVED"},
    [
        {"area": "LIVING ROOM", "description": "L-Shape Premium Italian Leather Sofa", "size": "10ft x 7ft", "qty_raw": "1", "rate_raw": "85000"},
        {"area": "MASTER BEDROOM", "description": "Solid Teak Wood Hydraulic Storage Bed", "size": "6ft x 6.5ft", "qty_raw": "1", "rate_raw": "55000"},
    ]
)

invoice_pdf_path = Path("scratch/sample_luxury_invoice.pdf")
statement_pdf_path = Path("scratch/sample_khata_statement.pdf")

try:
    print("Generating Luxury Invoice PDF...")
    _write_pdf_sync(inv.id, invoice_pdf_path)
    assert invoice_pdf_path.exists(), "Invoice PDF was not created!"
    size = invoice_pdf_path.stat().st_size
    assert size > 1000, f"Invoice PDF is suspiciously small: {size} bytes"
    with open(invoice_pdf_path, "rb") as f:
        header = f.read(5)
        assert header == b"%PDF-", f"Invalid PDF header: {header}"
    print(f"SUCCESS: Invoice PDF created successfully ({size} bytes) at {invoice_pdf_path}")

    print("Generating Customer Khata Statement PDF...")
    saved_stmt = save_customer_statement_pdf(cust.id, statement_pdf_path)
    assert saved_stmt and statement_pdf_path.exists(), "Statement PDF was not created!"
    stmt_size = statement_pdf_path.stat().st_size
    assert stmt_size > 1000, f"Statement PDF is suspiciously small: {stmt_size} bytes"
    with open(statement_pdf_path, "rb") as f:
        header = f.read(5)
        assert header == b"%PDF-", f"Invalid PDF header: {header}"
    print(f"SUCCESS: Customer Statement PDF created successfully ({stmt_size} bytes) at {statement_pdf_path}")

finally:
    # Cleanup test invoice
    invoice_service.delete_invoice(inv.id)
