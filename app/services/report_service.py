"""Reports service using aggregation queries and deep analytics.

Provides:
- Income & Cash Inflow Aggregations
- GSTR-1 Ready Tax Breakdown (Taxable Value, CGST, SGST, IGST, B2B vs B2C)
- Sales by Furniture Room / Area (Revenue, Item Count, % Share)
- Top Customers Analysis (Billed, Paid, Balance Due)
- Payment Mode Distribution (Cash, UPI, Bank Transfer, Cheque)
- Date Presets: Today, Week, Month, Quarter, Financial Year (FY), Last FY, All Time, Custom
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload, selectinload

from app.database.database import get_session
from app.models.models import Customer, Invoice, InvoiceItem, Payment
from app.services import business_service
from app.utils.cache import cache


def _today() -> date:
    return datetime.now(tz=timezone.utc).date()


def _current_financial_year(today: date) -> tuple[date, date]:
    """Indian Financial Year: April 1 to March 31."""
    if today.month >= 4:
        start_year = today.year
    else:
        start_year = today.year - 1
    return date(start_year, 4, 1), date(start_year + 1, 3, 31)


def _last_financial_year(today: date) -> tuple[date, date]:
    """Previous Indian Financial Year."""
    if today.month >= 4:
        start_year = today.year - 1
    else:
        start_year = today.year - 2
    return date(start_year, 4, 1), date(start_year + 1, 3, 31)


def _current_quarter(today: date) -> tuple[date, date]:
    """Indian FY Quarters: Q1 (Apr-Jun), Q2 (Jul-Sep), Q3 (Oct-Dec), Q4 (Jan-Mar)."""
    m = today.month
    y = today.year
    if 4 <= m <= 6:
        return date(y, 4, 1), date(y, 6, 30)
    if 7 <= m <= 9:
        return date(y, 7, 1), date(y, 9, 30)
    if 10 <= m <= 12:
        return date(y, 10, 1), date(y, 12, 31)
    return date(y, 1, 1), date(y, 3, 31)


def _date_range(period: str, start=None, end=None):
    today = _today()
    p = (period or "").lower().strip()
    if p in ("today",):
        return today, today
    if p in ("week", "this week"):
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        return monday, sunday
    if p in ("month", "this month"):
        return today.replace(day=1), today
    if p in ("quarter", "this quarter"):
        return _current_quarter(today)
    if p in ("year", "this year"):
        return today.replace(month=1, day=1), today
    if p in ("fy", "financial year", "this fy"):
        return _current_financial_year(today)
    if p in ("last_fy", "last financial year"):
        return _last_financial_year(today)
    if p in ("all", "all time"):
        return None, None
    if p in ("custom", "custom range"):
        return start, end
    return today.replace(day=1), today


def income_summary(period="today", start=None, end=None) -> dict:
    s, e = _date_range(period, start, end)
    session = get_session()
    try:
        q = session.query(
            func.coalesce(func.sum(Payment.amount), 0),
            func.count(Payment.id),
        )
        if s:
            q = q.filter(Payment.date >= s)
        if e:
            q = q.filter(Payment.date <= e)
        income, count = q.one()
        return {"income": float(income or 0), "payment_count": count or 0, "start": s, "end": e}
    finally:
        session.close()


def totals_overview() -> dict:
    cached = cache.get("report_totals")
    if cached is not None:
        return cached
    session = get_session()
    try:
        total_income = session.query(func.coalesce(func.sum(Payment.amount), 0)).scalar() or 0
        total_billed = (
            session.query(func.coalesce(func.sum(Invoice.grand_total), 0))
            .filter(Invoice.status != "DRAFT")
            .scalar() or 0
        )
        invoice_count = session.query(func.count(Invoice.id)).filter(Invoice.status != "DRAFT").scalar() or 0
        customer_count = session.query(func.count(Customer.id)).scalar() or 0
        result = {
            "total_income": float(total_income or 0),
            "total_outstanding": float(max(total_billed - total_income, 0)),
            "invoice_count": invoice_count,
            "customer_count": customer_count,
            "total_billed": float(total_billed or 0),
        }
        cache.set("report_totals", result, ttl=30)
        return result
    finally:
        session.close()


def payment_history(limit=200):
    cache_key = f"payment_history:{limit}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    session = get_session()
    try:
        result = (
            session.query(Payment)
            .join(Invoice)
            .options(joinedload(Payment.invoice).joinedload(Invoice.customer))
            .order_by(Payment.date.desc(), Payment.id.desc())
            .limit(limit)
            .all()
        )
        cache.set(cache_key, result, ttl=30)
        return result
    finally:
        session.close()


def monthly_income(months=12) -> list[dict]:
    session = get_session()
    try:
        today = _today()
        start = (today.replace(day=1) - timedelta(days=365)) if months >= 12 else today.replace(day=1)
        rows = (
            session.query(
                func.strftime("%Y-%m", Payment.date).label("month"),
                func.coalesce(func.sum(Payment.amount), 0).label("total"),
            )
            .filter(Payment.date >= start)
            .group_by("month")
            .order_by("month")
            .all()
        )
        return [{"month": r.month, "total": float(r[1])} for r in rows]
    finally:
        session.close()


def get_analytics_summary(period="month", start=None, end=None) -> dict:
    """Comprehensive financial and tax metrics for the given period."""
    s, e = _date_range(period, start, end)
    session = get_session()
    try:
        # Invoices issued in period
        inv_q = session.query(
            func.coalesce(func.sum(Invoice.grand_total), 0).label("billed"),
            func.coalesce(func.sum(Invoice.subtotal - Invoice.discount), 0).label("taxable"),
            func.coalesce(func.sum(Invoice.gst_amount), 0).label("gst"),
            func.count(Invoice.id).label("inv_count"),
        ).filter(Invoice.status != "DRAFT")

        if s:
            inv_q = inv_q.filter(Invoice.invoice_date >= s)
        if e:
            inv_q = inv_q.filter(Invoice.invoice_date <= e)

        inv_row = inv_q.one()

        # Payments received in period
        pay_q = session.query(
            func.coalesce(func.sum(Payment.amount), 0).label("income"),
            func.count(Payment.id).label("pay_count"),
        )
        if s:
            pay_q = pay_q.filter(Payment.date >= s)
        if e:
            pay_q = pay_q.filter(Payment.date <= e)

        pay_row = pay_q.one()

        # All-time overview
        total_income_all = session.query(func.coalesce(func.sum(Payment.amount), 0)).scalar() or 0
        total_billed_all = (
            session.query(func.coalesce(func.sum(Invoice.grand_total), 0))
            .filter(Invoice.status != "DRAFT")
            .scalar() or 0
        )
        total_receivables = max(float(total_billed_all) - float(total_income_all), 0.0)
        total_customers = session.query(func.count(Customer.id)).scalar() or 0

        return {
            "period_billed": float(inv_row.billed or 0),
            "period_taxable": float(inv_row.taxable or 0),
            "period_gst": float(inv_row.gst or 0),
            "period_invoices_count": int(inv_row.inv_count or 0),
            "period_income": float(pay_row.income or 0),
            "period_payments_count": int(pay_row.pay_count or 0),
            "total_receivables": float(total_receivables),
            "total_billed_all": float(total_billed_all),
            "total_income_all": float(total_income_all),
            "total_customers": int(total_customers),
            "start_date": s,
            "end_date": e,
        }
    finally:
        session.close()


def gst_register_report(period="month", start=None, end=None) -> dict:
    """GSTR-1 compliant tax register with invoice-level CGST/SGST/IGST breakdown."""
    s, e = _date_range(period, start, end)
    profile = business_service.get_profile()
    biz_state = (profile.state.strip().lower() if profile and profile.state else "")

    session = get_session()
    try:
        q = (
            session.query(Invoice)
            .options(joinedload(Invoice.customer), selectinload(Invoice.payments))
            .filter(Invoice.status != "DRAFT")
        )
        if s:
            q = q.filter(Invoice.invoice_date >= s)
        if e:
            q = q.filter(Invoice.invoice_date <= e)

        invoices = q.order_by(Invoice.invoice_date.desc(), Invoice.id.desc()).all()

        total_taxable = Decimal("0.00")
        total_cgst = Decimal("0.00")
        total_sgst = Decimal("0.00")
        total_igst = Decimal("0.00")
        total_gst = Decimal("0.00")
        total_grand = Decimal("0.00")

        b2b_count = 0
        b2b_taxable = Decimal("0.00")
        b2b_gst = Decimal("0.00")
        b2c_count = 0
        b2c_taxable = Decimal("0.00")
        b2c_gst = Decimal("0.00")

        rows = []
        for inv in invoices:
            cust = inv.customer
            c_name = cust.name if cust else "Walk-in Customer"
            c_mobile = cust.mobile if cust else "-"
            c_gstin = (cust.gstin.strip().upper() if cust and cust.gstin else "")
            c_state = (cust.state.strip() if cust and cust.state else "")

            is_b2b = bool(c_gstin)
            taxable = Decimal(str(inv.subtotal or 0)) - Decimal(str(inv.discount or 0))
            if taxable < Decimal("0"):
                taxable = Decimal("0.00")
            gst_amt = Decimal(str(inv.gst_amount or 0))
            grand = Decimal(str(inv.grand_total or 0))
            rate = float(inv.gst_rate or 0)

            # Determine CGST/SGST vs IGST
            # If customer state is provided and differs from business state -> IGST
            # Otherwise -> Split into CGST (50%) and SGST (50%)
            is_interstate = False
            if biz_state and c_state:
                if c_state.strip().lower() != biz_state:
                    is_interstate = True

            if is_interstate:
                cgst = Decimal("0.00")
                sgst = Decimal("0.00")
                igst = gst_amt
            else:
                cgst = (gst_amt / Decimal("2")).quantize(Decimal("0.01"))
                sgst = (gst_amt - cgst).quantize(Decimal("0.01"))
                igst = Decimal("0.00")

            total_taxable += taxable
            total_cgst += cgst
            total_sgst += sgst
            total_igst += igst
            total_gst += gst_amt
            total_grand += grand

            if is_b2b:
                b2b_count += 1
                b2b_taxable += taxable
                b2b_gst += gst_amt
            else:
                b2c_count += 1
                b2c_taxable += taxable
                b2c_gst += gst_amt

            paid = sum(Decimal(str(p.amount or 0)) for p in (inv.payments or []))
            balance = max(grand - paid, Decimal("0.00"))

            rows.append({
                "id": inv.id,
                "invoice_number": inv.invoice_number,
                "date": inv.invoice_date,
                "customer_name": c_name,
                "customer_mobile": c_mobile,
                "customer_gstin": c_gstin or "-",
                "customer_state": c_state or "-",
                "is_b2b": is_b2b,
                "taxable_value": float(taxable),
                "gst_rate": rate,
                "cgst": float(cgst),
                "sgst": float(sgst),
                "igst": float(igst),
                "gst_amount": float(gst_amt),
                "grand_total": float(grand),
                "paid_amount": float(paid),
                "balance": float(balance),
                "status": inv.status,
            })

        return {
            "rows": rows,
            "total_invoices": len(rows),
            "total_taxable": float(total_taxable),
            "total_cgst": float(total_cgst),
            "total_sgst": float(total_sgst),
            "total_igst": float(total_igst),
            "total_gst": float(total_gst),
            "total_grand": float(total_grand),
            "b2b_count": b2b_count,
            "b2b_taxable": float(b2b_taxable),
            "b2b_gst": float(b2b_gst),
            "b2c_count": b2c_count,
            "b2c_taxable": float(b2c_taxable),
            "b2c_gst": float(b2c_gst),
            "start_date": s,
            "end_date": e,
        }
    finally:
        session.close()


def furniture_sales_by_area(period="month", start=None, end=None) -> list[dict]:
    """Aggregate furniture sales volume and revenue by room / area."""
    s, e = _date_range(period, start, end)
    session = get_session()
    try:
        q = (
            session.query(
                func.coalesce(func.nullif(func.trim(InvoiceItem.area), ""), "General / Other").label("area_name"),
                func.coalesce(func.sum(InvoiceItem.amount), 0).label("area_total"),
                func.count(InvoiceItem.id).label("item_count"),
            )
            .join(Invoice, InvoiceItem.invoice_id == Invoice.id)
            .filter(Invoice.status != "DRAFT")
        )
        if s:
            q = q.filter(Invoice.invoice_date >= s)
        if e:
            q = q.filter(Invoice.invoice_date <= e)

        grouped = (
            q.group_by("area_name")
            .order_by(func.coalesce(func.sum(InvoiceItem.amount), 0).desc())
            .all()
        )

        total_rev = sum(float(g.area_total or 0) for g in grouped)
        results = []
        for g in grouped:
            rev = float(g.area_total or 0)
            pct = (rev / total_rev * 100.0) if total_rev > 0 else 0.0
            results.append({
                "area": g.area_name.upper(),
                "revenue": rev,
                "item_count": int(g.item_count or 0),
                "percent": round(pct, 1),
            })
        return results
    finally:
        session.close()


def top_customers_analytics(period="month", start=None, end=None, limit=20) -> list[dict]:
    """Top clients in period with total billed, paid, and outstanding balances."""
    s, e = _date_range(period, start, end)
    session = get_session()
    try:
        q = (
            session.query(Invoice)
            .options(joinedload(Invoice.customer), selectinload(Invoice.payments))
            .filter(Invoice.status != "DRAFT")
        )
        if s:
            q = q.filter(Invoice.invoice_date >= s)
        if e:
            q = q.filter(Invoice.invoice_date <= e)

        invoices = q.all()

        cust_map: dict[int, dict] = {}
        for inv in invoices:
            cid = inv.customer_id or 0
            if cid not in cust_map:
                c = inv.customer
                cust_map[cid] = {
                    "id": cid,
                    "name": c.name if c else "Walk-in Customer",
                    "mobile": c.mobile if c else "-",
                    "gstin": c.gstin if c else "-",
                    "city": c.city if c else "-",
                    "invoices_count": 0,
                    "total_billed": Decimal("0.00"),
                    "total_paid": Decimal("0.00"),
                }
            cm = cust_map[cid]
            cm["invoices_count"] += 1
            cm["total_billed"] += Decimal(str(inv.grand_total or 0))
            cm["total_paid"] += sum(Decimal(str(p.amount or 0)) for p in (inv.payments or []))

        result = []
        for cm in cust_map.values():
            billed = float(cm["total_billed"])
            paid = float(cm["total_paid"])
            bal = max(billed - paid, 0.0)
            pct_paid = (paid / billed * 100.0) if billed > 0 else 100.0
            result.append({
                "id": cm["id"],
                "name": cm["name"],
                "mobile": cm["mobile"],
                "gstin": cm["gstin"],
                "city": cm["city"],
                "invoices_count": cm["invoices_count"],
                "total_billed": billed,
                "total_paid": paid,
                "balance_due": bal,
                "compliance_pct": round(pct_paid, 1),
            })

        result.sort(key=lambda x: x["total_billed"], reverse=True)
        return result[:limit]
    finally:
        session.close()


def payment_modes_breakdown(period="month", start=None, end=None) -> list[dict]:
    """Breakdown of collections by payment mode (Cash, UPI, Cheque, Transfer)."""
    s, e = _date_range(period, start, end)
    session = get_session()
    try:
        q = session.query(
            func.coalesce(func.nullif(Payment.mode, ""), "Other").label("mode_name"),
            func.coalesce(func.sum(Payment.amount), 0).label("mode_total"),
            func.count(Payment.id).label("mode_count"),
        )
        if s:
            q = q.filter(Payment.date >= s)
        if e:
            q = q.filter(Payment.date <= e)

        grouped = q.group_by("mode_name").order_by(func.coalesce(func.sum(Payment.amount), 0).desc()).all()
        total_col = sum(float(g.mode_total or 0) for g in grouped)

        results = []
        for g in grouped:
            amt = float(g.mode_total or 0)
            pct = (amt / total_col * 100.0) if total_col > 0 else 0.0
            results.append({
                "mode": g.mode_name,
                "amount": amt,
                "count": int(g.mode_count or 0),
                "percent": round(pct, 1),
            })
        return results
    finally:
        session.close()


def payment_history_ledger(period="month", start=None, end=None, limit=250) -> list[dict]:
    """Chronological payments ledger with customer details for export/viewing."""
    s, e = _date_range(period, start, end)
    session = get_session()
    try:
        q = (
            session.query(Payment)
            .join(Invoice)
            .options(joinedload(Payment.invoice).joinedload(Invoice.customer))
        )
        if s:
            q = q.filter(Payment.date >= s)
        if e:
            q = q.filter(Payment.date <= e)

        pays = q.order_by(Payment.date.desc(), Payment.id.desc()).limit(limit).all()

        results = []
        for p in pays:
            inv = p.invoice
            cust = inv.customer if inv else None
            results.append({
                "id": p.id,
                "date": p.date,
                "invoice_number": inv.invoice_number if inv else "-",
                "customer_name": cust.name if cust else "Unknown",
                "customer_mobile": cust.mobile if cust else "-",
                "mode": p.mode or "Cash",
                "reference": p.reference or "-",
                "amount": float(p.amount or 0),
                "notes": p.notes or "",
            })
        return results
    finally:
        session.close()
