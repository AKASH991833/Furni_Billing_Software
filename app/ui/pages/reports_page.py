"""Reports page: income summaries, payment history, and totals.

Built with indexed aggregation queries. Date filters: Today / This Week /
This Month / This Year / Custom Range.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QFileDialog,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.services import report_service
from app.ui.pages.base_page import BasePage
from app.ui.style import PRIMARY, SUCCESS, WARNING
from app.ui.widgets.common import card, show_toast, stat_card


def _money(v) -> str:
    return f"\u20B9 {float(v or 0):,.2f}"


class ReportsPage(BasePage):
    # Stat card keys — created once, updated in-place on every refresh
    _STAT_KEYS = (
        ("period_income", "Period Income", SUCCESS),
        ("total_income", "Total Income", SUCCESS),
        ("total_outstanding", "Total Outstanding", WARNING),
        ("invoice_count", "Invoices", PRIMARY),
        ("customer_count", "Customers", PRIMARY),
        ("payment_count", "Payments (period)", "#3B82F6"),
    )

    def __init__(self, main_window=None, parent=None):
        super().__init__(main_window, parent)
        self._stat_cards = {}  # key -> ClickableStatCard for in-place updates
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(16)

        # Filters
        filter_bar = QHBoxLayout()
        filter_bar.addWidget(QLabel("Period:"))
        self.period = QComboBox()
        self.period.addItems(["Today", "This Week", "This Month", "This Year", "Custom Range"])
        self.period.currentTextChanged.connect(self._on_period)
        self.start_date = QDateEdit(QDate(datetime.now(tz=timezone.utc).date()))
        self.start_date.setCalendarPopup(True)
        self.end_date = QDateEdit(QDate(datetime.now(tz=timezone.utc).date()))
        self.end_date.setCalendarPopup(True)
        self.start_date.setEnabled(False)
        self.end_date.setEnabled(False)
        btn = QPushButton("Apply")
        btn.clicked.connect(self.refresh)
        btn_export = QPushButton("Export CSV")
        btn_export.setObjectName("primaryButton")
        btn_export.clicked.connect(self._export_csv)
        filter_bar.addWidget(self.period)
        filter_bar.addWidget(QLabel("From:"))
        filter_bar.addWidget(self.start_date)
        filter_bar.addWidget(QLabel("To:"))
        filter_bar.addWidget(self.end_date)
        filter_bar.addWidget(btn)
        filter_bar.addWidget(btn_export)
        filter_bar.addStretch(1)
        outer.addLayout(filter_bar)

        self.stats_grid = QGridLayout()
        self.stats_grid.setSpacing(14)
        self._build_stat_cards()
        outer.addLayout(self.stats_grid)

        bottom = QHBoxLayout()
        bottom.setSpacing(16)
        outer.addLayout(bottom, 1)

        pay_card = card("Payment History")
        self.pay_table = QTableWidget(0, 5)
        self.pay_table.setHorizontalHeaderLabels(["Date", "Invoice", "Mode", "Reference", "Amount"])
        self.pay_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.pay_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.pay_table.verticalHeader().setVisible(False)
        self.pay_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.pay_table.setAlternatingRowColors(True)
        pay_card.layout().addWidget(self.pay_table)
        bottom.addWidget(pay_card, 1)

    def _build_stat_cards(self):
        """Create stat cards once. They are updated in-place on refresh."""
        for i, (key, title, accent) in enumerate(self._STAT_KEYS):
            card_widget = stat_card(title, "—", accent)
            self.stats_grid.addWidget(card_widget, i // 3, i % 3)
            # Store reference to the value label for in-place updates
            self._stat_cards[key] = card_widget

    def _on_period(self, text):
        custom = text == "Custom Range"
        self.start_date.setEnabled(custom)
        self.end_date.setEnabled(custom)
        if not custom:
            self.refresh()

    def _period_key(self):
        m = {"Today": "today", "This Week": "week", "This Month": "month",
             "This Year": "year", "Custom Range": "custom"}
        return m.get(self.period.currentText(), "today")

    def on_first_show(self):
        self.refresh()

    def refresh(self):
        period = self._period_key()
        start = self.start_date.date().toPython() if period == "custom" else None
        end = self.end_date.date().toPython() if period == "custom" else None

        income = report_service.income_summary(period, start, end)
        overview = report_service.totals_overview()

        # Update stat card values in-place (no widget recreation)
        values = {
            "period_income": _money(income["income"]),
            "total_income": _money(overview["total_income"]),
            "total_outstanding": _money(overview["total_outstanding"]),
            "invoice_count": str(overview["invoice_count"]),
            "customer_count": str(overview["customer_count"]),
            "payment_count": str(income["payment_count"]),
        }
        for key, card_widget in self._stat_cards.items():
            # stat_card returns a QFrame; the value label is its first child widget
            # in the layout (statValue QLabel)
            lay = card_widget.layout()
            if lay and lay.count() > 0:
                value_label = lay.itemAt(0).widget()
                if value_label:
                    value_label.setText(values.get(key, "—"))

        self._load_payments()

    def _load_payments(self):
        pays = report_service.payment_history(200)
        self.pay_table.setRowCount(0)
        for p in pays:
            r = self.pay_table.rowCount()
            self.pay_table.insertRow(r)
            inv_no = p.invoice.invoice_number if p.invoice else "-"
            vals = [p.date.strftime("%d-%b-%Y") if p.date else "-", inv_no,
                    p.mode, p.reference or "-", f"\u20B9 {float(p.amount or 0):,.2f}"]
            for c, vv in enumerate(vals):
                self.pay_table.setItem(r, c, QTableWidgetItem(str(vv)))

    def _export_csv(self):
        """Export the current payment history table to a CSV file."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Payment History",
            str(__import__("os").path.expanduser("~/payment_history.csv")),
            "CSV Files (*.csv)",
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"
        try:
            headers = ["Date", "Invoice", "Mode", "Reference", "Amount"]
            rows = []
            for r in range(self.pay_table.rowCount()):
                row_data = []
                for c in range(self.pay_table.columnCount()):
                    item = self.pay_table.item(r, c)
                    row_data.append(item.text() if item else "")
                rows.append(row_data)
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(rows)
            show_toast(self, f"Exported {len(rows)} payments to {path}", "success")
        except Exception as e:  # noqa: BLE001
            show_toast(self, f"Export failed: {e}", "error")
