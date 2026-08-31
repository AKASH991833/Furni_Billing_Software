"""WhatsApp sharing service.

Realistically, a standard wa.me URL can only open a chat with a pre-filled
text message; the WhatsApp Web/Desktop protocol does NOT let you auto-attach
a PDF file from a local path. So we:

  - Build a professional text message with customer/business/invoice details.
  - Open wa.me/<phone>?text=<encoded message>.
  - Provide a clearly-worded note explaining PDF attachment limitation,
    and (where the platform supports it) mention sending the PDF manually.

We never falsely claim the PDF attaches automatically.
"""
from __future__ import annotations

import urllib.parse
import webbrowser


def sanitize_phone(phone: str) -> str:
    """Normalise an Indian phone number to 91XXXXXXXXXX for wa.me URLs.

    Handles formats like:
      9876543210, 09876543210, +919876543210, 91-9876543210,
      +91 98765 43210, 098765-43210, etc.
    """
    digits = "".join(ch for ch in (phone or "") if ch.isdigit())
    if not digits:
        return ""
    # Strip leading 0 or country code 91 that was already dialled
    if digits.startswith("0"):
        digits = digits[1:]
    # Remove country code if already present (10-digit local number)
    if len(digits) > 12:
        # More than 12 digits — likely invalid; keep last 12
        digits = digits[-12:]
    if digits.startswith("91") and len(digits) == 12:
        return digits  # Already has country code
    if len(digits) == 10:
        return "91" + digits
    if len(digits) == 11 and digits.startswith("0"):
        return "91" + digits[1:]
    return digits  # Best effort — let wa.me validation catch bad numbers


def build_whatsapp_message(customer_name: str, business_name: str,
                           invoice_number: str, total, paid, outstanding) -> str:
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


def open_whatsapp(phone: str, message: str, base: str | None = None) -> bool:
    digits = sanitize_phone(phone)
    if not digits:
        raise ValueError("No valid mobile number available for this customer.")
    encoded = urllib.parse.quote(message)
    url = f"https://wa.me/{digits}?text={encoded}"
    webbrowser.open(url)
    return True
