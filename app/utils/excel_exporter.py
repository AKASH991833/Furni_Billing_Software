"""High-performance corporate-grade Excel export utility.

Generates beautifully formatted .xlsx workbooks with:
- Executive dark-navy header & typography
- KPI summary cards
- Currency and numeric data-type formatting (real numbers, not strings)
- Color-coded status badges (PAID, PARTIALLY PAID, UNPAID)
- Auto-adjusted column widths & frozen header panes
- Native interactive Excel charts (Bar, Column, Pie)
- CSV fallback compatibility
"""
from __future__ import annotations

import csv
import os
from datetime import date, datetime
from typing import Any, Sequence

import openpyxl
from openpyxl.chart import BarChart, PieChart, LineChart, Reference
from openpyxl.chart.series import SeriesLabel
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

# Palette definitions
NAVY_HEADER = "1E3A8A"
NAVY_TEXT = "FFFFFF"
ROW_ZEBRA = "F8FAFC"
ROW_WHITE = "FFFFFF"
BORDER_COLOR = "CBD5E1"
TOTAL_ROW_FILL = "F1F5F9"

# Status colors
STATUS_PAID_BG = "DCFCE7"
STATUS_PAID_FG = "166534"
STATUS_PARTIAL_BG = "FEF3C7"
STATUS_PARTIAL_FG = "92400E"
STATUS_UNPAID_BG = "FEE2E2"
STATUS_UNPAID_FG = "991B1B"

# Fonts
FONT_NAME = "Segoe UI"
FONT_TITLE = Font(name=FONT_NAME, size=16, bold=True, color="0F172A")
FONT_SUBTITLE = Font(name=FONT_NAME, size=10, italic=True, color="64748B")
FONT_HEADER = Font(name=FONT_NAME, size=11, bold=True, color=NAVY_TEXT)
FONT_DATA = Font(name=FONT_NAME, size=10, color="1E293B")
FONT_DATA_BOLD = Font(name=FONT_NAME, size=10, bold=True, color="0F172A")
FONT_TOTAL = Font(name=FONT_NAME, size=11, bold=True, color="0F172A")

# Fills
FILL_HEADER = PatternFill(start_color=NAVY_HEADER, end_color=NAVY_HEADER, fill_type="solid")
FILL_ZEBRA = PatternFill(start_color=ROW_ZEBRA, end_color=ROW_ZEBRA, fill_type="solid")
FILL_WHITE = PatternFill(start_color=ROW_WHITE, end_color=ROW_WHITE, fill_type="solid")
FILL_TOTAL = PatternFill(start_color=TOTAL_ROW_FILL, end_color=TOTAL_ROW_FILL, fill_type="solid")

# Borders
THIN_BORDER_SIDE = Side(style="thin", color=BORDER_COLOR)
DOUBLE_BORDER_SIDE = Side(style="double", color="0F172A")
CELL_BORDER = Border(left=THIN_BORDER_SIDE, right=THIN_BORDER_SIDE, top=THIN_BORDER_SIDE, bottom=THIN_BORDER_SIDE)
TOTAL_BORDER = Border(left=THIN_BORDER_SIDE, right=THIN_BORDER_SIDE, top=THIN_BORDER_SIDE, bottom=DOUBLE_BORDER_SIDE)

# Alignments
ALIGN_LEFT = Alignment(horizontal="left", vertical="center")
ALIGN_CENTER = Alignment(horizontal="center", vertical="center")
ALIGN_RIGHT = Alignment(horizontal="right", vertical="center")
ALIGN_HEADER = Alignment(horizontal="center", vertical="center", wrap_text=True)

# Formats
FMT_CURRENCY = "₹ #,##0.00"
FMT_NUMBER = "#,##0.00"
FMT_INTEGER = "#,##0"
FMT_PERCENT = "0.0%"
FMT_DATE = "yyyy-mm-dd"


def _safe_float(val: Any) -> float:
    if val is None or val == "":
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).replace("₹", "").replace(",", "").replace("%", "").strip()
    try:
        return float(s)
    except (ValueError, TypeError):
        return 0.0


def create_base_workbook(title: str, subtitle: str = "") -> tuple[openpyxl.Workbook, Any]:
    """Initialize a styled Excel workbook with title banner."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Analytics & Data"
    ws.views.sheetView[0].showGridLines = True

    # Title Row
    ws.cell(row=1, column=1, value=title).font = FONT_TITLE
    ws.cell(row=1, column=1).alignment = ALIGN_LEFT
    ws.row_dimensions[1].height = 28

    if subtitle:
        ws.cell(row=2, column=1, value=subtitle).font = FONT_SUBTITLE
        ws.cell(row=2, column=1).alignment = ALIGN_LEFT
        ws.row_dimensions[2].height = 18

    return wb, ws


def add_kpi_cards(ws: Any, start_row: int, cards: list[dict[str, Any]]) -> int:
    """Add styled executive KPI summary cards across top columns.
    cards: [{'label': 'Total Billed', 'value': 200000.0, 'format': 'currency'}, ...]
    """
    if not cards:
        return start_row

    ws.row_dimensions[start_row].height = 18
    ws.row_dimensions[start_row + 1].height = 24

    col = 1
    for card in cards:
        # Label cell
        lbl_cell = ws.cell(row=start_row, column=col, value=card.get("label", "").upper())
        lbl_cell.font = Font(name=FONT_NAME, size=9, bold=True, color="64748B")
        lbl_cell.alignment = ALIGN_CENTER
        lbl_cell.fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
        lbl_cell.border = Border(left=THIN_BORDER_SIDE, right=THIN_BORDER_SIDE, top=THIN_BORDER_SIDE)

        # Value cell
        raw_val = card.get("value", 0)
        fmt = card.get("format", "text")
        val_cell = ws.cell(row=start_row + 1, column=col)
        val_cell.font = Font(name=FONT_NAME, size=13, bold=True, color="1E3A8A")
        val_cell.alignment = ALIGN_CENTER
        val_cell.fill = PatternFill(start_color="F8FAFC", end_color="F8FAFC", fill_type="solid")
        val_cell.border = Border(left=THIN_BORDER_SIDE, right=THIN_BORDER_SIDE, bottom=THIN_BORDER_SIDE)

        if fmt == "currency":
            val_cell.value = _safe_float(raw_val)
            val_cell.number_format = FMT_CURRENCY
        elif fmt == "number":
            val_cell.value = _safe_float(raw_val)
            val_cell.number_format = FMT_INTEGER
        elif fmt == "percent":
            val_cell.value = _safe_float(raw_val) / 100.0 if _safe_float(raw_val) > 1 else _safe_float(raw_val)
            val_cell.number_format = FMT_PERCENT
        else:
            val_cell.value = str(raw_val)

        col += 1

    return start_row + 3


def write_table(
    ws: Any,
    start_row: int,
    headers: list[str],
    rows: list[list[Any]],
    col_types: list[str] | None = None,
    totals_cols: list[int] | None = None,
) -> int:
    """Write data rows with formatting, zebra-striping, and auto column widths."""
    num_cols = len(headers)
    col_types = col_types or ["text"] * num_cols

    # Header Row
    ws.row_dimensions[start_row].height = 28
    for c_idx, h in enumerate(headers, 1):
        cell = ws.cell(row=start_row, column=c_idx, value=h)
        cell.font = FONT_HEADER
        cell.fill = FILL_HEADER
        cell.alignment = ALIGN_HEADER
        cell.border = CELL_BORDER

    # Freeze Panes below headers
    ws.freeze_panes = ws.cell(row=start_row + 1, column=1)

    curr_row = start_row + 1
    for r_idx, row in enumerate(rows):
        ws.row_dimensions[curr_row].height = 20
        fill = FILL_ZEBRA if (r_idx % 2 == 1) else FILL_WHITE

        for c_idx, val in enumerate(row, 1):
            cell = ws.cell(row=curr_row, column=c_idx)
            cell.font = FONT_DATA
            cell.fill = fill
            cell.border = CELL_BORDER

            ctype = col_types[c_idx - 1] if c_idx - 1 < len(col_types) else "text"

            if ctype == "currency":
                cell.value = _safe_float(val)
                cell.number_format = FMT_CURRENCY
                cell.alignment = ALIGN_RIGHT
            elif ctype == "number":
                cell.value = _safe_float(val)
                cell.number_format = FMT_NUMBER
                cell.alignment = ALIGN_RIGHT
            elif ctype == "integer":
                cell.value = int(_safe_float(val))
                cell.number_format = FMT_INTEGER
                cell.alignment = ALIGN_RIGHT
            elif ctype == "percent":
                num = _safe_float(val)
                cell.value = num / 100.0 if num > 1.0 else num
                cell.number_format = FMT_PERCENT
                cell.alignment = ALIGN_RIGHT
            elif ctype == "date":
                if isinstance(val, (date, datetime)):
                    cell.value = val.strftime("%Y-%m-%d")
                else:
                    cell.value = str(val or "")
                cell.number_format = FMT_DATE
                cell.alignment = ALIGN_CENTER
            elif ctype == "status":
                st_str = str(val or "").strip().upper()
                cell.value = st_str
                cell.alignment = ALIGN_CENTER
                if any(x in st_str for x in ("PAID", "SETTLED", "ACTIVE", "B2B")):
                    cell.fill = PatternFill(start_color=STATUS_PAID_BG, end_color=STATUS_PAID_BG, fill_type="solid")
                    cell.font = Font(name=FONT_NAME, size=10, bold=True, color=STATUS_PAID_FG)
                elif any(x in st_str for x in ("PARTIAL",)):
                    cell.fill = PatternFill(start_color=STATUS_PARTIAL_BG, end_color=STATUS_PARTIAL_BG, fill_type="solid")
                    cell.font = Font(name=FONT_NAME, size=10, bold=True, color=STATUS_PARTIAL_FG)
                elif any(x in st_str for x in ("UNPAID", "OVERDUE", "PENDING", "DUE")):
                    cell.fill = PatternFill(start_color=STATUS_UNPAID_BG, end_color=STATUS_UNPAID_BG, fill_type="solid")
                    cell.font = Font(name=FONT_NAME, size=10, bold=True, color=STATUS_UNPAID_FG)
            else:
                cell.value = str(val) if val is not None else ""
                cell.alignment = ALIGN_LEFT

        curr_row += 1

    # Totals Row
    if totals_cols and rows:
        ws.row_dimensions[curr_row].height = 24
        for c_idx in range(1, num_cols + 1):
            cell = ws.cell(row=curr_row, column=c_idx)
            cell.fill = FILL_TOTAL
            cell.border = TOTAL_BORDER
            cell.font = FONT_TOTAL

            if c_idx == 1:
                cell.value = "TOTAL"
                cell.alignment = ALIGN_LEFT
            elif c_idx in totals_cols:
                col_letter = get_column_letter(c_idx)
                cell.value = f"=SUM({col_letter}{start_row + 1}:{col_letter}{curr_row - 1})"
                ctype = col_types[c_idx - 1]
                if ctype == "currency":
                    cell.number_format = FMT_CURRENCY
                else:
                    cell.number_format = FMT_NUMBER
                cell.alignment = ALIGN_RIGHT
            else:
                cell.value = ""

        curr_row += 1

    # Auto-fit Column Widths
    for col_idx in range(1, num_cols + 1):
        col_letter = get_column_letter(col_idx)
        max_len = 0
        for r in range(start_row, curr_row):
            val = ws.cell(row=r, column=col_idx).value
            if val is not None:
                # Approximate currency string length for formulas or floats
                s = f"₹ {val:,.2f}" if isinstance(val, (int, float)) else str(val)
                max_len = max(max_len, len(s))
        ws.column_dimensions[col_letter].width = max(max_len + 4, 13)

    return curr_row


# ===========================================================================
# Specific Section Exporters
# ===========================================================================

def export_invoices_to_excel(filepath: str, invoices: list[Any]) -> None:
    """Export invoices list with financial summary cards & comparison chart."""
    if filepath.lower().endswith(".csv"):
        _export_invoices_csv(filepath, invoices)
        return

    now_str = datetime.now().strftime("%d-%b-%Y %I:%M %p")
    wb, ws = create_base_workbook("INVOICE SALES & BILLING REGISTER", f"Generated on {now_str} • Furniture Billing Suite")

    # Metrics
    tot_billed = sum(float(inv.grand_total or 0) for inv in invoices)
    tot_paid = sum(sum(float(p.amount or 0) for p in (inv.payments or [])) for inv in invoices)
    tot_due = max(tot_billed - tot_paid, 0.0)

    cards = [
        {"label": "Total Invoices", "value": len(invoices), "format": "number"},
        {"label": "Total Billed", "value": tot_billed, "format": "currency"},
        {"label": "Total Collected", "value": tot_paid, "format": "currency"},
        {"label": "Outstanding Due", "value": tot_due, "format": "currency"},
    ]
    table_start = add_kpi_cards(ws, 4, cards)

    headers = [
        "Invoice No", "Customer Name", "Contact Mobile", "Invoice Date",
        "Due Date", "Status", "Grand Total", "Paid Amount", "Balance Due"
    ]
    col_types = ["text", "text", "text", "date", "date", "status", "currency", "currency", "currency"]

    from app.services.invoice_service import compute_status

    rows = []
    for inv in invoices:
        t = float(inv.grand_total or 0)
        p = sum(float(pm.amount or 0) for pm in (inv.payments or []))
        d = max(t - p, 0.0)
        st = compute_status(inv.grand_total, p, inv.status, inv.due_date)
        rows.append([
            inv.invoice_number,
            inv.customer.name if inv.customer else "Walk-in Customer",
            inv.customer.mobile if (inv.customer and inv.customer.mobile) else "-",
            inv.invoice_date,
            inv.due_date,
            st,
            t,
            p,
            d,
        ])

    end_row = write_table(ws, table_start, headers, rows, col_types, totals_cols=[7, 8, 9])

    # Add Invoices Summary Chart
    if len(rows) > 0:
        chart = BarChart()
        chart.type = "col"
        chart.style = 10
        chart.title = "Collection Overview: Billed vs Paid vs Due"
        chart.y_axis.title = "Amount (₹)"
        chart.x_axis.title = "Metrics"
        chart.width = 16
        chart.height = 10

        # Totals row is at end_row - 1
        tot_row = end_row - 1
        data = Reference(ws, min_col=7, min_row=table_start, max_col=9, max_row=tot_row)
        chart.add_data(data, titles_from_data=True)
        ws.add_chart(chart, f"K{table_start}")

    wb.save(filepath)


def export_gstr1_to_excel(filepath: str, rows_data: list[dict[str, Any]]) -> None:
    """Export GSTR-1 Tax Register with GST breakdown and B2B/B2C analysis."""
    if filepath.lower().endswith(".csv"):
        _export_gstr1_csv(filepath, rows_data)
        return

    now_str = datetime.now().strftime("%d-%b-%Y %I:%M %p")
    wb, ws = create_base_workbook("GSTR-1 TAX REGISTER & GST BREAKDOWN", f"Generated on {now_str} • Compliant with Indian GST Standards")

    tot_taxable = sum(float(r.get("taxable_value", 0)) for r in rows_data)
    tot_cgst = sum(float(r.get("cgst", 0)) for r in rows_data)
    tot_sgst = sum(float(r.get("sgst", 0)) for r in rows_data)
    tot_igst = sum(float(r.get("igst", 0)) for r in rows_data)
    tot_grand = sum(float(r.get("grand_total", 0)) for r in rows_data)

    cards = [
        {"label": "Taxable Value", "value": tot_taxable, "format": "currency"},
        {"label": "Total CGST", "value": tot_cgst, "format": "currency"},
        {"label": "Total SGST", "value": tot_sgst, "format": "currency"},
        {"label": "Total IGST", "value": tot_igst, "format": "currency"},
        {"label": "Total GST Value", "value": tot_cgst + tot_sgst + tot_igst, "format": "currency"},
    ]
    table_start = add_kpi_cards(ws, 4, cards)

    headers = [
        "Invoice No", "Date", "Customer Name", "Mobile", "GSTIN",
        "Place of Supply", "Type", "Taxable Value", "GST Rate", "CGST",
        "SGST", "IGST", "Grand Total", "Paid", "Balance", "Status"
    ]
    col_types = [
        "text", "date", "text", "text", "text",
        "text", "status", "currency", "percent", "currency",
        "currency", "currency", "currency", "currency", "currency", "status"
    ]

    rows = []
    for r in rows_data:
        rows.append([
            r.get("invoice_number", ""),
            r.get("date"),
            r.get("customer_name", ""),
            r.get("customer_mobile", "-"),
            r.get("customer_gstin", "-"),
            r.get("customer_state", "-"),
            "B2B" if r.get("is_b2b") else "B2C",
            r.get("taxable_value", 0.0),
            r.get("gst_rate", 0.0) / 100.0,
            r.get("cgst", 0.0),
            r.get("sgst", 0.0),
            r.get("igst", 0.0),
            r.get("grand_total", 0.0),
            r.get("paid_amount", 0.0),
            r.get("balance", 0.0),
            r.get("status", ""),
        ])

    write_table(ws, table_start, headers, rows, col_types, totals_cols=[8, 10, 11, 12, 13, 14, 15])
    wb.save(filepath)


def export_areas_to_excel(filepath: str, areas_data: list[dict[str, Any]]) -> None:
    """Export Furniture Sales by Area with embedded 3D/Donut Revenue Share Pie Chart."""
    if filepath.lower().endswith(".csv"):
        _export_areas_csv(filepath, areas_data)
        return

    now_str = datetime.now().strftime("%d-%b-%Y %I:%M %p")
    wb, ws = create_base_workbook("FURNITURE SALES BY ROOM AREA & CATEGORY", f"Revenue Contribution Analysis • Generated on {now_str}")

    tot_revenue = sum(float(a.get("revenue", 0)) for a in areas_data)
    tot_items = sum(int(a.get("item_count", 0)) for a in areas_data)

    cards = [
        {"label": "Room Areas Analyzed", "value": len(areas_data), "format": "number"},
        {"label": "Total Furniture Items", "value": tot_items, "format": "number"},
        {"label": "Total Furniture Sales", "value": tot_revenue, "format": "currency"},
    ]
    table_start = add_kpi_cards(ws, 4, cards)

    headers = ["Room Area / Category", "Items Count", "Revenue (INR)", "Revenue Share (%)"]
    col_types = ["text", "integer", "currency", "percent"]

    rows = []
    for a in areas_data:
        rows.append([
            a.get("area", "OTHER"),
            a.get("item_count", 0),
            a.get("revenue", 0.0),
            float(a.get("percent", 0.0)) / 100.0,
        ])

    end_row = write_table(ws, table_start, headers, rows, col_types, totals_cols=[2, 3])

    # Pie Chart for Area Distribution
    if len(rows) > 0:
        pie = PieChart()
        pie.title = "Revenue Distribution by Room Area"
        labels = Reference(ws, min_col=1, min_row=table_start + 1, max_row=table_start + len(rows))
        data = Reference(ws, min_col=3, min_row=table_start, max_row=table_start + len(rows))
        pie.add_data(data, titles_from_data=True)
        pie.set_categories(labels)
        pie.style = 10
        pie.width = 16
        pie.height = 10
        ws.add_chart(pie, f"F{table_start}")

    wb.save(filepath)


def export_receivables_to_excel(filepath: str, customers_data: list[dict[str, Any]]) -> None:
    """Export Customer Receivables & Balances with Outstanding Bar Chart."""
    if filepath.lower().endswith(".csv"):
        _export_receivables_csv(filepath, customers_data)
        return

    now_str = datetime.now().strftime("%d-%b-%Y %I:%M %p")
    wb, ws = create_base_workbook("CLIENT RECEIVABLES & OUTSTANDING DUES", f"Credit Control Ledger • Generated on {now_str}")

    tot_billed = sum(float(c.get("total_billed", 0)) for c in customers_data)
    tot_paid = sum(float(c.get("total_paid", 0)) for c in customers_data)
    tot_due = sum(float(c.get("balance_due", 0)) for c in customers_data)

    cards = [
        {"label": "Customers with Dues", "value": len(customers_data), "format": "number"},
        {"label": "Total Cumulative Invoiced", "value": tot_billed, "format": "currency"},
        {"label": "Total Collections Received", "value": tot_paid, "format": "currency"},
        {"label": "Total Pending Balances", "value": tot_due, "format": "currency"},
    ]
    table_start = add_kpi_cards(ws, 4, cards)

    headers = [
        "Customer Name", "Contact Mobile", "GSTIN", "City",
        "Invoices Count", "Total Billed", "Total Paid", "Balance Due", "Settlement Ratio"
    ]
    col_types = ["text", "text", "text", "text", "integer", "currency", "currency", "currency", "percent"]

    rows = []
    for c in customers_data:
        rows.append([
            c.get("name", ""),
            c.get("mobile", "-"),
            c.get("gstin", "-"),
            c.get("city", "-"),
            c.get("invoices_count", 0),
            c.get("total_billed", 0.0),
            c.get("total_paid", 0.0),
            c.get("balance_due", 0.0),
            float(c.get("compliance_pct", 0.0)) / 100.0,
        ])

    end_row = write_table(ws, table_start, headers, rows, col_types, totals_cols=[5, 6, 7, 8])

    # Top Receivables Bar Chart
    if len(rows) > 0:
        chart = BarChart()
        chart.type = "bar"
        chart.style = 11
        chart.title = "Top Outstanding Balances by Customer"
        chart.x_axis.title = "Pending Due (₹)"
        chart.y_axis.title = "Customer"
        chart.width = 16
        chart.height = 11

        max_chart_rows = min(len(rows), 10)
        data = Reference(ws, min_col=8, min_row=table_start, max_row=table_start + max_chart_rows)
        cats = Reference(ws, min_col=1, min_row=table_start + 1, max_row=table_start + max_chart_rows)
        chart.add_data(data, titles_from_data=True)
        chart.set_categories(cats)
        chart.legend = None
        ws.add_chart(chart, f"K{table_start}")

    wb.save(filepath)


def export_payments_to_excel(filepath: str, payments_data: list[dict[str, Any]]) -> None:
    """Export Payment History Ledger with Payment Mode / Timeline analytics."""
    if filepath.lower().endswith(".csv"):
        _export_payments_csv(filepath, payments_data)
        return

    now_str = datetime.now().strftime("%d-%b-%Y %I:%M %p")
    wb, ws = create_base_workbook("PAYMENT RECEIPTS & COLLECTION LEDGER", f"Realized Cash & Digital Collections • Generated on {now_str}")

    tot_amount = sum(float(p.get("amount", 0)) for p in payments_data)

    cards = [
        {"label": "Total Transactions", "value": len(payments_data), "format": "number"},
        {"label": "Total Amount Collected", "value": tot_amount, "format": "currency"},
    ]
    table_start = add_kpi_cards(ws, 4, cards)

    headers = [
        "Payment Date", "Invoice No", "Customer Name", "Contact Mobile",
        "Payment Mode", "Reference / UTR", "Amount Received", "Notes / Remarks"
    ]
    col_types = ["date", "text", "text", "text", "status", "text", "currency", "text"]

    rows = []
    for p in payments_data:
        rows.append([
            p.get("date"),
            p.get("invoice_number", ""),
            p.get("customer_name", ""),
            p.get("customer_mobile", "-"),
            p.get("mode", "Cash"),
            p.get("reference", "-"),
            p.get("amount", 0.0),
            p.get("notes", ""),
        ])

    write_table(ws, table_start, headers, rows, col_types, totals_cols=[7])
    wb.save(filepath)


def export_customer_directory_to_excel(filepath: str, customers: list[dict[str, Any]]) -> None:
    """Export Customer Directory & Lifetime Ledger."""
    if filepath.lower().endswith(".csv"):
        _export_customer_directory_csv(filepath, customers)
        return

    now_str = datetime.now().strftime("%d-%b-%Y %I:%M %p")
    wb, ws = create_base_workbook("CUSTOMER DIRECTORY & MASTER LEDGER", f"Active Client Portfolio • Generated on {now_str}")

    tot_invoiced = sum(float(c.get("total_invoiced", 0)) for c in customers)
    tot_collected = sum(float(c.get("total_paid", 0)) for c in customers)
    tot_balance = sum(float(c.get("outstanding", 0)) for c in customers)

    cards = [
        {"label": "Total Accounts", "value": len(customers), "format": "number"},
        {"label": "Lifetime Invoiced", "value": tot_invoiced, "format": "currency"},
        {"label": "Lifetime Collected", "value": tot_collected, "format": "currency"},
        {"label": "Total Current Balance", "value": tot_balance, "format": "currency"},
    ]
    table_start = add_kpi_cards(ws, 4, cards)

    headers = [
        "ID", "Customer Name", "Mobile", "Email", "City", "State",
        "GSTIN", "Invoices", "Total Billed", "Total Paid", "Balance Due", "Status"
    ]
    col_types = ["integer", "text", "text", "text", "text", "text", "text", "integer", "currency", "currency", "currency", "status"]

    rows = []
    for c in customers:
        rows.append([
            c.get("id"),
            c.get("name", ""),
            c.get("mobile", "-"),
            c.get("email", "-"),
            c.get("city", "-"),
            c.get("state", "-"),
            c.get("gstin", "-"),
            c.get("invoice_count", 0),
            c.get("total_invoiced", 0.0),
            c.get("total_paid", 0.0),
            c.get("outstanding", 0.0),
            "Settled" if c.get("is_settled") else "Pending Due",
        ])

    write_table(ws, table_start, headers, rows, col_types, totals_cols=[8, 9, 10, 11])
    wb.save(filepath)


def export_items_to_excel(filepath: str, items: list[dict[str, Any]]) -> None:
    """Export individual invoice items with Area grouping and totals."""
    if filepath.lower().endswith(".csv"):
        _export_items_csv(filepath, items)
        return

    now_str = datetime.now().strftime("%d-%b-%Y %I:%M %p")
    wb, ws = create_base_workbook("INVOICE LINE ITEMS SPECIFICATION", f"Itemized Work Order • Generated on {now_str}")

    tot_amount = sum(float(it.get("amount") or 0) for it in items)

    cards = [
        {"label": "Total Line Items", "value": len(items), "format": "number"},
        {"label": "Total Work Order Amount", "value": tot_amount, "format": "currency"},
    ]
    table_start = add_kpi_cards(ws, 4, cards)

    headers = ["S.N.", "Room / Area", "Description", "Dimensions / Size", "Quantity", "Rate", "Total Amount"]
    col_types = ["integer", "text", "text", "text", "number", "currency", "currency"]

    rows = []
    for i, it in enumerate(items, 1):
        rows.append([
            i,
            it.get("area", "OTHER"),
            it.get("description", ""),
            it.get("size", "-"),
            _safe_float(it.get("qty_raw")),
            _safe_float(it.get("rate_raw")),
            _safe_float(it.get("amount")),
        ])

    write_table(ws, table_start, headers, rows, col_types, totals_cols=[5, 7])
    wb.save(filepath)


# ===========================================================================
# CSV Fallbacks (UTF-8 BOM for clean Hindi/Unicode Excel import)
# ===========================================================================

def _export_invoices_csv(filepath: str, invoices: list[Any]) -> None:
    from app.services.invoice_service import compute_status
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Invoice No", "Customer Name", "Mobile", "Date", "Due Date", "Status", "Grand Total", "Paid Amount", "Outstanding Due"])
        for inv in invoices:
            t = float(inv.grand_total or 0)
            p = sum(float(pm.amount or 0) for pm in (inv.payments or []))
            d = max(t - p, 0.0)
            st = compute_status(inv.grand_total, p, inv.status, inv.due_date)
            w.writerow([
                inv.invoice_number,
                inv.customer.name if inv.customer else "",
                inv.customer.mobile if (inv.customer and inv.customer.mobile) else "",
                inv.invoice_date.strftime("%Y-%m-%d") if inv.invoice_date else "",
                inv.due_date.strftime("%Y-%m-%d") if inv.due_date else "",
                st, f"{t:.2f}", f"{p:.2f}", f"{d:.2f}"
            ])


def _export_gstr1_csv(filepath: str, rows: list[dict[str, Any]]) -> None:
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Invoice Number", "Invoice Date", "Customer Name", "Mobile", "Customer GSTIN", "Place of Supply", "Invoice Type", "Taxable Value", "GST Rate", "CGST", "SGST", "IGST", "Grand Total", "Paid Amount", "Balance Due", "Status"])
        for r in rows:
            w.writerow([
                r.get("invoice_number"),
                r["date"].strftime("%d-%b-%Y") if r.get("date") else "",
                r.get("customer_name"), r.get("customer_mobile"), r.get("customer_gstin"),
                r.get("customer_state"), "B2B" if r.get("is_b2b") else "B2C",
                f"{r.get('taxable_value', 0):.2f}", f"{r.get('gst_rate', 0):.0f}%",
                f"{r.get('cgst', 0):.2f}", f"{r.get('sgst', 0):.2f}", f"{r.get('igst', 0):.2f}",
                f"{r.get('grand_total', 0):.2f}", f"{r.get('paid_amount', 0):.2f}",
                f"{r.get('balance', 0):.2f}", r.get("status")
            ])


def _export_areas_csv(filepath: str, areas: list[dict[str, Any]]) -> None:
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Furniture Category / Room Area", "Items Volume", "Revenue (INR)", "Revenue Share (%)"])
        for a in areas:
            w.writerow([a.get("area"), a.get("item_count"), f"{a.get('revenue', 0):.2f}", f"{a.get('percent', 0):.1f}%"])


def _export_receivables_csv(filepath: str, customers: list[dict[str, Any]]) -> None:
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Customer Name", "Contact Mobile", "GSTIN", "City", "Invoices Count", "Total Billed", "Total Paid", "Balance Due", "Settlement %"])
        for c in customers:
            w.writerow([
                c.get("name"), c.get("mobile"), c.get("gstin"), c.get("city"),
                c.get("invoices_count"), f"{c.get('total_billed', 0):.2f}",
                f"{c.get('total_paid', 0):.2f}", f"{c.get('balance_due', 0):.2f}",
                f"{c.get('compliance_pct', 0):.1f}%"
            ])


def _export_payments_csv(filepath: str, payments: list[dict[str, Any]]) -> None:
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Payment Date", "Invoice Number", "Customer Name", "Contact Mobile", "Payment Mode", "Reference / UTR", "Amount (INR)", "Notes"])
        for p in payments:
            w.writerow([
                p["date"].strftime("%d-%b-%Y") if p.get("date") else "",
                p.get("invoice_number"), p.get("customer_name"), p.get("customer_mobile", "-"),
                p.get("mode"), p.get("reference"), f"{p.get('amount', 0):.2f}", p.get("notes", "")
            ])


def _export_customer_directory_csv(filepath: str, customers: list[dict[str, Any]]) -> None:
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["Customer ID", "Customer Name", "Mobile", "Email", "City", "State", "GSTIN", "Invoices Count", "Total Billed", "Total Collected", "Outstanding Balance", "Settlement Status"])
        for c in customers:
            w.writerow([
                c.get("id"), c.get("name"), c.get("mobile"), c.get("email"),
                c.get("city"), c.get("state"), c.get("gstin"), c.get("invoice_count"),
                f"{c.get('total_invoiced', 0):.2f}", f"{c.get('total_paid', 0):.2f}",
                f"{c.get('outstanding', 0):.2f}", "Settled" if c.get("is_settled") else "Pending Due"
            ])


def _export_items_csv(filepath: str, items: list[dict[str, Any]]) -> None:
    with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["S.N.", "Area", "Description", "Size", "Qty", "Rate", "Amount"])
        for i, it in enumerate(items, 1):
            w.writerow([i, it.get("area", ""), it.get("description", ""), it.get("size", ""), it.get("qty_raw", ""), it.get("rate_raw", ""), it.get("amount", "")])
