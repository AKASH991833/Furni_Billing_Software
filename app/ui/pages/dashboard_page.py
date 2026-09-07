"""Live dashboard page — clickable, fast, and informative.

Stat cards navigate to relevant pages on click.
Table rows open invoices/payments on double-click.
Quick action buttons for common tasks.
Auto-refresh keeps data current.
Overdue alerts shown prominently.

Performance: stat cards are created once and updated in-place on
refresh, avoiding widget recreation overhead and UI flicker.
"""
from __future__ import annotations

from PySide6.QtCore import QMargins, Qt, QTimer
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.services import dashboard_service
from app.services.invoice_service import compute_status
from app.ui.pages.base_page import BasePage
from app.ui.style import DANGER, PRIMARY, SUCCESS, WARNING
from app.ui.widgets.common import _dark_or_light


def _money(v) -> str:
    return f"\u20B9 {float(v or 0):,.2f}"


class ClickableStatCard(QFrame):
    """Stat card that navigates to a page on click.

    Created once and updated in-place via ``set_value()`` to avoid
    widget recreation on every dashboard refresh.
    """

    def __init__(self, title: str, value: str, accent: str = PRIMARY,
                 navigate_to: str | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("dashStatCard")
        self._navigate_to = navigate_to
        self._accent = accent
        self.setCursor(Qt.PointingHandCursor if navigate_to else Qt.ArrowCursor)
        self.setStyleSheet(
            f"QFrame#dashStatCard {{ border-left: 4px solid {accent};"
            f" background: {_dark_or_light('qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 rgba(31,41,55,0.92),stop:1 rgba(28,38,51,0.88))', 'qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 rgba(255,255,255,0.92),stop:1 rgba(248,250,254,0.88))')};"
            f" border: 1px solid {_dark_or_light('rgba(55,65,81,0.5)','rgba(200,210,230,0.5)')};"
            f" border-radius: 14px; border-left: 4px solid {accent}; }}"
            f"QFrame#dashStatCard:hover {{ border-color: rgba(37, 99, 235, 0.3);"
            f" background: {_dark_or_light('qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 rgba(30,41,59,0.95),stop:1 rgba(30,41,55,0.9))','qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 rgba(255,255,255,0.96),stop:1 rgba(240,244,252,0.92))')}; }}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 16, 18, 16)
        lay.setSpacing(4)
        v = QLabel(value)
        v.setObjectName("dashStatValue")
        v.setStyleSheet(f"color: {accent};")
        t = QLabel(title)
        t.setObjectName("dashStatLabel")
        lay.addWidget(v)
        lay.addWidget(t)
        self._value_label = v  # direct reference for in-place updates

    def set_value(self, value: str):
        """Update the displayed value without recreating the widget."""
        self._value_label.setText(value)

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
        self._stat_cards = {}  # key -> ClickableStatCard for in-place updates
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 22, 28, 22)
        outer.setSpacing(14)

        # --- Overdue alert banner (glass danger) ---
        self.alert_frame = QFrame()
        self.alert_frame.setObjectName("dashAlert")
        alert_lay = QHBoxLayout(self.alert_frame)
        alert_lay.setContentsMargins(18, 12, 18, 12)
        self.alert_label = QLabel()
        self.alert_label.setObjectName("dashAlertText")
        self.alert_label.setWordWrap(True)
        alert_lay.addWidget(self.alert_label)
        self.alert_frame.setVisible(False)
        outer.addWidget(self.alert_frame)

        # --- Quick action buttons (glass) ---
        actions_row = QHBoxLayout()
        actions_row.setSpacing(10)
        btn_new_inv = self._action_btn("+ New Invoice", PRIMARY)
        btn_new_inv.setObjectName("dashActionPrimary")
        btn_new_inv.clicked.connect(lambda: self._navigate_to("invoices", new_invoice=True))
        btn_view_inv = self._action_btn("View Invoices", _dark_or_light("#374151", "#6B7280"))
        btn_view_inv.setObjectName("dashActionSecondary")
        btn_view_inv.clicked.connect(lambda: self._navigate_to("invoices"))
        btn_add_cust = self._action_btn("+ Add Customer", _dark_or_light("#374151", "#6B7280"))
        btn_add_cust.setObjectName("dashActionSecondary")
        btn_add_cust.clicked.connect(lambda: self._navigate_to("customers"))
        btn_view_reports = self._action_btn("Reports", _dark_or_light("#374151", "#6B7280"))
        btn_view_reports.setObjectName("dashActionSecondary")
        btn_view_reports.clicked.connect(lambda: self._navigate_to("reports"))
        actions_row.addWidget(btn_new_inv)
        actions_row.addWidget(btn_view_inv)
        actions_row.addWidget(btn_add_cust)
        actions_row.addWidget(btn_view_reports)
        actions_row.addStretch(1)
        outer.addLayout(actions_row)

        # --- Stats grid (built once, updated in-place) ---
        self._stats_grid = QGridLayout()
        self._stats_grid.setSpacing(12)
        outer.addLayout(self._stats_grid)
        self._build_stat_cards()

        # --- Bottom row: Recent Invoices + Recent Payments (glass cards) ---
        bottom = QHBoxLayout()
        bottom.setSpacing(14)
        outer.addLayout(bottom, 1)

        rec_inv_card = self._section_card("Recent Invoices")
        self.recent_invoices_table = self._make_table(
            ["Invoice No", "Customer", "Date", "Status", "Amount"], 5)
        self.recent_invoices_table.setObjectName("dashTable")
        self.recent_invoices_table.cellDoubleClicked.connect(self._on_invoice_double_click)
        rec_inv_card.layout().addWidget(self.recent_invoices_table)
        bottom.addWidget(rec_inv_card, 3)

        rec_pay_card = self._section_card("Recent Payments")
        self.recent_payments_table = self._make_table(
            ["Date", "Invoice", "Mode", "Amount"], 4)
        self.recent_payments_table.setObjectName("dashTable")
        rec_pay_card.layout().addWidget(self.recent_payments_table)
        bottom.addWidget(rec_pay_card, 2)

        # --- Monthly income chart (glass card) ---
        chart_card = self._section_card("Monthly Income (last 6 months)")
        try:
            from PySide6.QtCharts import (
                QBarCategoryAxis,
                QBarSeries,
                QBarSet,
                QChart,
                QChartView,
                QValueAxis,
            )
            from PySide6.QtGui import QColor as _QC

            self.chart = QChart()
            self.chart.setBackgroundRoundness(10)
            self.chart.setMargins(QMargins(0, 0, 0, 0))
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

    def _build_stat_cards(self):
        """Create stat cards once. They are updated in-place on refresh."""
        card_defs = [
            ("total_customers", "Total Customers", PRIMARY, "customers"),
            ("total_invoices", "Total Invoices", PRIMARY, "invoices"),
            ("today_income", "Today's Income", SUCCESS, None),
            ("monthly_income", "Monthly Income", SUCCESS, "reports"),
            ("total_income", "Total Income", SUCCESS, "reports"),
            ("total_outstanding", "Total Outstanding", WARNING, "invoices"),
            ("paid_invoices", "Paid Invoices", "#3B82F6", "invoices"),
            ("pending_invoices", "Pending Invoices", DANGER, "invoices"),
        ]
        for i, (key, title, accent, nav) in enumerate(card_defs):
            row, col = divmod(i, 4)
            card = ClickableStatCard(title, "—", accent, navigate_to=nav)
            self._stats_grid.addWidget(card, row, col)
            self._stat_cards[key] = card

    def _action_btn(self, text, color=PRIMARY):
        """Create a quick action button."""
        btn = QPushButton(text)
        btn.setCursor(Qt.PointingHandCursor)
        # Default style — overridden by setObjectName in _build()
        btn.setStyleSheet(
            f"QPushButton {{ background: {color}; color: white; border: none;"
            " border-radius: 10px; padding: 9px 20px; font-weight: 600; font-size: 12px; }"
            f"QPushButton:hover {{ background: {color}DD; }}"
        )
        return btn

    def _section_card(self, title):
        """Create a glass card section with a title."""
        c = QFrame()
        c.setObjectName("dashSectionCard")
        v = QVBoxLayout(c)
        v.setContentsMargins(16, 14, 16, 14)
        v.setSpacing(8)
        t = QLabel(title)
        t.setObjectName("dashSectionTitle")
        v.addWidget(t)
        return c

    def _make_table(self, headers, hidden_rows=5):
        t = QTableWidget(0, len(headers))
        t.setObjectName("dashTable")
        t.setHorizontalHeaderLabels(headers)
        t.setEditTriggers(QTableWidget.NoEditTriggers)
        t.setSelectionBehavior(QTableWidget.SelectRows)
        t.verticalHeader().setVisible(False)
        t.horizontalHeader().setStretchLastSection(True)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        t.setAlternatingRowColors(True)
        t.setMinimumHeight(200)
        return t

    def on_first_show(self):
        self.refresh()

    def refresh(self):
        stats = dashboard_service.dashboard_stats()
        self._update_stats(stats)
        self._render_alerts(stats)
        self._render_recent_invoices()
        self._render_recent_payments()
        self._render_chart()

    def _soft_refresh(self):
        """Refresh data without full rebuild (avoids UI flicker)."""
        try:
            stats = dashboard_service.dashboard_stats()
            self._update_stats(stats)
            self._render_alerts(stats)
            self._render_recent_invoices()
            self._render_recent_payments()
            self._render_chart()
        except Exception:  # noqa: BLE001, S110
            pass


    def _render_alerts(self, stats):
        """Show overdue invoice alert banner if there are overdue invoices."""
        overdue = stats.get("pending_invoices", 0)
        outstanding = stats.get("total_outstanding", 0)
        if overdue > 0 and outstanding > 0:
            self.alert_label.setText(
                f"\u26A0  {overdue} pending invoice(s) with {_money(outstanding)} outstanding. "
                f"Click 'View Invoices' to follow up."
            )
            self.alert_frame.setVisible(True)
        else:
            self.alert_frame.setVisible(False)

    def _update_stats(self, stats):
        """Update stat card values in-place (no widget recreation)."""
        formatters = {
            "total_customers": lambda v: str(v),
            "total_invoices": lambda v: str(v),
            "today_income": _money,
            "monthly_income": _money,
            "total_income": _money,
            "total_outstanding": _money,
            "paid_invoices": lambda v: str(v),
            "pending_invoices": lambda v: str(v),
        }
        for key, card in self._stat_cards.items():
            fmt = formatters.get(key, str)
            card.set_value(fmt(stats.get(key, 0)))

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
            customer = inv["customer_name"] or "-"
            status = compute_status(
                inv["grand_total"], inv["paid"],
                inv["status"], inv["due_date"],
            )
            vals = [inv["invoice_number"], customer,
                    inv["invoice_date"].strftime("%d-%b-%Y") if inv["invoice_date"] else "-",
                    status, _money(inv["grand_total"])]
            for c, v in enumerate(vals):
                item = QTableWidgetItem(str(v))
                item.setData(Qt.UserRole, inv["id"])
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
            inv_no = p["invoice_number"] or "-"
            vals = [p["date"].strftime("%d-%b-%Y") if p["date"] else "-",
                    inv_no, p["mode"], _money(p["amount"])]
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
        except Exception:  # noqa: BLE001, S110
            pass

    def _navigate_to(self, page_key, new_invoice=False):
        """Navigate to another page."""
        if self.main_window:
            if new_invoice:
                inv_page = self.main_window.pages.get("invoices")
                if inv_page:
                    inv_page.start_new_invoice()
            self.main_window.show_page(page_key)
