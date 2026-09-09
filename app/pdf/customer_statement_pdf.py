"""Customer Account Statement (Khata Passbook) PDF Generator.

Produces an executive, bank-passbook style A4 Statement PDF for any customer,
detailing all invoices (debits), payments (credits), running balance, and
bank payment / UPI QR details for instant settlement.
"""
from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path

from app.pdf.html_template import _generate_upi_qr, _media_to_data_uri, _money_inr
from app.pdf.theme import get_theme
from app.services import business_service, customer_service


def _esc(v) -> str:
    if v is None:
        return ""
    return html.escape(str(v), quote=True)


def build_customer_statement_html(customer_id: int) -> str:
    customer = customer_service.get_customer(customer_id)
    if not customer:
        raise ValueError(f"Customer {customer_id} not found.")

    profile = business_service.get_profile()
    theme = get_theme(getattr(profile, "pdf_theme", "colour") if profile else "colour")
    currency = getattr(profile, "currency", "₹") or "₹"

    # Business details
    biz_name = getattr(profile, "business_name", "Business Name") if profile else "Business Name"
    biz_mob = getattr(profile, "mobile", "") if profile else ""
    biz_email = getattr(profile, "email", "") if profile else ""
    biz_gst = getattr(profile, "gstin", "") if profile else ""
    biz_addr = getattr(profile, "address", "") if profile else ""
    logo_uri = _media_to_data_uri(getattr(profile, "logo_path", None) if profile else None, upscale_min=80)

    # Collect transactions
    invs = customer_service.customer_invoices(customer_id)
    pays = customer_service.customer_payments(customer_id)

    events = []
    for inv in invs:
        dt = inv.invoice_date or datetime.now(tz=timezone.utc).date()
        amt = float(inv.grand_total or 0)
        events.append({
            "date": dt,
            "sort_key": (dt, 0, inv.id),
            "type": "INVOICE",
            "desc": f"Invoice {inv.invoice_number}",
            "ref": inv.invoice_number,
            "debit": amt,
            "credit": 0.0,
        })

    for p in pays:
        dt = p.date or datetime.now(tz=timezone.utc).date()
        amt = float(p.amount or 0)
        inv_ref = p.invoice.invoice_number if p.invoice else "Advance"
        desc = f"Payment Received ({p.mode})" + (f" - {p.reference}" if p.reference else "")
        events.append({
            "date": dt,
            "sort_key": (dt, 1, p.id),
            "type": "PAYMENT",
            "desc": desc,
            "ref": inv_ref,
            "debit": 0.0,
            "credit": amt,
        })

    events.sort(key=lambda x: x["sort_key"])

    # Compute running balance
    total_invoiced = 0.0
    total_paid = 0.0
    running = 0.0
    rows_html = []
    alt = False

    for i, ev in enumerate(events, 1):
        debit = ev["debit"]
        credit = ev["credit"]
        total_invoiced += debit
        total_paid += credit
        running += (debit - credit)

        d_txt = _money_inr(debit, currency) if debit > 0 else "-"
        c_txt = _money_inr(credit, currency) if credit > 0 else "-"
        b_txt = _money_inr(running, currency)
        b_col = theme.red if running > 0 else "#059669"

        row_cls = "r alt" if alt else "r"
        alt = not alt

        date_str = ev["date"].strftime("%d-%b-%Y") if hasattr(ev["date"], "strftime") else str(ev["date"])
        type_badge = (
            '<span class="badge badge-inv">INVOICE</span>' if ev["type"] == "INVOICE"
            else '<span class="badge badge-pay">PAYMENT</span>'
        )

        rows_html.append(
            f'<tr class="{row_cls}">'
            f'  <td class="c-sn">{i}</td>'
            f'  <td class="c-date">{date_str}</td>'
            f'  <td class="c-type">{type_badge}</td>'
            f'  <td class="c-desc"><b>{_esc(ev["desc"])}</b></td>'
            f'  <td class="c-ref">{_esc(ev["ref"])}</td>'
            f'  <td class="c-num c-deb">{d_txt}</td>'
            f'  <td class="c-num c-crd">{c_txt}</td>'
            f'  <td class="c-num c-bal" style="color:{b_col};">{b_txt}</td>'
            f'</tr>'
        )

    if not rows_html:
        rows_html.append(
            '<tr><td colspan="8" style="text-align:center;padding:12px;color:#64748B;">No transactions recorded for this customer yet.</td></tr>'
        )

    closing_balance = max(total_invoiced - total_paid, 0.0)

    # Bank & UPI Details
    bank_name = getattr(profile, "bank_name", "") if profile else ""
    account_no = getattr(profile, "account_number", "") if profile else ""
    ifsc_code = getattr(profile, "ifsc_code", "") if profile else ""
    account_holder = getattr(profile, "account_holder", "") if profile else ""
    upi_id = getattr(profile, "upi_id", "") if profile else ""
    upi_qr_enabled = getattr(profile, "upi_qr_enabled", True) if profile else True

    qr_uri = _generate_upi_qr(
        upi_id,
        account_holder or biz_name,
        amount=closing_balance,
        note=f"Statement {customer.name}",
    ) if (upi_id and upi_qr_enabled and closing_balance > 0) else ""

    bank_html = ""
    if bank_name or upi_id:
        qr_img = f'<div class="qr-box"><img src="{qr_uri}"/><div class="qr-lbl">Scan to Clear Balance</div></div>' if qr_uri else ""
        bank_html = (
            f'<div class="bank-box">'
            f'  <div class="bb-info">'
            f'    <div class="bb-title">Bank Payment Details</div>'
            f'    {f"<div class=bb-r><b>Bank:</b> {_esc(bank_name)}</div>" if bank_name else ""}'
            f'    {f"<div class=bb-r><b>A/C No:</b> {_esc(account_no)}</div>" if account_no else ""}'
            f'    {f"<div class=bb-r><b>IFSC:</b> {_esc(ifsc_code)}</div>" if ifsc_code else ""}'
            f'    {f"<div class=bb-r><b>A/C Holder:</b> {_esc(account_holder)}</div>" if account_holder else ""}'
            f'    {f"<div class=bb-r><b>UPI ID:</b> {_esc(upi_id)}</div>" if upi_id else ""}'
            f'  </div>'
            f'  {qr_img}'
            f'</div>'
        )

    today_str = datetime.now(tz=timezone.utc).strftime("%d-%b-%Y")
    logo_tag = f'<img src="{logo_uri}" class="logo-img"/>' if logo_uri else ""

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<style>
@page {{ size: A4 portrait; margin: 12mm 14mm 12mm 14mm; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Inter', Roboto, Arial, sans-serif;
  color: {theme.ink}; font-size: 9.5px; line-height: 1.35; -webkit-print-color-adjust: exact;
}}
.head {{ display: flex; align-items: center; justify-content: space-between; padding-bottom: 3mm; border-bottom: 1mm solid {theme.navy}; }}
.head-left {{ display: flex; align-items: center; gap: 4mm; }}
.logo-img {{ max-height: 18mm; max-width: 40mm; object-fit: contain; }}
.biz-name {{ font-size: 19px; font-weight: 800; color: {theme.navy}; text-transform: uppercase; letter-spacing: 0.4px; }}
.biz-sub {{ font-size: 8.5px; color: {theme.muted}; margin-top: 1px; line-height: 1.4; }}
.head-right {{ text-align: right; }}
.doc-title {{ font-size: 16px; font-weight: 800; color: #ffffff; background: {theme.navy}; padding: 2mm 6mm; letter-spacing: 2px; border-radius: 1mm; display: inline-block; }}
.doc-date {{ font-size: 8.5px; color: {theme.muted}; margin-top: 1.5mm; font-weight: 600; }}

.card-grid {{ display: flex; gap: 4mm; margin-top: 3.5mm; }}
.info-card {{ flex: 1; border: 0.25mm solid {theme.border}; border-top: 0.8mm solid {theme.navy}; border-radius: 1.2mm; padding: 2.5mm 3.5mm; background: #ffffff; }}
.card-lbl {{ font-size: 7.5px; font-weight: 800; color: {theme.gold_dark}; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 1.5mm; }}
.card-name {{ font-size: 12px; font-weight: 800; color: {theme.navy}; margin-bottom: 1mm; }}
.card-line {{ font-size: 8.8px; color: {theme.muted}; margin-top: 0.8mm; line-height: 1.35; }}

.kpi-grid {{ display: flex; gap: 3.5mm; margin-top: 3.5mm; }}
.kpi-box {{ flex: 1; border: 0.25mm solid {theme.border}; border-radius: 1.2mm; padding: 2.2mm 3mm; text-align: center; background: #FAFBFD; }}
.kpi-box.due {{ background: #FEF2F2; border-color: #FCA5A5; }}
.kpi-lbl {{ font-size: 7.8px; font-weight: 800; color: {theme.muted}; text-transform: uppercase; letter-spacing: 0.8px; }}
.kpi-val {{ font-size: 13px; font-weight: 800; color: {theme.navy}; margin-top: 1mm; }}
.kpi-box.due .kpi-val {{ color: {theme.red}; }}

table {{ width: 100%; border-collapse: collapse; margin-top: 4mm; border: 0.25mm solid {theme.border}; }}
thead tr {{ background: {theme.navy}; color: #ffffff; }}
th {{ padding: 2mm 2mm; font-size: 8.5px; font-weight: 800; letter-spacing: 0.4px; text-align: left; border-right: 0.2mm solid rgba(255,255,255,0.15); }}
th.t-ar, td.c-num {{ text-align: right; }}
td {{ padding: 1.4mm 2mm; font-size: 8.8px; border-bottom: 0.2mm solid {theme.border}; border-right: 0.2mm solid {theme.border}; }}
tr.alt {{ background: #F8FAFC; }}
.c-sn {{ text-align: center; width: 8mm; }}
.c-date {{ width: 22mm; white-space: nowrap; }}
.c-type {{ width: 18mm; text-align: center; }}
.c-ref {{ width: 24mm; font-family: monospace; font-size: 8.5px; }}
.c-deb {{ font-weight: 700; color: {theme.ink}; width: 26mm; }}
.c-crd {{ font-weight: 700; color: #059669; width: 26mm; }}
.c-bal {{ font-weight: 800; width: 28mm; }}

.badge {{ display: inline-block; padding: 0.6mm 2mm; border-radius: 0.6mm; font-size: 7px; font-weight: 800; letter-spacing: 0.4px; }}
.badge-inv {{ background: #EFF6FF; color: #1E40AF; border: 0.2mm solid #BFDBFE; }}
.badge-pay {{ background: #ECFDF5; color: #065F46; border: 0.2mm solid #A7F3D0; }}

.summary-band {{ display: flex; justify-content: space-between; align-items: flex-start; margin-top: 4mm; gap: 4mm; }}
.bank-box {{ flex: 1; border: 0.25mm solid {theme.border}; border-top: 0.8mm solid {theme.gold}; border-radius: 1.2mm; padding: 2.5mm 3.5mm; background: #ffffff; display: flex; gap: 4mm; align-items: center; }}
.bb-title {{ font-size: 8px; font-weight: 800; color: {theme.gold_dark}; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 1.2mm; }}
.bb-r {{ font-size: 8.5px; color: {theme.muted}; margin-top: 0.6mm; line-height: 1.35; }}
.qr-box {{ width: 24mm; text-align: center; }}
.qr-box img {{ width: 22mm; height: 22mm; border: 0.2mm solid {theme.border}; border-radius: 0.8mm; }}
.qr-lbl {{ font-size: 6.8px; font-weight: 800; color: {theme.muted}; text-transform: uppercase; margin-top: 0.5mm; }}

.tot-card {{ width: 75mm; border: 0.25mm solid {theme.border}; border-radius: 1.2mm; padding: 2.5mm 3.5mm; background: #FAFBFD; }}
.tot-r {{ display: flex; justify-content: space-between; font-size: 9px; padding: 0.8mm 0; }}
.tot-r.grand {{ font-size: 11.5px; font-weight: 800; border-top: 0.4mm solid {theme.navy}; margin-top: 1mm; padding-top: 1.5mm; }}
.tot-r.grand .tot-val {{ color: {theme.red}; }}

.sign-box {{ margin-top: 6mm; display: flex; justify-content: flex-end; }}
.sign-inner {{ text-align: center; width: 55mm; }}
.sign-line {{ border-top: 0.35mm solid {theme.ink}; margin-top: 8mm; padding-top: 1.2mm; font-size: 8.8px; font-weight: 700; color: {theme.navy}; }}
.sign-lbl {{ font-size: 7.5px; color: {theme.muted}; letter-spacing: 0.8px; margin-top: 0.6mm; }}

.foot {{ margin-top: 6mm; padding-top: 2mm; border-top: 0.25mm solid {theme.border}; display: flex; justify-content: space-between; font-size: 8px; color: {theme.muted}; }}
</style>
</head>
<body>

<div class="head">
  <div class="head-left">
    {logo_tag}
    <div>
      <div class="biz-name">{_esc(biz_name)}</div>
      <div class="biz-sub">
        {_esc(biz_addr)}<br/>
        Phone: {_esc(biz_mob)} | Email: {_esc(biz_email)} {f'| GSTIN: {_esc(biz_gst)}' if biz_gst else ''}
      </div>
    </div>
  </div>
  <div class="head-right">
    <div class="doc-title">ACCOUNT STATEMENT</div>
    <div class="doc-date">Generated: {today_str}</div>
  </div>
</div>

<div class="card-grid">
  <div class="info-card">
    <div class="card-lbl">Customer / Client</div>
    <div class="card-name">{_esc(customer.name)}</div>
    <div class="card-line"><b>Phone:</b> {_esc(customer.mobile or '-')}</div>
    {f'<div class="card-line"><b>Email:</b> {_esc(customer.email)}</div>' if customer.email else ''}
    {f'<div class="card-line"><b>Address:</b> {_esc(customer.address or "")}</div>' if customer.address else ''}
    {f'<div class="card-line"><b>GSTIN:</b> {_esc(customer.gstin)}</div>' if customer.gstin else ''}
  </div>
  <div class="info-card">
    <div class="card-lbl">Statement Period</div>
    <div class="card-name">Complete History</div>
    <div class="card-line"><b>Total Invoices:</b> {len(invs)}</div>
    <div class="card-line"><b>Total Receipts:</b> {len(pays)}</div>
    <div class="card-line"><b>Currency:</b> Indian Rupee ({currency})</div>
  </div>
</div>

<div class="kpi-grid">
  <div class="kpi-box">
    <div class="kpi-lbl">Total Billed</div>
    <div class="kpi-val">{_money_inr(total_invoiced, currency)}</div>
  </div>
  <div class="kpi-box">
    <div class="kpi-lbl">Total Paid / Received</div>
    <div class="kpi-val" style="color:#059669;">{_money_inr(total_paid, currency)}</div>
  </div>
  <div class="kpi-box due">
    <div class="kpi-lbl">Current Outstanding</div>
    <div class="kpi-val">{_money_inr(closing_balance, currency)}</div>
  </div>
</div>

<table>
  <thead>
    <tr>
      <th class="c-sn">#</th>
      <th>DATE</th>
      <th>TYPE</th>
      <th>TRANSACTION DETAILS</th>
      <th>REF / INV NO</th>
      <th class="t-ar">BILLED (DEBIT)</th>
      <th class="t-ar">PAID (CREDIT)</th>
      <th class="t-ar">BALANCE</th>
    </tr>
  </thead>
  <tbody>
    {"".join(rows_html)}
  </tbody>
</table>

<div class="summary-band">
  {bank_html}
  <div class="tot-card">
    <div class="tot-r"><span>Total Billed:</span><b>{_money_inr(total_invoiced, currency)}</b></div>
    <div class="tot-r"><span>Total Received:</span><b style="color:#059669;">{_money_inr(total_paid, currency)}</b></div>
    <div class="tot-r grand"><span>Closing Balance:</span><span class="tot-val">{_money_inr(closing_balance, currency)}</span></div>
  </div>
</div>

<div class="sign-box">
  <div class="sign-inner">
    <div class="sign-line">For {_esc(biz_name)}</div>
    <div class="sign-lbl">AUTHORIZED SIGNATORY</div>
  </div>
</div>

<div class="foot">
  <div>This is a computer generated customer statement. For queries, please contact {_esc(biz_mob)}.</div>
  <div>Page 1 of 1</div>
</div>

</body>
</html>
"""
    return html_doc


def save_customer_statement_pdf(customer_id: int, destination: Path) -> Path:
    """Render customer statement synchronously to destination file using QWebEngine."""
    html_content = build_customer_statement_html(customer_id)
    from app.pdf.pdf_service import _get_pdf_view, _print_html_to_file
    view = _get_pdf_view()
    _print_html_to_file(view, html_content, destination)
    return destination
