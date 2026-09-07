"""Live dashboard page — clickable, fast, and informative.

Stat cards navigate to relevant pages on click.
Table rows open invoices/payments on double-click.
Quick action buttons for common tasks.
Auto-refresh keeps data current.
Overdue alerts shown prominently.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QHeaderView,
)

from app.services import dashboard_service
from app.services.invoice_service import invoice_status, invoice_outstanding
from app.ui.pages.base_page import BasePage
from app.ui.style import PRIMARY, SUCCESS, WARNING, DANGER, TEXT_MUTED


def _money(v) -> str:
    return f"\u20B9 {float(v or 0):,.2f}"


class ClickableStatCard(QFrame):
    """Stat card that navigates to a page on click."""

    def __init__(self, title: str, value: str, accent: str = PRIMARY,
                 navigate_to: str = None, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self._navigate_to = navigate_to
        self.setCursor(Qt.PointingHandCursor if navigate_to else Qt.ArrowCursor)
        self.setStyleSheet(
            f"QFrame#card {{ border-left: 4px solid {accent}; background: white;"
            " border: 1px solid #E5E7EB; border-radius: 12px;"
            f" border-left: 4px solid {accent}; }}"
            "QFrame#card:hover { border-color: #2563EB; background: #F8FAFC; }"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 14, 16, 14)
        lay.setSpacing(4)
        v = QLabel(value)
        v.setObjectName("statValue")
        v.setStyleSheet(f"color: {accent};")
        t = QLabel(title)
        t.setObjectName("statLabel")
        lay.addWidget(v)
        lay.addWidget(t)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton and self._navigate_to:
            # Find the main_window by walking up the widget tree
            w = self.parent()
            while w:
                if hasattr(w, 'main_window') and w.main_window:
                    w.main_window.show_page(self._navigate_to)
                    return
                w = w.parent()
        super().mousePressEvent(ev)


class DashboardPage(BasePage):
    def __init__(self, main_window=None, parent=None):
        super().__init__(main_window, parent)
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(12)

        # --- Overdue alert banner ---
        self.alert_frame = QFrame()
        self.alert_frame.setObjectName("card")
        self.alert_frame.setStyleSheet(
            "QFrame#card { background: #FEF2F2; border: 1px solid #FECACA; border-radius: 10px; }"
        )
        alert_lay = QHBoxLayout(self.alert_frame)
        alert_lay.setContentsMargins(16, 10, 16, 10)
        self.alert_label = QLabel()
        self.alert_label.setStyleSheet("color: #991B1B; font-weight: 600; font-size: 13px;")
        self.alert_label.setWordWrap(True)
        alert_lay.addWidget(self.alert_label)
        self.alert_frame.setVisible(False)
        outer.addWidget(self.alert_frame)

        # --- Quick action buttons ---
        actions_row = QHBoxLayout()
        actions_row.setSpacing(8)
        btn_new_inv = self._action_btn("+ New Invoice", PRIMARY)
        btn_new_inv.clicked.connect(lambda: self._navigate_to("invoices", new_invoice=True))
        btn_view_inv = self._action_btn("View Invoices", "#6B7280")
        btn_view_inv.clicked.connect(lambda: self._navigate_to("invoices"))
        btn_add_cust = self._action_btn("+ Add Customer", "#6B7280")
        btn_add_cust.clicked.connect(lambda: self._navigate_to("customers"))
        btn_view_reports = self._action_btn("Reports", "#6B7280")
        btn_view_reports.clicked.connect(lambda: self._navigate_to("reports"))
        actions_row.addWidget(btn_new_inv)
        actions_row.addWidget(btn_view_inv)
        actions_row.addWidget(btn_add_cust)
        actions_row.addWidget(btn_view_reports)
        actions_row.addStretch(1)
        outer.addLayout(actions_row)

        # --- Stats grid ---
        self._stats_grid = QGridLayout()
        self._stats_grid.setSpacing(10)
        outer.addLayout(self._stats_grid)

        # --- Bottom row: Recent Invoices + Recent Payments ---
        bottom = QHBoxLayout()
        bottom.setSpacing(12)
        outer.addLayout(bottom, 1)

        rec_inv_card = self._section_card("Recent Invoices")
        self.recent_invoices_table = self._make_table(
            ["Invoice No", "Customer", "Date", "Status", "Amount"], 5)
        self.recent_invoices_table.cellDoubleClicked.connect(self._on_invoice_double_click)
        rec_inv_card.layout().addWidget(self.recent_invoices_table)
        bottom.addWidget(rec_inv_card, 3)

        rec_pay_card = self._section_card("Recent Payments")
        self.recent_payments_table = self._make_table(
            ["Date", "Invoice", "Mode", "Amount"], 4)
        rec_pay_card.layout().addWidget(self.recent_payments_table)
        bottom.addWidget(rec_pay_card, 2)

        # --- Monthly income chart ---
        chart_card = self._section_card("Monthly Income (last 6 months)")
        try:
            from PySide6.QtCharts import (  # noqa: F401
                QBarCategoryAxis, QBarSeries, QBarSet, QChart, QChartView,
                QValueAxis,
            )
            from PySide6.QtGui import QColor as _QC

            self.chart = QChart()
            self.chart.setBackgroundRoundness(10)
            self.chart.setMargins(__import__("PySide6.QtCore", fromlist=["QMargins"]).QMargins(0, 0, 0, 0))
            self.series = QBarSeries()
            self.chart_series = QBarSet("Income")
            self.chart_series.setColor(_QC("#2563EB"))
            self.series.append(self.chart_series)
            self.chart.addSeries(self.series)
            self.chart.legend().setVisible(True)
            self.chart.legend().setAlignment(Qt.AlignBottom)
            self.axis_x = QBarCategoryAxis()
            self.axis_y = QValueAxis()
            self.chart.addAxis(self.axis_x, Qt.AlignBottom)
            self.chart.addAxis(self.axis_y, Qt.AlignLeft)
            self.series.attachAxis(self.axis_x)
            self.series.attachAxis(self.axis_y)
            self.axis_y.setLabelFormat("%.0f")
            self.chart_view = QChartView(self.chart)
            self.chart_view.setMinimumHeight(200)
            self.chart_view.setStyleSheet("border-radius: 8px;")
            chart_card.layout().addWidget(self.chart_view)
            self._chart_enabled = True
        except Exception:  # noqa: BLE001
            self._chart_enabled = False
            chart_card.layout().addWidget(QLabel("Chart library unavailable."))
        outer.addWidget(chart_card)

        # --- Auto-refresh timer (every 30 seconds) ---
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(30_000)
        self._refresh_timer.timeout.connect(self._soft_refresh)
        self._refresh_timer.start()

    def _action_btn(self, text, color=PRIMARY):
        """Create a quick action button."""
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        btn.setStyleSheet(
            f"QPushButton {{ background: {color}; color: white; border: none;"
            " border-radius: 8px; padding: 8px 16px; font-weight: 600; font-size: 12px; }"
            f"QPushButton:hover {{ background: {color}DD; }}"
        )
        return btn

    def _section_card(self, title):
        """Create a styled card section with a title."""
        c = QFrame()
        c.setObjectName("card")
        c.setStyleSheet(
            "QFrame#card { background: white; border: 1px solid #E5E7EB; border-radius: 12px; }"
        )
        v = QVBoxLayout(c)
        v.setContentsMargins(14, 12, 14, 12)
        v.setSpacing(8)
        t = QLabel(title)
        t.setObjectName("cardTitle")
        t.setStyleSheet("font-size: 14px; font-weight: 700; color: #1F2937;")
        v.addWidget(t)
        return c

    def _make_table(self, headers, hidden_rows=5):
        t = QTableWidget(0, len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.setEditTriggers(QTableWidget.NoEditTriggers)
        t.setSelectionBehavior(QTableWidget.SelectRows)
        t.verticalHeader().setVisible(False)
        t.horizontalHeader().setStretchLastSection(True)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        t.setAlternatingRowColors(True)
        t.setMinimumHeight(200)
        t.setStyleSheet(
            "QTableWidget { background: white; alternate-background-color: #F9FAFB;"
            " border: 1px solid #E5E7EB; border-radius: 8px; }"
            "QTableWidget::item { padding: 6px 8px; }"
            "QTableWidget::item:selected { background: #EFF3FA; color: #173560; }"
            "QTableWidget::item:hover { background: #F3F4F6; }"
            "QHeaderView::section { background: #F3F4F6; color: #6B7280; font-weight: 600;"
            " border: none; border-bottom: 1px solid #E5E7EB; padding: 8px; }"
        )
        return t

    def on_first_show(self):
        self.refresh()

    def refresh(self):
        stats = dashboard_service.dashboard_stats()
        self._render_stats(stats)
        self._render_alerts(stats)
        self._render_recent_invoices()
        self._render_recent_payments()
        self._render_chart()

    def _soft_refresh(self):
        """Refresh data without full rebuild (avoids UI flicker)."""
        try:
            stats = dashboard_service.dashboard_stats()
            self._render_alerts(stats)
            self._render_recent_invoices()
            self._render_recent_payments()
            self._render_chart()
        except Exception:  # noqa: BLE001
            pass

    def _render_alerts(self, stats):
        """Show overdue invoice alert banner if there are overdue invoices."""
        overdue = stats.get("pending_invoices", 0)
        outstanding = stats.get("total_outstanding", 0)
        if overdue > 0 and outstanding > 0:
            self.alert_label.setText(
                f"⚠  {overdue} pending invoice(s) with {_money(outstanding)} outstanding. "
                f"Click 'View Invoices' to follow up."
            )
            self.alert_frame.setVisible(True)
        else:
            self.alert_frame.setVisible(False)

    def _render_stats(self, stats):
        while self._stats_grid.count():
            item = self._stats_grid.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        cards = [
            ("Total Customers", str(stats["total_customers"]), PRIMARY, "customers"),
            ("Total Invoices", str(stats["total_invoices"]), PRIMARY, "invoices"),
            ("Today's Income", _money(stats["today_income"]), SUCCESS, None),
            ("Monthly Income", _money(stats["monthly_income"]), SUCCESS, "reports"),
            ("Total Income", _money(stats["total_income"]), SUCCESS, "reports"),
            ("Total Outstanding", _money(stats["total_outstanding"]), WARNING, "invoices"),
            ("Paid Invoices", str(stats["paid_invoices"]), "#3B82F6", "invoices"),
            ("Pending Invoices", str(stats["pending_invoices"]), DANGER, "invoices"),
        ]
        for i, (title, val, accent, nav) in enumerate(cards):
            row, col = divmod(i, 4)
            card_widget = ClickableStatCard(title, val, accent, navigate_to=nav)
            self._stats_grid.addWidget(card_widget, row, col)

    def _render_recent_invoices(self):
        t = self.recent_invoices_table
        invoices = dashboard_service.recent_invoices(6)
        t.setRowCount(0)
        if not invoices:
            t.setRowCount(1)
            empty = QTableWidgetItem("No invoices yet. Create your first invoice!")
            empty.setTextAlignment(Qt.AlignCenter)
            empty.setFlags(Qt.ItemIsEnabled)
            t.setItem(0, 0, empty)
            t.setSpan(0, 0, 1, 5)
            return
        for inv in invoices:
            r = t.rowCount()
            t.insertRow(r)
            customer = inv.customer.name if inv.customer else "-"
            total = float(inv.grand_total or 0)
            paid = sum(float(p.amount or 0) for p in (inv.payments or []))
            if total == 0:
                status = "DRAFT" if inv.status == "DRAFT" else "UNPAID"
            elif paid <= 0:
                if inv.due_date and inv.due_date < __import__("datetime").date.today():
                    status = "OVERDUE"
                else:
                    status = "UNPAID"
            elif paid >= total:
                status = "PAID"
            else:
                if inv.due_date and inv.due_date < __import__("datetime").date.today():
                    status = "OVERDUE"
                else:
                    status = "PARTIALLY PAID"
            vals = [inv.invoice_number, customer,
                    inv.invoice_date.strftime("%d-%b-%Y") if inv.invoice_date else "-",
                    status, _money(inv.grand_total)]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(str(v))
                item.setData(Qt.UserRole, inv.id)
                if c == 3:
                    item.setForeground(
                        Qt.GlobalColor.darkBlue if status == "PAID"
                        else Qt.GlobalColor.darkYellow if "PART" in status
                        else Qt.GlobalColor.darkRed if status in ("OVERDUE", "UNPAID")
                        else Qt.GlobalColor.darkGray)
                t.setItem(r, c, item)

    def _on_invoice_double_click(self, row, col):
        """Open invoice editor when double-clicking a row."""
        item = self.recent_invoices_table.item(row, 0)
        if item:
            inv_id = item.data(Qt.UserRole)
            if inv_id:
                self._open_invoice(inv_id)

    def _open_invoice(self, inv_id):
        """Navigate to invoices page and open the specific invoice."""
        if self.main_window:
            inv_page = self.main_window.pages.get("invoices")
            if inv_page:
                inv_page._edit_row_by_id(inv_id)
                self.main_window.show_page("invoices")

    def _render_recent_payments(self):
        t = self.recent_payments_table
        payments = dashboard_service.recent_payments(6)
        t.setRowCount(0)
        if not payments:
            t.setRowCount(1)
            empty = QTableWidgetItem("No payments recorded yet.")
            empty.setTextAlignment(Qt.AlignCenter)
            empty.setFlags(Qt.ItemIsEnabled)
            t.setItem(0, 0, empty)
            t.setSpan(0, 0, 1, 4)
            return
        for p in payments:
            r = t.rowCount()
            t.insertRow(r)
            inv_no = p.invoice.invoice_number if p.invoice else "-"
            vals = [p.date.strftime("%d-%b-%Y") if p.date else "-",
                    inv_no, p.mode, _money(p.amount)]
            for c, v in enumerate(vals):
                t.setItem(r, c, QTableWidgetItem(str(v)))

    def _render_chart(self):
        if not getattr(self, "_chart_enabled", False):
            return
        try:
            months = dashboard_service.monthly_income_for_year(6)
            last6 = months[-6:] if len(months) > 6 else months
            values = [m["total"] for m in last6]
            labels = [m["month"][2:] + "/" + m["month"][:2] if len(m["month"]) >= 5
                      else m["month"] for m in last6]
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

    def _navigate_to(self, page_key, new_invoice=False):
        """Navigate to another page."""
        if self.main_window:
            if new_invoice:
                inv_page = self.main_window.pages.get("invoices")
                if inv_page:
                    inv_page.start_new_invoice()
            self.main_window.show_page(page_key)
