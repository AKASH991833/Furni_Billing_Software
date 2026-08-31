"""Live dashboard page."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QHeaderView,
)

from app.services import dashboard_service
from app.ui.pages.base_page import BasePage
from app.ui.widgets.common import card, stat_card
from app.ui.style import PRIMARY, SUCCESS, WARNING, DANGER, TEXT_MUTED


def _money(v) -> str:
    return f"\u20B9 {float(v or 0):,.2f}"


class DashboardPage(BasePage):
    def __init__(self, main_window=None, parent=None):
        super().__init__(main_window, parent)
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(16)

        self._stats_grid = QGridLayout()
        self._stats_grid.setSpacing(14)
        outer.addLayout(self._stats_grid)

        bottom = QHBoxLayout()
        bottom.setSpacing(16)
        outer.addLayout(bottom, 1)

        rec_inv_card = card("Recent Invoices")
        self.recent_invoices_table = self._make_table(
            ["Invoice No", "Customer", "Date", "Status", "Amount"], 5)
        rec_inv_card.layout().addWidget(self.recent_invoices_table)
        bottom.addWidget(rec_inv_card, 3)

        rec_pay_card = card("Recent Payments")
        self.recent_payments_table = self._make_table(
            ["Date", "Invoice", "Mode", "Amount"], 4)
        rec_pay_card.layout().addWidget(self.recent_payments_table)
        bottom.addWidget(rec_pay_card, 2)

        # Monthly income chart
        chart_card = card("Monthly Income (last 6 months)")
        try:
            from PySide6.QtCharts import (  # noqa: F401
                QBarCategoryAxis, QBarSeries, QBarSet, QChart, QChartView,
                QValueAxis,
            )
            from PySide6.QtCore import Qt as _Qt
            from PySide6.QtGui import QColor

            self.chart = QChart()
            self.series = QBarSeries()
            self.chart_series = QBarSet("Income")
            self.chart_series.setColor(QColor("#2563EB"))
            self.series.append(self.chart_series)
            self.chart.addSeries(self.series)
            self.chart.legend().setVisible(True)
            self.chart.legend().setAlignment(_Qt.AlignBottom)
            self.axis_x = QBarCategoryAxis()
            self.axis_y = QValueAxis()
            self.chart.addAxis(self.axis_x, _Qt.AlignBottom)
            self.chart.addAxis(self.axis_y, _Qt.AlignLeft)
            self.series.attachAxis(self.axis_x)
            self.series.attachAxis(self.axis_y)
            self.axis_y.setLabelFormat("%.0f")
            self.chart_view = QChartView(self.chart)
            self.chart_view.setMinimumHeight(220)
            chart_card.layout().addWidget(self.chart_view)
            self._chart_enabled = True
        except Exception:  # noqa: BLE001
            self._chart_enabled = False
            chart_card.layout().addWidget(QLabel("Chart library unavailable."))
        outer.addWidget(chart_card)

        self._refresh_titles = {}
        self._stat_cards = {}

    def _make_table(self, headers, hidden_rows=5):
        t = QTableWidget(0, len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.setEditTriggers(QTableWidget.NoEditTriggers)
        t.setSelectionBehavior(QTableWidget.SelectRows)
        t.verticalHeader().setVisible(False)
        t.horizontalHeader().setStretchLastSection(True)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        t.setAlternatingRowColors(True)
        t.setMinimumHeight(220)
        return t

    def on_first_show(self):
        self.refresh()

    def refresh(self):
        stats = dashboard_service.dashboard_stats()
        self._render_stats(stats)

        self._render_recent_invoices()
        self._render_recent_payments()
        self._render_chart()

    def _render_chart(self):
        if not getattr(self, "_chart_enabled", False):
            return
        try:
            months = dashboard_service.monthly_income_for_year(6)
            last6 = months[-6:] if len(months) > 6 else months
            values = [m["total"] for m in last6]
            labels = [m["month"][2:] + "/" + m["month"][:2] if len(m["month"]) >= 5
                      else m["month"] for m in last6]
            # Only remove existing data if there is any
            count = self.chart_series.count()
            if count > 0:
                self.chart_series.remove(0, count - 1)
            for v in values:
                self.chart_series.append(float(v))
            self.axis_x.clear()
            self.axis_x.append([lbl for lbl in labels] or ["-"])
            top = max(max(values, default=0) * 1.1, 10)
            self.axis_y.setRange(0, top)
        except Exception:  # noqa: BLE001
            pass

    def _render_stats(self, stats):
        # clear existing grid
        while self._stats_grid.count():
            item = self._stats_grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        cards = [
            ("Total Customers", str(stats["total_customers"]), PRIMARY),
            ("Total Invoices", str(stats["total_invoices"]), PRIMARY),
            ("Today's Income", _money(stats["today_income"]), SUCCESS),
            ("Monthly Income", _money(stats["monthly_income"]), SUCCESS),
            ("Total Income", _money(stats["total_income"]), SUCCESS),
            ("Total Outstanding", _money(stats["total_outstanding"]), WARNING),
            ("Paid Invoices", str(stats["paid_invoices"]), "#3B82F6"),
            ("Pending Invoices", str(stats["pending_invoices"]), DANGER),
        ]
        for i, (title, val, accent) in enumerate(cards):
            row, col = divmod(i, 4)
            self._stats_grid.addWidget(stat_card(title, val, accent), row, col)

    def _render_recent_invoices(self):
        t = self.recent_invoices_table
        invoices = dashboard_service.recent_invoices(6)
        t.setRowCount(0)
        for inv in invoices:
            r = t.rowCount()
            t.insertRow(r)
            from app.services.invoice_service import invoice_status
            customer = inv.customer.name if inv.customer else "-"
            status = invoice_status(inv)
            vals = [inv.invoice_number, customer,
                    inv.invoice_date.strftime("%d-%b-%Y") if inv.invoice_date else "-",
                    status, _money(inv.grand_total)]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(str(v))
                if c == 3:
                    item.setForeground(Qt.GlobalColor.darkBlue if status == "PAID"
                                       else Qt.GlobalColor.darkYellow if "PART" in status
                                       else Qt.GlobalColor.darkRed if status in ("OVERDUE", "UNPAID")
                                       else Qt.GlobalColor.darkGray)
                t.setItem(r, c, item)

    def _render_recent_payments(self):
        t = self.recent_payments_table
        payments = dashboard_service.recent_payments(6)
        t.setRowCount(0)
        for p in payments:
            r = t.rowCount()
            t.insertRow(r)
            inv_no = p.invoice.invoice_number if p.invoice else "-"
            vals = [p.date.strftime("%d-%b-%Y") if p.date else "-",
                    inv_no, p.mode, _money(p.amount)]
            for c, v in enumerate(vals):
                t.setItem(r, c, QTableWidgetItem(str(v)))
