"""Reports page: income summaries, payment history, and totals.

Built with indexed aggregation queries. Date filters: Today / This Week /
This Month / This Year / Custom Range.
"""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services import report_service
from app.ui.pages.base_page import BasePage
from app.ui.widgets.common import card, stat_card
from app.ui.style import PRIMARY, SUCCESS, WARNING


def _money(v) -> str:
    return f"\u20B9 {float(v or 0):,.2f}"


class ReportsPage(BasePage):
    def __init__(self, main_window=None, parent=None):
        super().__init__(main_window, parent)
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
        self.start_date = QDateEdit(QDate(date.today()))
        self.start_date.setCalendarPopup(True)
        self.end_date = QDateEdit(QDate(date.today()))
        self.end_date.setCalendarPopup(True)
        self.start_date.setEnabled(False)
        self.end_date.setEnabled(False)
        btn = QPushButton("Apply")
        btn.clicked.connect(self.refresh)
        filter_bar.addWidget(self.period)
        filter_bar.addWidget(QLabel("From:"))
        filter_bar.addWidget(self.start_date)
        filter_bar.addWidget(QLabel("To:"))
        filter_bar.addWidget(self.end_date)
        filter_bar.addWidget(btn)
        filter_bar.addStretch(1)
        outer.addLayout(filter_bar)

        self.stats_grid = QGridLayout()
        self.stats_grid.setSpacing(14)
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

        while self.stats_grid.count():
            it = self.stats_grid.takeAt(0)
            w = it.widget()
            if w:
                w.deleteLater()

        cards = [
            ("Period Income", _money(income["income"]), SUCCESS),
            ("Total Income", _money(overview["total_income"]), SUCCESS),
            ("Total Outstanding", _money(overview["total_outstanding"]), WARNING),
            ("Invoices", str(overview["invoice_count"]), PRIMARY),
            ("Customers", str(overview["customer_count"]), PRIMARY),
            ("Payments (period)", str(income["payment_count"]), "#3B82F6"),
        ]
        for i, (t, v, a) in enumerate(cards):
            self.stats_grid.addWidget(stat_card(t, v, a), i // 3, i % 3)

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
