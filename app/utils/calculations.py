"""Pure calculation engine — deliberately separated from the UI.

Handles numeric rows, decimal quantities, and LS (text) rows without ever
producing NaN / Infinity / #VALUE! / undefined. When qty or rate is not a
number, the amount is treated as manual and returned untouched.
"""
from __future__ import annotations


def is_number(value) -> bool:
    """Return True if value can be parsed as a finite number."""
    if value is None:
        return False
    if isinstance(value, bool):
        return False
    try:
        f = float(value)
    except (TypeError, ValueError):
        return False
    import math
    return math.isfinite(f)


def to_number(value, default=0.0) -> float:
    if not is_number(value):
        return float(default)
    try:
        f = float(value)
    except (TypeError, ValueError):
        return float(default)
    return f


def format_qty(value) -> str:
    """Format a number preserving decimals, e.g. 10.5 -> '10.5'."""
    if not is_number(value):
        return str(value)
    f = to_number(value)
    if f == int(f):
        return str(int(f))
    return ("%g" % f)


def format_rate(value) -> str:
    if not is_number(value):
        return str(value)
    f = to_number(value)
    if f == int(f):
        return str(int(f))
    return ("%g" % f)


def row_amount(qty, rate, manual_amount=None):
    """Compute amount for a row.

    If both qty and rate are numeric -> qty * rate.
    Otherwise the row is LS / text -> return manual_amount (or None).
    Returns a numeric value or None (meaning: needs manual input).
    """
    if is_number(qty) and is_number(rate):
        return round(float(qty) * float(rate), 2)
    if manual_amount is not None and is_number(manual_amount):
        return round(float(manual_amount), 2)
    return None


def row_is_ls(qty, rate) -> bool:
    return not (is_number(qty) and is_number(rate))


def _row_fields(r):
    """Normalise a row (ORM object or dict) to (area, qty, rate, manual)."""
    if hasattr(r, "area") and hasattr(r, "qty_raw"):
        area = getattr(r, "area", "") or ""
        q = getattr(r, "qty_raw")
        rt = getattr(r, "rate_raw")
        manual = getattr(r, "amount")
    elif hasattr(r, "qty"):
        area = getattr(r, "area", "") or ""
        q = getattr(r, "qty")
        rt = getattr(r, "rate")
        manual = getattr(r, "amount")
    else:
        area = r.get("area", "") or ""
        q = r.get("qty_raw") if isinstance(r.get("qty_raw"), str) else r.get("qty")
        rt = r.get("rate_raw") if isinstance(r.get("rate_raw"), str) else r.get("rate")
        manual = r.get("amount")
    return area, q, rt, manual


def _normalise_area(area) -> str:
    area = (area or "").strip()
    return area or "OTHER"


def compute_rows(rows):
    """Compute each row's amount.

    rows: iterable of items with .qty_raw/.rate_raw/.amount (or dicts).
    Returns (list_of_computed_amounts, subtotal).
    """
    computed = []
    subtotal = 0.0
    for r in rows:
        _area, q, rt, manual = _row_fields(r)
        amt = row_amount(q, rt, manual)
        computed.append(amt)
        if amt is not None:
            subtotal += amt
    return computed, round(subtotal, 2)


def compute_area_totals(rows) -> dict:
    """Group items by area and return {area_name: area_total}.

    Each item's amount is computed with ``row_amount`` (numeric qty*rate, or the
    manually entered amount for LS/text rows). Every area present gets its own
    total, summing only the items that belong to it. There is no fixed limit on
    areas or items; empty areas are omitted.

    ``rows`` may be ORM objects or dicts. Returns a dict keyed by the normalised
    area name (whitespace-stripped, empty -> 'OTHER').
    """
    totals: dict = {}
    for r in rows:
        area, q, rt, manual = _row_fields(r)
        area = _normalise_area(area)
        amt = row_amount(q, rt, manual)
        if amt is None:
            continue
        totals[area] = totals.get(area, 0.0) + amt
    return {k: round(v, 2) for k, v in totals.items()}


def compute_full_invoice(rows, discount=0, gst_rate=0) -> dict:
    """Compute a complete invoice with an area-wise breakdown.

    Returns a dict with ``area_totals`` (per-area sums) plus the usual subtotal /
    discount / gst / grand_total numbers. The subtotal is the sum of all area
    totals, so it always includes every item belonging to any area.
    """
    area_totals = compute_area_totals(rows)
    subtotal = sum(area_totals.values())
    result = apply_gst(subtotal, discount, gst_rate)
    result["area_totals"] = area_totals
    return result


def apply_gst(subtotal, discount, gst_rate) -> dict:
    """Return subtotal, discount, gst, grand total."""
    disc = 0.0 if not is_number(discount) else float(discount)
    rate = 0.0 if not is_number(gst_rate) else float(gst_rate)
    nett = subtotal - disc
    gst = round(nett * rate / 100.0, 2)
    grand = nett + gst
    return {
        "subtotal": round(subtotal, 2),
        "discount": round(disc, 2),
        "gst_rate": round(rate, 2),
        "gst_amount": round(gst, 2),
        "grand_total": round(grand, 2),
    }


_NUM_WORDS = [
    "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight",
    "Nine", "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen",
    "Sixteen", "Seventeen", "Eighteen", "Nineteen",
]
_TENS = [
    "", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy",
    "Eighty", "Ninety",
]


def _two_digits(n):
    if n < 20:
        return _NUM_WORDS[n]
    return (_TENS[n // 10] + (" " + _NUM_WORDS[n % 10] if n % 10 else "")).strip()


def _three_digits(n):
    s = ""
    h = n // 100
    rem = n % 100
    if h:
        s += _NUM_WORDS[h] + " Hundred"
    if rem:
        if s:
            s += " "
        s += _two_digits(rem)
    return s


def amount_in_words(amount) -> str:
    """Indian numbering (crore/lakh/thousand) with paise."""
    if not is_number(amount):
        return "Zero Rupees Only"
    amount = float(amount)
    rupees = int(amount)
    paise = int(round((amount - rupees) * 100))

    def convert(n):
        if n == 0:
            return ""
        crore = n // 10000000
        n %= 10000000
        lakh = n // 100000
        n %= 100000
        thousand = n // 1000
        n %= 1000
        part = ""
        if crore:
            part += _three_digits(crore) + " Crore "
        if lakh:
            part += _three_digits(lakh) + " Lakh "
        if thousand:
            part += _three_digits(thousand) + " Thousand "
        part += _three_digits(n)
        return part.strip()

    words = convert(rupees) or "Zero"
    words += " Rupees"
    if paise:
        words += " and " + _two_digits(paise) + " Paise"
    words += " Only"
    return words
