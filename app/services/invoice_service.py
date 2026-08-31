"""Invoice service — database is the source of truth."""
from __future__ import annotations

from datetime import date

from sqlalchemy import or_

from app.database.database import get_session
from app.models.models import Customer, Invoice, InvoiceItem, Setting, Payment
from app.utils.calculations import amount_in_words, compute_full_invoice
from sqlalchemy.orm import joinedload, selectinload


def invoice_outstanding(invoice) -> float:
    paid = sum(float(p.amount or 0) for p in (invoice.payments or []))
    return max(float(invoice.grand_total or 0) - paid, 0)


def invoice_status(invoice) -> str:
    total = float(invoice.grand_total or 0)
    paid = sum(float(p.amount or 0) for p in (invoice.payments or []))
    if total == 0:
        return "DRAFT" if invoice.status == "DRAFT" else "UNPAID"
    if paid <= 0:
        from datetime import date
        if invoice.due_date and invoice.due_date < date.today():
            return "OVERDUE"
        return "UNPAID"
    if paid >= total:
        return "PAID"
    from datetime import date as _d
    if invoice.due_date and invoice.due_date < _d.today():
        return "OVERDUE"
    return "PARTIALLY PAID"


def next_invoice_number(prefix: str, session=None) -> str:
    own = session is None
    s = session if session else get_session()
    try:
        row = s.query(Setting).filter_by(key="invoice_seq").first()
        seq = int(row.value) if row and row.value else 0
        seq += 1
        if row:
            row.value = str(seq)
        else:
            s.add(Setting(key="invoice_seq", value=str(seq)))
        if own:
            s.commit()
        return f"{prefix}-{seq:04d}"
    finally:
        if own:
            s.close()


def _compute_total(items_data, discount, gst_rate):
    """Compute row amounts, per-area totals and the overall totals.

    Returns ``(computed, totals)`` where ``computed`` is a list of per-row
    amounts (parallel to ``items_data``) and ``totals`` is the invoice-wide
    dict (subtotal/discount/gst/grand) from the area-wise engine. The subtotal
    is the sum of every area total, i.e. it covers all items.
    """
    result = compute_full_invoice(items_data, discount, gst_rate)
    area_totals = result.pop("area_totals")
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
        computed, totals = _compute_total(items, data.get("discount", 0), gst_rate)
        number = data.get("invoice_number") if data.get("invoice_number") else None
        if not number:
            number = next_invoice_number(data.get("invoice_prefix", "INV"), session)
        # Guard against duplicate invoice numbers (e.g. after manual DB edit)
        if session.query(Invoice).filter_by(invoice_number=number).first():
            number = next_invoice_number(data.get("invoice_prefix", "INV"), session)

        inv = Invoice(
            invoice_number=number,
            customer_id=data.get("customer_id"),
            project_id=data.get("project_id"),
            invoice_date=data.get("invoice_date", date.today()),
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
        inv = session.query(Invoice).get(invoice_id)
        if inv is None:
            raise ValueError("Invoice not found")

        gst_enabled = bool(data.get("gst_enabled", inv.gst_enabled
                                    if getattr(inv, "gst_enabled", None) is not None
                                    else True))
        gst_rate = data.get("gst_rate", 0) if gst_enabled else 0
        computed, totals = _compute_total(items, data.get("discount", 0), gst_rate)

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
            q.options(joinedload(Invoice.customer), selectinload(Invoice.payments))
            .order_by(Invoice.invoice_date.desc(), Invoice.id.desc())
            .limit(limit)
            .all()
        )
    finally:
        session.close()


def delete_invoice(invoice_id: int) -> bool:
    session = get_session()
    try:
        inv = session.query(Invoice).get(invoice_id)
        if inv:
            session.delete(inv)
            session.commit()
            return True
        return False
    finally:
        session.close()


def list_all_invoices(limit: int = 500):
    session = get_session()
    try:
        return (
            session.query(Invoice)
            .options(joinedload(Invoice.customer), selectinload(Invoice.payments))
            .order_by(Invoice.invoice_date.desc(), Invoice.id.desc())
            .limit(limit)
            .all()
        )
    finally:
        session.close()
