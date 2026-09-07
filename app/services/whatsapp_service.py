"""WhatsApp sharing service.

Generates the invoice PDF with a proper filename, copies it to the system
clipboard (so the user can Ctrl+V it into WhatsApp), and opens a wa.me chat
with a short pre-filled message.
"""
from __future__ import annotations

import urllib.parse
import webbrowser
from pathlib import Path


def sanitize_phone(phone: str) -> str:
    """Normalise an Indian phone number to 91XXXXXXXXXX for wa.me URLs."""
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if not digits:
        return ""
    digits = digits.removeprefix("0")
    if len(digits) > 12:
        digits = digits[-12:]
    if digits.startswith("91") and len(digits) == 12:
        return digits
    if len(digits) == 10:
        return "91" + digits
    if len(digits) == 11 and digits.startswith("0"):
        return "91" + digits[1:]
    return digits


def build_whatsapp_message(customer_name: str, business_name: str,
                           invoice_number: str, total, paid, outstanding) -> str:
    """Build the detailed text message (kept for backward compatibility)."""
    total = "0" if total is None else f"{float(total):,.2f}"
    paid = "0" if paid is None else f"{float(paid):,.2f}"
    out = "0" if outstanding is None else f"{float(outstanding):,.2f}"
    lines = [
        f"Dear {customer_name},",
        "",
        f"Thank you for choosing {business_name}.",
        "",
        f"Invoice Number : {invoice_number}",
        f"Invoice Total  : \u20B9 {total}",
        f"Amount Paid    : \u20B9 {paid}",
        f"Outstanding    : \u20B9 {out}",
        "",
        "For any queries, please contact us. Thank you!",
    ]
    return "\n".join(lines)


def build_short_message(customer_name: str, business_name: str,
                        invoice_number: str) -> str:
    """Short message — the PDF itself carries all the details."""
    return (
        f"Dear {customer_name},\n\n"
        f"Please find attached the invoice *{invoice_number}* "
        f"from {business_name}.\n\n"
        f"For any queries, please contact us. Thank you!"
    )


def generate_pdf(invoice_id: int, customer_name: str,
                 invoice_number: str) -> Path:
    """Generate the invoice PDF and return its file path.

    The file is saved to ``~/Documents/MahendraInvoices/`` with a clean name
    like ``Invoice_IN-2026-0100_Akash.pdf``.
    """
    from app.pdf.pdf_service import _write_pdf_sync

    safe_customer = "".join(
        c for c in customer_name if c.isalnum() or c in " _-"
    ).strip() or "Customer"
    safe_invoice = "".join(
        c for c in invoice_number if c.isalnum() or c in "_-"
    ).strip() or "invoice"

    filename = f"Invoice_{safe_invoice}_{safe_customer}.pdf"
    dest_dir = Path.home() / "Documents" / "MahendraInvoices"
    dest_dir.mkdir(parents=True, exist_ok=True)
    destination = dest_dir / filename

    # Avoid file-in-use errors on Windows by appending a counter
    if destination.exists():
        for i in range(1, 100):
            candidate = dest_dir / f"Invoice_{safe_invoice}_{safe_customer}_{i}.pdf"
            if not candidate.exists():
                destination = candidate
                break

    _write_pdf_sync(invoice_id, destination)
    return destination


def copy_file_to_clipboard(path: Path) -> None:
    """Copy a file to the system clipboard so it can be pasted (Ctrl+V)."""
    from PySide6.QtCore import QMimeData, QUrl
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return
    clipboard = app.clipboard()
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(path))])
    clipboard.setMimeData(mime)


def open_whatsapp(phone: str, message: str) -> bool:
    """Open a WhatsApp chat with a pre-filled message."""
    digits = sanitize_phone(phone)
    if not digits:
        raise ValueError("No valid mobile number available for this customer.")
    encoded = urllib.parse.quote(message)
    url = f"https://wa.me/{digits}?text={encoded}"
    webbrowser.open(url)
    return True


def share_invoice_pdf(parent, invoice_id: int, customer_name: str,
                      business_name: str, invoice_number: str,
                      phone: str) -> None:
    """Full flow: generate PDF → copy to clipboard → open WhatsApp.

    Shows a guidance dialog at the end so the user knows what to do.
    """
    from PySide6.QtWidgets import QMessageBox

    from app.pdf.pdf_service import _showGenerating
    _showGenerating(parent)

    # 1. Generate PDF
    pdf_path = generate_pdf(invoice_id, customer_name, invoice_number)

    # 2. Copy PDF to clipboard
    copy_file_to_clipboard(pdf_path)

    # 3. Build short message and open WhatsApp
    msg = build_short_message(customer_name, business_name, invoice_number)
    open_whatsapp(phone, msg)

    # 4. Show guidance dialog
    QMessageBox.information(
        parent,
        "WhatsApp — Invoice PDF Ready",
        f"Invoice PDF has been generated and copied to your clipboard.\n\n"
        f"File: {pdf_path.name}\n\n"
        f"Steps:\n"
        f"1. In the WhatsApp chat, press Ctrl+V to paste the PDF\n"
        f"2. Add any extra message if needed\n"
        f"3. Hit Send!\n\n"
        f"The PDF is also saved at:\n{pdf_path.parent}",
    )
