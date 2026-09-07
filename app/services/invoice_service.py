"""Invoice service — database is the source of truth.

Performance improvements:
  - selectinload/joinedload on all list queries to avoid N+1
  - Batched relationship loading for customer/payments/items
  - Single-session transaction handling via session_scope
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import or_
from sqlalchemy.orm import joinedload, selectinload

from app.database.database import get_session
from app.models.models import Customer, Invoice, InvoiceItem, Setting
from app.utils.cache import cache
from app.utils.calculations import amount_in_words, compute_full_invoice


def invoice_outstanding(invoice) -> float:
    paid = sum(float(p.amount or 0) for p in (invoice.payments or []))
    return max(float(invoice.grand_total or 0) - paid, 0)


def compute_status(grand_total, paid, db_status, due_date) -> str:
    """Compute the display status for an invoice.

    Works with any data source (ORM objects, dicts, raw values).
    Returns one of: DRAFT, UNPAID, PAID, PARTIALLY PAID, OVERDUE.
    """
    total = float(grand_total or 0)
    paid_f = float(paid or 0)
    if total == 0:
        return "DRAFT" if db_status == "DRAFT" else "UNPAID"
    if paid_f <= 0:
        if due_date and due_date < datetime.now(tz=timezone.utc).date():
            return "OVERDUE"
        return "UNPAID"
    if paid_f >= total:
        return "PAID"
    if due_date and due_date < datetime.now(tz=timezone.utc).date():
        return "OVERDUE"
    return "PARTIALLY PAID"


def invoice_status(invoice) -> str:
    paid = sum(float(p.amount or 0) for p in (invoice.payments or []))
    return compute_status(invoice.grand_total, paid, invoice.status, invoice.due_date)


def peek_next_invoice_number(prefix: str, customer_name: str | None = None,
                             year: int | None = None) -> str:
    """Return what the next invoice number WOULD be, without incrementing.

    Uses the profile's ``next_sequence_number`` and format template so the
    preview matches what will actually be generated.
    """
    session = get_session()
    try:
        from app.services.business_service import get_profile
        profile = get_profile()
        base_seq = int(getattr(profile, "next_sequence_number", 1) or 1) if profile else 1
        if customer_name:
            slug = _customer_slug(customer_name)
            yr = year or datetime.now(tz=timezone.utc).date().year
            key = f"invoice_seq_{slug}_{yr}"
            row = session.query(Setting).filter_by(key=key).first()
            seq = int(row.value) if row and row.value else 100
        else:
            key = "invoice_seq"
            row = session.query(Setting).filter_by(key=key).first()
            if row and row.value:
                seq = int(row.value)
            else:
                seq = base_seq - 1  # so next becomes base_seq
        return _compose_number(prefix, customer_name, year, seq + 1)
    finally:
        session.close()


def next_invoice_number(prefix: str, session=None, customer_name: str | None = None,
                        year: int | None = None) -> str:
    """Increment the counter and return the new invoice number.

    With ``customer_name``, the counter is per customer and year, producing
    ``CustomerName-PREFIX-YYYY-NNN``; ``year`` defaults to the current year.
    """
    own = session is None
    s = session if session else get_session()
    try:
        if customer_name:
            slug = _customer_slug(customer_name)
            yr = year or datetime.now(tz=timezone.utc).date().year
            key = f"invoice_seq_{slug}_{yr}"
            base = 100
        else:
            slug = None
            key = "invoice_seq"
            # Use the profile's next_sequence_number as the starting point
            from app.services.business_service import get_profile
            profile = get_profile()
            base = int(getattr(profile, "next_sequence_number", 1) or 1) - 1 if profile else 0
        row = s.query(Setting).filter_by(key=key).first()
        seq = int(row.value) if row and row.value else base
        seq += 1
        if row:
            row.value = str(seq)
        else:
            s.add(Setting(key=key, value=str(seq)))
        if own:
            s.commit()
        return _compose_number(prefix, customer_name, year, seq)
    finally:
        if own:
            s.close()


def _customer_slug(name: str | None) -> str:
    """Turn a customer name into a safe slug like ``Akash-Vishwakarma``."""
    if not name:
        return ""
    import re
    slug = re.sub(r"[^A-Za-z0-9]+", "-", str(name).strip()).strip("-")
    return slug or "CUSTOMER"


def _compose_number(prefix: str, customer_name: str | None, year: int | None, seq: int) -> str:
    """Build the display invoice number using the profile's format template.

    Format tokens:
        {PREFIX}  – the invoice prefix (e.g. INV)
        {SEQ}     – zero-padded sequence number (width from profile)
        {YEAR}    – 4-digit year
        {CUSTOMER}– customer slug (for customer-scoped numbering)
    If no format is configured, falls back to the legacy ``PREFIX-SEQ`` layout.
    """
    from app.services.business_service import get_profile
    profile = get_profile()
    fmt = getattr(profile, "invoice_format", "") if profile else ""
    digits = int(getattr(profile, "invoice_sequence_digits", 4) or 4)
    yr = year or datetime.now(tz=timezone.utc).date().year
    seq_str = str(seq).zfill(digits)

    if customer_name:
        slug = _customer_slug(customer_name)
        if fmt and "{CUSTOMER}" in fmt:
            result = fmt.replace("{PREFIX}", prefix)
            result = result.replace("{SEQ}", seq_str)
            result = result.replace("{YEAR}", str(yr))
            result = result.replace("{CUSTOMER}", slug)
            return result
        return f"{slug}-{prefix}-{yr}-{seq_str}"

    # Non-customer-scoped
    if fmt and ("{PREFIX}" in fmt or "{SEQ}" in fmt):
        result = fmt.replace("{PREFIX}", prefix)
        result = result.replace("{SEQ}", seq_str)
        result = result.replace("{YEAR}", str(yr))
        return result
    if fmt == "PREFIX-YEAR-SEQ":
        return f"{prefix}-{yr}-{seq_str}"
    if fmt == "PREFIX-SEQ-YEAR":
        return f"{prefix}-{seq_str}-{yr}"
    return f"{prefix}-{seq_str}"


def _compute_total(items_data, discount, gst_rate):
    """Compute row amounts, per-area totals and the overall totals.

    Returns ``(computed, totals)`` where ``computed`` is a list of per-row
    amounts (parallel to ``items_data``) and ``totals`` is the invoice-wide
    dict (subtotal/discount/gst/grand) from the area-wise engine. The subtotal
    is the sum of every area total, i.e. it covers all items.
    """
    result = compute_full_invoice(items_data, discount, gst_rate)
    result.pop("area_totals")
    computed, _subtotal = _compute_row_amounts(items_data)
    totals = result
    return computed, totals


def _compute_row_amounts(items_data):
    from app.utils.calculations import compute_rows
    return compute_rows(items_data)


def create_invoice(data: dict, items: list[dict]) -> Invoice:
    session = get_session()
    try:
        gst_enabled = bool(data.get("gst_enabled", True))
        gst_rate = data.get("gst_rate", 0) if gst_enabled else 0
        # Clamp discount to [0, ∞) at the service boundary
        raw_discount = data.get("discount", 0)
        safe_discount = max(float(raw_discount), 0.0) if raw_discount is not None else 0.0
        computed, totals = _compute_total(items, safe_discount, gst_rate)
        prefix = data.get("invoice_prefix", "INV")

        # Derive the customer name (for customer-scoped numbering) and year.
        customer_name = None
        if data.get("customer_id"):
            c = session.get(Customer, data["customer_id"])
            if c:
                customer_name = c.name
        inv_year = data.get("invoice_date", datetime.now(tz=timezone.utc).date()).year

        number = data.get("invoice_number") if data.get("invoice_number") else None
        if not number:
            number = next_invoice_number(prefix, session,
                                         customer_name=customer_name, year=inv_year)
        # Guard against duplicate invoice numbers (e.g. after manual DB edit)
        if session.query(Invoice).filter_by(invoice_number=number).first():
            number = next_invoice_number(prefix, session,
                                         customer_name=customer_name, year=inv_year)

        inv = Invoice(
            invoice_number=number,
            customer_id=data.get("customer_id"),
            project_id=data.get("project_id"),
            invoice_date=data.get("invoice_date", datetime.now(tz=timezone.utc).date()),
            due_date=data.get("due_date"),
            site_address=data.get("site_address"),
            status=data.get("status", "DRAFT"),
            discount=totals["discount"],
            gst_enabled=gst_enabled,
            gst_rate=totals["gst_rate"],
            subtotal=totals["subtotal"],
            gst_amount=totals["gst_amount"],
            grand_total=totals["grand_total"],
            amount_in_words=amount_in_words(totals["grand_total"]),
            notes=data.get("notes"),
        )
        session.add(inv)
        session.flush()

        for i, it in enumerate(items):
            val = computed[i]
            session.add(InvoiceItem(
                invoice_id=inv.id,
                area=it.get("area"),
                description=it.get("description"),
                size=it.get("size"),
                qty_raw=str(it.get("qty_raw")) if it.get("qty_raw") is not None else None,
                rate_raw=str(it.get("rate_raw")) if it.get("rate_raw") is not None else None,
                qty=_num(it.get("qty_raw")),
                rate=_num(it.get("rate_raw")),
                amount=val,
                sort_order=i,
            ))
        session.commit()
        cache.invalidate("dashboard_stats")
        cache.invalidate("report_totals")
        cache.invalidate_prefix("payment_history:")
        cache.invalidate_prefix("recent_")
        cache.invalidate_prefix("monthly_")
        cache.invalidate_prefix("cust_totals:")
        return (
            session.query(Invoice)
            .options(
                joinedload(Invoice.customer),
                joinedload(Invoice.project),
                selectinload(Invoice.items),
                selectinload(Invoice.payments),
            )
            .filter(Invoice.id == inv.id)
            .first()
        )
    finally:
        session.close()


def update_invoice(invoice_id: int, data: dict, items: list[dict]) -> Invoice:
    session = get_session()
    try:
        inv = session.get(Invoice, invoice_id)
        if inv is None:
            raise ValueError("Invoice not found")

        gst_enabled = bool(data.get("gst_enabled", inv.gst_enabled
                                    if getattr(inv, "gst_enabled", None) is not None
                                    else True))
        gst_rate = data.get("gst_rate", 0) if gst_enabled else 0
        # Clamp discount to [0, ∞) at the service boundary
        raw_discount = data.get("discount", 0)
        safe_discount = max(float(raw_discount), 0.0) if raw_discount is not None else 0.0
        computed, totals = _compute_total(items, safe_discount, gst_rate)

        inv.customer_id = data.get("customer_id", inv.customer_id)
        inv.project_id = data.get("project_id", inv.project_id)
        inv.invoice_date = data.get("invoice_date", inv.invoice_date)
        inv.due_date = data.get("due_date")
        inv.site_address = data.get("site_address")
        inv.status = data.get("status", inv.status)
        inv.discount = totals["discount"]
        inv.gst_enabled = gst_enabled
        inv.gst_rate = totals["gst_rate"]
        inv.subtotal = totals["subtotal"]
        inv.gst_amount = totals["gst_amount"]
        inv.grand_total = totals["grand_total"]
        inv.amount_in_words = amount_in_words(totals["grand_total"])
        inv.notes = data.get("notes")

        for old in list(inv.items):
            session.delete(old)
        session.flush()

        for i, it in enumerate(items):
            val = computed[i]
            session.add(InvoiceItem(
                invoice_id=inv.id,
                area=it.get("area"),
                description=it.get("description"),
                size=it.get("size"),
                qty_raw=str(it.get("qty_raw")) if it.get("qty_raw") is not None else None,
                rate_raw=str(it.get("rate_raw")) if it.get("rate_raw") is not None else None,
                qty=_num(it.get("qty_raw")),
                rate=_num(it.get("rate_raw")),
                amount=val,
                sort_order=i,
            ))

        session.commit()
        cache.invalidate("dashboard_stats")
        cache.invalidate("report_totals")
        cache.invalidate_prefix("payment_history:")
        cache.invalidate_prefix("recent_")
        cache.invalidate_prefix("monthly_")
        cache.invalidate_prefix("cust_totals:")
        # Expire the items collection so the identity map reloads fresh state,
        # otherwise the returned object would carry the pre-edit stale items.
        session.expire(inv, ["items"])
        return (
            session.query(Invoice)
            .options(
                joinedload(Invoice.customer),
                joinedload(Invoice.project),
                selectinload(Invoice.items),
                selectinload(Invoice.payments),
            )
            .filter(Invoice.id == inv.id)
            .first()
        )
    finally:
        session.close()


def _num(v):
    try:
        if v is None or str(v).strip() == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def get_invoice(invoice_id: int) -> Invoice | None:
    session = get_session()
    try:
        return (
            session.query(Invoice)
            .options(
                joinedload(Invoice.customer),
                joinedload(Invoice.project),
                selectinload(Invoice.items),
                selectinload(Invoice.payments),
            )
            .filter(Invoice.id == invoice_id)
            .first()
        )
    finally:
        session.close()


def get_invoice_status(invoice_id: int) -> str | None:
    """Lightweight query — only returns the status field, no eager loading."""
    session = get_session()
    try:
        inv = session.query(Invoice.status).filter(Invoice.id == invoice_id).first()
        return inv[0] if inv else None
    finally:
        session.close()


def search_invoices(query: str = "", status: str = "", limit: int = 200):
    session = get_session()
    try:
        q = session.query(Invoice).join(Customer, isouter=True)
        if query:
            pat = f"%{query}%"
            q = q.filter(
                or_(
                    Invoice.invoice_number.ilike(pat),
                    Customer.name.ilike(pat),
                    Customer.mobile.ilike(pat),
                )
            )
        if status:
            q = q.filter(Invoice.status == status)
        return (
            q.options(
                joinedload(Invoice.customer),
                selectinload(Invoice.payments),
            )
            .order_by(Invoice.invoice_date.desc(), Invoice.id.desc())
            .limit(limit)
            .all()
        )
    finally:
        session.close()


def delete_invoice(invoice_id: int) -> bool:
    session = get_session()
    try:
        inv = session.get(Invoice, invoice_id)
        if inv:
            session.delete(inv)
            session.commit()
            cache.invalidate("dashboard_stats")
            cache.invalidate("report_totals")
            cache.invalidate_prefix("payment_history:")
            cache.invalidate_prefix("recent_")
            cache.invalidate_prefix("monthly_")
            cache.invalidate_prefix("cust_totals:")
            return True
        return False
    finally:
        session.close()


def list_all_invoices(limit: int = 500):
    """List all invoices with customer + payments eagerly loaded (avoids N+1)."""
    session = get_session()
    try:
        return (
            session.query(Invoice)
            .options(
                joinedload(Invoice.customer),
                selectinload(Invoice.payments),
            )
            .order_by(Invoice.invoice_date.desc(), Invoice.id.desc())
            .limit(limit)
            .all()
        )
    finally:
        session.close()
