"""Live dashboard page — clickable, fast, and informative.

Features:
- Payment collection alert banner for overdue accounts.
- Executive quick-action hub (+ New Invoice, + Add Customer, Invoices, Reports).
- 4 High-Impact Hero KPI metric cards + secondary business metrics.
- Left column (58%): Recent Activity with Tab Switcher (Recent Invoices / Recent Payments) + Monthly Revenue Trend Chart.
- Right column (42%): Top Pending Collections Follow-up with 1-click WhatsApp payment reminders.
- Auto-refresh keeps data current every 30 seconds without UI flicker.
"""
from __future__ import annotations

from datetime import datetime, timezone
from urllib.parse import quote

from PySide6.QtCore import QMargins, Qt, QTimer, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.services import customer_service, dashboard_service
from app.services.business_service import get_profile
from app.services.invoice_service import compute_status
from app.ui.pages.base_page import BasePage
from app.ui.style import DANGER, PRIMARY, SUCCESS, WARNING
from app.ui.widgets.common import _dark_or_light


def _money(v) -> str:
    return f"\u20B9 {float(v or 0):,.2f}"


class ClickableStatCard(QFrame):
    """Stat card that navigates to a page on click.

    Created once and updated in-place via ``set_value()`` and ``set_sub()``
    to avoid widget recreation on every dashboard refresh.
    """

    def __init__(self, title: str, value: str, accent: str = PRIMARY,
                 sub_text: str = "", navigate_to: str | None = None, parent=None):
        super().__init__(parent)
        self.setObjectName("dashStatCard")
        self._navigate_to = navigate_to
        self._accent = accent
        self.setCursor(Qt.PointingHandCursor if navigate_to else Qt.ArrowCursor)
        self.setStyleSheet(
            f"QFrame#dashStatCard {{ border-left: 4px solid {accent};"
            f" background: #FFFFFF;"
            f" border: 1px solid #E2E8F0;"
            f" border-radius: 12px; border-left: 4px solid {accent}; }}"
            f"QFrame#dashStatCard:hover {{ border-color: #CBD5E1; background: #F8FAFC; }}"
        )
        lay = QVBoxLayout(self)
        lay.setContentsMargins(18, 14, 18, 14)
        lay.setSpacing(3)

        t = QLabel(title)
        t.setObjectName("dashStatLabel")
        t.setStyleSheet("font-size: 10px; font-weight: 700; color: #64748B; letter-spacing: 0.5px;")

        v = QLabel(value)
        v.setObjectName("dashStatValue")
        v.setStyleSheet(f"color: {accent}; font-size: 20px; font-weight: 800;")

        self.sub = QLabel(sub_text)
        self.sub.setStyleSheet("font-size: 11px; color: #94A3B8;")

        lay.addWidget(t)
        lay.addWidget(v)
        lay.addWidget(self.sub)

        self._value_label = v
        self._title_label = t

    def set_value(self, value: str):
        self._value_label.setText(value)

    def set_sub(self, text: str):
        self.sub.setText(text)

    def mousePressEvent(self, ev):
        if ev.button() == Qt.LeftButton and self._navigate_to:
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
        self._stat_cards = {}
        self._chart_enabled = False
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(28, 20, 28, 20)
        outer.setSpacing(14)

        # --- 1. Overdue Alert Banner ---
        self.alert_frame = QFrame()
        self.alert_frame.setObjectName("dashAlert")
        self.alert_frame.setStyleSheet(
            "QFrame#dashAlert { background: #FEF2F2; border: 1px solid #FECACA; "
            "border-left: 5px solid #DC2626; border-radius: 10px; padding: 6px 14px; }"
        )
        alert_lay = QHBoxLayout(self.alert_frame)
        alert_lay.setContentsMargins(8, 4, 8, 4)
        alert_lay.setSpacing(10)

        alert_icon = QLabel("⚠️")
        alert_icon.setStyleSheet("font-size: 16px;")
        alert_lay.addWidget(alert_icon)

        self.alert_label = QLabel()
        self.alert_label.setObjectName("dashAlertText")
        self.alert_label.setStyleSheet("color: #991B1B; font-weight: 600; font-size: 12px;")
        self.alert_label.setWordWrap(True)
        alert_lay.addWidget(self.alert_label, 1)

        btn_alert_nav = QPushButton("View Overdue Invoices →")
        btn_alert_nav.setCursor(Qt.PointingHandCursor)
        btn_alert_nav.setStyleSheet(
            "background: #DC2626; color: white; border: none; border-radius: 6px; "
            "padding: 5px 12px; font-size: 11px; font-weight: 700;"
        )
        btn_alert_nav.clicked.connect(lambda: self._navigate_to("invoices"))
        alert_lay.addWidget(btn_alert_nav)

        self.alert_frame.setVisible(False)
        outer.addWidget(self.alert_frame)

        # --- 2. Action Hub Bar ---
        actions_row = QHBoxLayout()
        actions_row.setSpacing(10)

        btn_new_inv = QPushButton("+ New Invoice")
        btn_new_inv.setCursor(Qt.PointingHandCursor)
        btn_new_inv.setStyleSheet(
            "QPushButton { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #173560, stop:1 #1E4B85); "
            "color: white; border: none; border-radius: 8px; padding: 8px 18px; font-weight: 700; font-size: 12px; }"
            "QPushButton:hover { background: #0F2547; }"
        )
        btn_new_inv.clicked.connect(lambda: self._navigate_to("invoices", new_invoice=True))

        btn_add_cust = QPushButton("+ Add Customer")
        btn_add_cust.setCursor(Qt.PointingHandCursor)
        btn_add_cust.setStyleSheet(
            "QPushButton { background: #059669; color: white; border: none; border-radius: 8px; "
            "padding: 8px 16px; font-weight: 700; font-size: 12px; }"
            "QPushButton:hover { background: #047857; }"
        )
        btn_add_cust.clicked.connect(lambda: self._navigate_to("customers"))

        btn_view_workers = self._action_btn("👷 Workers", "workers")
        btn_view_inv = self._action_btn("📋 All Invoices", "invoices")
        btn_view_reports = self._action_btn("📊 Reports & Tax", "reports")
        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setStyleSheet(
            "QPushButton { background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 8px; "
            "padding: 8px 14px; font-size: 12px; font-weight: 600; color: #334155; }"
            "QPushButton:hover { background: #F8FAFC; border-color: #2563EB; color: #2563EB; }"
        )
        btn_refresh.clicked.connect(self.refresh)

        actions_row.addWidget(btn_new_inv)
        actions_row.addWidget(btn_add_cust)
        actions_row.addWidget(btn_view_workers)
        actions_row.addWidget(btn_view_inv)
        actions_row.addWidget(btn_view_reports)
        actions_row.addStretch(1)
        actions_row.addWidget(btn_refresh)
        outer.addLayout(actions_row)

        # --- 3. Hero KPI Metric Cards (4 Cards) ---
        self._stats_grid = QGridLayout()
        self._stats_grid.setSpacing(12)
        outer.addLayout(self._stats_grid)
        self._build_stat_cards()

        # --- 4. Main Body: Split into Two Columns (58% / 42%) ---
        split_layout = QHBoxLayout()
        split_layout.setSpacing(14)
        outer.addLayout(split_layout, 1)

        # Left Column: Recent Activity (Tabbed Invoices/Payments) + Monthly Chart
        left_col = QVBoxLayout()
        left_col.setSpacing(12)
        split_layout.addLayout(left_col, 58)

        # Card: Recent Activity with Tab Switcher
        rec_card = QFrame()
        rec_card.setObjectName("dashSectionCard")
        rec_card.setStyleSheet("QFrame#dashSectionCard { background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 12px; }")
        rec_lay = QVBoxLayout(rec_card)
        rec_lay.setContentsMargins(12, 10, 12, 10)
        rec_lay.setSpacing(8)

        tab_header = QHBoxLayout()
        tab_header.setSpacing(8)

        self.btn_tab_invoices = QPushButton("📄 Recent Invoices")
        self.btn_tab_invoices.setCursor(Qt.PointingHandCursor)
        self.btn_tab_invoices.clicked.connect(lambda: self._switch_activity_tab(0))

        self.btn_tab_payments = QPushButton("💵 Recent Payments")
        self.btn_tab_payments.setCursor(Qt.PointingHandCursor)
        self.btn_tab_payments.clicked.connect(lambda: self._switch_activity_tab(1))

        tab_header.addWidget(self.btn_tab_invoices)
        tab_header.addWidget(self.btn_tab_payments)
        tab_header.addStretch(1)
        rec_lay.addLayout(tab_header)

        self.activity_stack = QStackedWidget()

        # Tab 0: Recent Invoices Table
        self.recent_invoices_table = self._make_table(["INVOICE NO", "CUSTOMER", "DATE", "STATUS", "AMOUNT"])
        hh_inv = self.recent_invoices_table.horizontalHeader()
        hh_inv.setSectionResizeMode(0, QHeaderView.Interactive)
        hh_inv.setSectionResizeMode(1, QHeaderView.Stretch)
        hh_inv.setSectionResizeMode(2, QHeaderView.Interactive)
        hh_inv.setSectionResizeMode(3, QHeaderView.Interactive)
        hh_inv.setSectionResizeMode(4, QHeaderView.Interactive)
        self.recent_invoices_table.setColumnWidth(0, 155)
        self.recent_invoices_table.setColumnWidth(2, 105)
        self.recent_invoices_table.setColumnWidth(3, 140)
        self.recent_invoices_table.setColumnWidth(4, 115)
        self.recent_invoices_table.cellDoubleClicked.connect(self._on_invoice_double_click)
        self.activity_stack.addWidget(self.recent_invoices_table)

        # Tab 1: Recent Payments Table
        self.recent_payments_table = self._make_table(["DATE", "INVOICE", "MODE", "REFERENCE", "AMOUNT"])
        hh_pay = self.recent_payments_table.horizontalHeader()
        hh_pay.setSectionResizeMode(0, QHeaderView.Interactive)
        hh_pay.setSectionResizeMode(1, QHeaderView.Interactive)
        hh_pay.setSectionResizeMode(2, QHeaderView.Interactive)
        hh_pay.setSectionResizeMode(3, QHeaderView.Stretch)
        hh_pay.setSectionResizeMode(4, QHeaderView.Interactive)
        self.recent_payments_table.setColumnWidth(0, 105)
        self.recent_payments_table.setColumnWidth(1, 135)
        self.recent_payments_table.setColumnWidth(2, 100)
        self.recent_payments_table.setColumnWidth(4, 115)
        self.activity_stack.addWidget(self.recent_payments_table)

        rec_lay.addWidget(self.activity_stack)
        left_col.addWidget(rec_card, 3)

        self._switch_activity_tab(0)

        # Card: Monthly Revenue Chart
        chart_card = QFrame()
        chart_card.setObjectName("dashSectionCard")
        chart_card.setStyleSheet("QFrame#dashSectionCard { background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 12px; }")
        chart_lay = QVBoxLayout(chart_card)
        chart_lay.setContentsMargins(12, 10, 12, 10)
        chart_lay.setSpacing(6)

        chart_title = QLabel("📈 Monthly Revenue Trend (Last 6 Months)")
        chart_title.setStyleSheet("color: #173560; font-size: 13px; font-weight: 700;")
        chart_lay.addWidget(chart_title)

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
            self.chart.setBackgroundRoundness(8)
            self.chart.setMargins(QMargins(4, 4, 4, 4))
            self.series = QBarSeries()
            self.chart_series = QBarSet("Revenue")
            self.chart_series.setColor(_QC("#2563EB"))
            self.series.append(self.chart_series)
            self.chart.addSeries(self.series)
            self.chart.legend().setVisible(False)

            self.axis_x = QBarCategoryAxis()
            self.axis_y = QValueAxis()
            self.chart.addAxis(self.axis_x, Qt.AlignBottom)
            self.chart.addAxis(self.axis_y, Qt.AlignLeft)
            self.series.attachAxis(self.axis_x)
            self.series.attachAxis(self.axis_y)
            self.axis_y.setLabelFormat("%.0f")

            self.chart_view = QChartView(self.chart)
            self.chart_view.setMinimumHeight(160)
            chart_lay.addWidget(self.chart_view)
            self._chart_enabled = True
        except Exception:
            self._chart_enabled = False
            lbl = QLabel("Chart module unavailable.")
            lbl.setStyleSheet("color: #94A3B8; font-size: 11px;")
            chart_lay.addWidget(lbl)

        left_col.addWidget(chart_card, 2)

        # Right Column (42%): Top Pending Collections Follow-up
        right_col = QVBoxLayout()
        right_col.setSpacing(12)
        split_layout.addLayout(right_col, 42)

        pending_card = QFrame()
        pending_card.setObjectName("dashSectionCard")
        pending_card.setStyleSheet("QFrame#dashSectionCard { background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 12px; }")
        pending_lay = QVBoxLayout(pending_card)
        pending_lay.setContentsMargins(12, 10, 12, 10)
        pending_lay.setSpacing(8)

        p_header = QHBoxLayout()
        p_title = QLabel("⚡ Top Collections Follow-Up")
        p_title.setStyleSheet("color: #173560; font-size: 13px; font-weight: 700;")
        p_badge = QLabel("Immediate Attention")
        p_badge.setStyleSheet("background: #FEF2F2; color: #DC2626; border: 1px solid #FECACA; border-radius: 8px; font-size: 10px; font-weight: 700; padding: 2px 8px;")
        p_header.addWidget(p_title)
        p_header.addStretch(1)
        p_header.addWidget(p_badge)
        pending_lay.addLayout(p_header)

        self.pending_collections_table = self._make_table(["CUSTOMER & MOBILE", "DUE AMOUNT", "FOLLOW-UP"])
        hh_pend = self.pending_collections_table.horizontalHeader()
        hh_pend.setSectionResizeMode(0, QHeaderView.Stretch)
        hh_pend.setSectionResizeMode(1, QHeaderView.Interactive)
        hh_pend.setSectionResizeMode(2, QHeaderView.Interactive)
        self.pending_collections_table.setColumnWidth(1, 120)
        self.pending_collections_table.setColumnWidth(2, 175)
        pending_lay.addWidget(self.pending_collections_table)
        right_col.addWidget(pending_card)

        # --- 5. Auto-refresh timer (every 30 seconds) ---
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(30_000)
        self._refresh_timer.timeout.connect(self._soft_refresh)
        self._refresh_timer.start()

    def _switch_activity_tab(self, idx: int):
        self.activity_stack.setCurrentIndex(idx)
        active_style = (
            "background: #173560; color: #FFFFFF; border: none; "
            "border-radius: 6px; padding: 5px 12px; font-size: 11px; font-weight: 700;"
        )
        inactive_style = (
            "background: #F1F5F9; color: #475569; border: 1px solid #E2E8F0; "
            "border-radius: 6px; padding: 5px 12px; font-size: 11px; font-weight: 600;"
        )
        if idx == 0:
            self.btn_tab_invoices.setStyleSheet(active_style)
            self.btn_tab_payments.setStyleSheet(inactive_style)
        else:
            self.btn_tab_invoices.setStyleSheet(inactive_style)
            self.btn_tab_payments.setStyleSheet(active_style)

    def _build_stat_cards(self):
        """Create 5 executive hero metric cards + secondary indicators."""
        self.card_monthly = ClickableStatCard("THIS MONTH REVENUE", "—", "#2563EB", "Today: —", "reports")
        self.card_billed = ClickableStatCard("TOTAL BILLED REVENUE", "—", "#173560", "Across — invoices", "invoices")
        self.card_collected = ClickableStatCard("TOTAL COLLECTED", "—", "#059669", "Across all payment modes", "reports")
        self.card_outstanding = ClickableStatCard("OUTSTANDING DUE", "—", "#DC2626", "— pending invoices", "invoices")
        self.card_workers = ClickableStatCard("WORKERS & LABOUR", "—", "#7C3AED", "Active: —", "workers")

        self._stats_grid.addWidget(self.card_monthly, 0, 0)
        self._stats_grid.addWidget(self.card_billed, 0, 1)
        self._stats_grid.addWidget(self.card_collected, 0, 2)
        self._stats_grid.addWidget(self.card_outstanding, 0, 3)
        self._stats_grid.addWidget(self.card_workers, 0, 4)

        # Mapping for backward compatibility
        self._stat_cards = {
            "monthly_income": self.card_monthly,
            "total_income": self.card_collected,
            "total_outstanding": self.card_outstanding,
            "total_invoices": self.card_billed,
            "today_income": self.card_monthly,
            "total_customers": self.card_billed,
            "paid_invoices": self.card_collected,
            "pending_invoices": self.card_outstanding,
        }

    def _action_btn(self, text: str, page_key: str) -> QPushButton:
        b = QPushButton(text)
        b.setCursor(Qt.PointingHandCursor)
        b.setStyleSheet(
            "QPushButton { background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 8px; "
            "padding: 8px 16px; font-size: 12px; font-weight: 600; color: #1E293B; }"
            "QPushButton:hover { background: #F8FAFC; border-color: #2563EB; color: #2563EB; }"
        )
        b.clicked.connect(lambda: self._navigate_to(page_key))
        return b

    def _make_table(self, headers: list[str]) -> QTableWidget:
        t = QTableWidget(0, len(headers))
        t.setObjectName("dashTable")
        t.setHorizontalHeaderLabels(headers)
        t.setEditTriggers(QTableWidget.NoEditTriggers)
        t.setSelectionBehavior(QTableWidget.SelectRows)
        t.verticalHeader().setVisible(False)
        t.verticalHeader().setDefaultSectionSize(38)
        t.setAlternatingRowColors(True)
        return t

    def on_first_show(self):
        self.refresh()

    def refresh(self):
        stats = dashboard_service.dashboard_stats()
        self._update_stats(stats)
        self._render_alerts(stats)
        self._render_recent_invoices()
        self._render_recent_payments()
        self._render_pending_collections()
        self._render_chart()

    def _soft_refresh(self):
        try:
            stats = dashboard_service.dashboard_stats()
            self._update_stats(stats)
            self._render_alerts(stats)
            self._render_recent_invoices()
            self._render_recent_payments()
            self._render_pending_collections()
            self._render_chart()
        except Exception:
            pass

    def _update_stats(self, stats: dict):
        m_inc = stats.get("monthly_income", 0)
        t_inc = stats.get("today_income", 0)
        tot_inc = stats.get("total_income", 0)
        tot_out = stats.get("total_outstanding", 0)
        tot_inv = stats.get("total_invoices", 0)
        pend_inv = stats.get("pending_invoices", 0)
        paid_inv = stats.get("paid_invoices", 0)
        tot_cust = stats.get("total_customers", 0)

        # Exact billed total from database aggregation
        tot_billed = stats.get("total_billed", float(tot_inc) + float(tot_out))

        self.card_monthly.set_value(_money(m_inc))
        self.card_monthly.set_sub(f"Today: {_money(t_inc)}")

        self.card_billed.set_value(_money(tot_billed))
        self.card_billed.set_sub(f"{tot_inv} invoices • {tot_cust} customers")

        self.card_collected.set_value(_money(tot_inc))
        self.card_collected.set_sub(f"{paid_inv} paid in full")

        self.card_outstanding.set_value(_money(tot_out))
        self.card_outstanding.set_sub(f"{pend_inv} pending payment(s)")

        try:
            from app.services import worker_service
            w_metrics = worker_service.get_dashboard_worker_metrics()
            act_w = w_metrics.get("active_workers", 0)
            cost_w = w_metrics.get("month_work_cost", 0)
            due_w = w_metrics.get("pending_payments", 0)
            self.card_workers.set_value(f"{act_w} Active")
            self.card_workers.set_sub(f"Cost: {_money(cost_w)} • Due: {_money(due_w)}")
        except Exception:
            self.card_workers.set_value("0 Active")
            self.card_workers.set_sub("Worker ledger ready")

    def _render_alerts(self, stats: dict):
        overdue = stats.get("pending_invoices", 0)
        outstanding = stats.get("total_outstanding", 0)
        if overdue > 0 and outstanding > 0:
            self.alert_label.setText(
                f"{overdue} pending invoice(s) with {_money(outstanding)} outstanding balance. Follow up to speed up cash flow."
            )
            self.alert_frame.setVisible(True)
        else:
            self.alert_frame.setVisible(False)

    def _render_recent_invoices(self):
        t = self.recent_invoices_table
        invoices = dashboard_service.recent_invoices(7)
        t.setRowCount(0)
        if not invoices:
            t.setRowCount(1)
            empty = QTableWidgetItem("No invoices yet. Create your first invoice!")
            empty.setTextAlignment(Qt.AlignCenter)
            t.setItem(0, 0, empty)
            t.setSpan(0, 0, 1, 5)
            return

        t.setUpdatesEnabled(False)
        t.setRowCount(len(invoices))
        try:
            for r, inv in enumerate(invoices):
                customer = inv["customer_name"] or "—"
                status = compute_status(inv["grand_total"], inv["paid"], inv["status"], inv["due_date"])

                # Col 0: Invoice No
                it_no = QTableWidgetItem(inv["invoice_number"] or "")
                it_no.setData(Qt.UserRole, inv["id"])
                it_no.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                it_no.setForeground(Qt.GlobalColor.darkBlue)
                t.setItem(r, 0, it_no)

                # Col 1: Customer
                it_cust = QTableWidgetItem(customer)
                it_cust.setData(Qt.UserRole, inv["id"])
                t.setItem(r, 1, it_cust)

                # Col 2: Date
                it_date = QTableWidgetItem(inv["invoice_date"].strftime("%d-%b-%Y") if inv["invoice_date"] else "—")
                it_date.setData(Qt.UserRole, inv["id"])
                t.setItem(r, 2, it_date)

                # Col 3: Status Badge
                w_st = QWidget()
                lay_st = QHBoxLayout(w_st)
                lay_st.setContentsMargins(4, 2, 4, 2)
                lay_st.setAlignment(Qt.AlignCenter)
                badge = QLabel(status)
                badge.setAlignment(Qt.AlignCenter)

                if status == "PAID":
                    badge_style = "background: #ECFDF5; color: #059669; border: 1px solid #A7F3D0;"
                elif status == "PARTIALLY PAID":
                    badge_style = "background: #FFFBEB; color: #D97706; border: 1px solid #FDE68A;"
                elif status == "OVERDUE":
                    badge_style = "background: #FEF2F2; color: #DC2626; border: 1px solid #FECACA;"
                elif status == "UNPAID":
                    badge_style = "background: #EFF6FF; color: #2563EB; border: 1px solid #BFDBFE;"
                else:
                    badge_style = "background: #F1F5F9; color: #475569; border: 1px solid #CBD5E1;"

                badge.setStyleSheet(f"{badge_style} border-radius: 9px; font-weight: 700; font-size: 10px; padding: 2px 8px;")
                lay_st.addWidget(badge)
                it_st = QTableWidgetItem("")
                it_st.setData(Qt.UserRole, inv["id"])
                t.setItem(r, 3, it_st)
                t.setCellWidget(r, 3, w_st)

                # Col 4: Amount
                it_amt = QTableWidgetItem(_money(inv["grand_total"]))
                it_amt.setData(Qt.UserRole, inv["id"])
                it_amt.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                t.setItem(r, 4, it_amt)
        finally:
            t.setUpdatesEnabled(True)

    def _render_recent_payments(self):
        t = self.recent_payments_table
        payments = dashboard_service.recent_payments(7)
        t.setRowCount(0)
        if not payments:
            t.setRowCount(1)
            empty = QTableWidgetItem("No payments recorded yet.")
            empty.setTextAlignment(Qt.AlignCenter)
            t.setItem(0, 0, empty)
            t.setSpan(0, 0, 1, 5)
            return

        t.setUpdatesEnabled(False)
        t.setRowCount(len(payments))
        try:
            for r, p in enumerate(payments):
                t.setItem(r, 0, QTableWidgetItem(p["date"].strftime("%d-%b-%Y") if p["date"] else "—"))
                t.setItem(r, 1, QTableWidgetItem(p["invoice_number"] or "—"))
                t.setItem(r, 2, QTableWidgetItem(p["mode"] or "Cash"))
                t.setItem(r, 3, QTableWidgetItem(p["reference"] or "—"))

                amt = QTableWidgetItem(_money(p["amount"]))
                amt.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                amt.setForeground(Qt.GlobalColor.darkGreen)
                t.setItem(r, 4, amt)
        finally:
            t.setUpdatesEnabled(True)

    def _render_pending_collections(self):
        t = self.pending_collections_table
        items = dashboard_service.top_pending_collections(6)
        t.setRowCount(0)
        if not items:
            t.setRowCount(1)
            empty = QTableWidgetItem("All accounts are fully paid! 🎉")
            empty.setTextAlignment(Qt.AlignCenter)
            t.setItem(0, 0, empty)
            t.setSpan(0, 0, 1, 3)
            return

        t.setUpdatesEnabled(False)
        t.setRowCount(len(items))
        try:
            for r, it in enumerate(items):
                # Col 0: Customer & Mobile (2-line layout)
                w_cust = QWidget()
                lay_cust = QVBoxLayout(w_cust)
                lay_cust.setContentsMargins(6, 2, 6, 2)
                lay_cust.setSpacing(1)
                lbl_name = QLabel(it["customer_name"])
                lbl_name.setStyleSheet("font-weight: 700; color: #0F172A; font-size: 11px;")
                lbl_mob = QLabel(f"☎ {it['mobile']}" if it['mobile'] else "No phone")
                lbl_mob.setStyleSheet("color: #64748B; font-size: 10px;")
                lay_cust.addWidget(lbl_name)
                lay_cust.addWidget(lbl_mob)
                t.setItem(r, 0, QTableWidgetItem(""))
                t.setCellWidget(r, 0, w_cust)

                # Col 1: Due Balance
                it_bal = QTableWidgetItem(_money(it["outstanding"]))
                it_bal.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                it_bal.setForeground(QColor("#DC2626"))
                it_bal.setFont(QFont("Segoe UI", 9, QFont.Bold))
                t.setItem(r, 1, it_bal)

                # Col 2: Action buttons (WhatsApp Remind + Collect Payment)
                w_btn = QWidget()
                lay_btn = QHBoxLayout(w_btn)
                lay_btn.setContentsMargins(2, 2, 2, 2)
                lay_btn.setSpacing(4)
                lay_btn.setAlignment(Qt.AlignCenter)

                btn_remind = QPushButton("💬 Remind")
                btn_remind.setObjectName("dashReminderBtn")
                btn_remind.setCursor(Qt.PointingHandCursor)
                btn_remind.setToolTip("Send WhatsApp reminder message")
                btn_remind.setStyleSheet(
                    "QPushButton#dashReminderBtn { background: #ECFDF5; border: 1px solid #A7F3D0;"
                    " border-radius: 6px; color: #059669; font-weight: 700; font-size: 10px; padding: 4px 6px; }"
                    "QPushButton#dashReminderBtn:hover { background: #D1FAE5; border-color: #6EE7B7; }"
                )
                btn_remind.clicked.connect(lambda _, item=it: self._send_whatsapp_reminder(item))
                lay_btn.addWidget(btn_remind)

                btn_collect = QPushButton("💳 Collect")
                btn_collect.setObjectName("dashCollectBtn")
                btn_collect.setCursor(Qt.PointingHandCursor)
                btn_collect.setToolTip("Record received payment or settle full balance")
                btn_collect.setStyleSheet(
                    "QPushButton#dashCollectBtn { background: #EFF6FF; border: 1px solid #BFDBFE;"
                    " border-radius: 6px; color: #1D4ED8; font-weight: 700; font-size: 10px; padding: 4px 6px; }"
                    "QPushButton#dashCollectBtn:hover { background: #DBEAFE; border-color: #93C5FD; }"
                )
                btn_collect.clicked.connect(lambda _, item=it: self._open_payment_for_customer(item))
                lay_btn.addWidget(btn_collect)

                t.setItem(r, 2, QTableWidgetItem(""))
                t.setCellWidget(r, 2, w_btn)
        finally:
            t.setUpdatesEnabled(True)

    def _open_payment_for_customer(self, item: dict):
        """Open payment dialog for customer's pending invoice directly from Dashboard."""
        inv_id = item.get("primary_invoice_id")
        if not inv_id:
            from app.services import invoice_service
            invoices = invoice_service.list_invoices_for_customer(item.get("customer_id"))
            for inv in invoices:
                if inv.status != "DRAFT":
                    due = invoice_service.invoice_outstanding(inv)
                    if due > 0.009:
                        inv_id = inv.id
                        break
        if not inv_id:
            QMessageBox.information(self, "No Pending Invoice", "No pending unpaid invoice found for this customer.")
            return

        from app.services import invoice_service
        from app.ui.pages.payment_dialog import PaymentDialog
        inv = invoice_service.get_invoice(inv_id)
        if inv:
            dlg = PaymentDialog(inv, self)
            dlg.exec()
            self.refresh()
            if self.main_window and hasattr(self.main_window, "refresh_all"):
                self.main_window.refresh_all()

    def _send_dashboard_whatsapp(self, customer_id: int):
        c = customer_service.get_customer(customer_id)
        if not c or not c.mobile:
            QMessageBox.warning(self, "WhatsApp Reminder", "Customer has no mobile number saved.")
            return

        profile = get_profile()
        biz_name = profile.business_name if profile else "Our Store"
        totals = customer_service.customer_totals(customer_id)
        outstanding = float(totals.get("outstanding", 0) or 0)

        mob = "".join(filter(str.isdigit, c.mobile))
        if len(mob) == 10:
            mob = f"91{mob}"

        msg = (
            f"Dear {c.name},\n\n"
            f"Greetings from *{biz_name}*!\n\n"
            f"This is a gentle reminder regarding your pending balance of *₹ {outstanding:,.2f}*.\n"
        )
        if profile and profile.upi_id:
            msg += f"UPI Payment ID: *{profile.upi_id}*\n"
        if profile and profile.bank_name:
            msg += f"Bank: *{profile.bank_name}* | A/C: *{profile.account_number}* | IFSC: *{profile.ifsc_code}*\n"
        msg += "\nKindly clear the balance at your earliest convenience. Thank you!"

        url = f"https://wa.me/{mob}?text={quote(msg)}"
        QDesktopServices.openUrl(QUrl(url))

    def _render_chart(self):
        if not getattr(self, "_chart_enabled", False):
            return
        try:
            months = dashboard_service.monthly_income_for_year(6)
            last6 = months[-6:] if len(months) > 6 else months
            values = [m["total"] for m in last6]
            labels = []
            for m in last6:
                try:
                    dt = datetime.strptime(m["month"], "%Y-%m")
                    labels.append(dt.strftime("%b '%y"))
                except Exception:
                    labels.append(m["month"])

            count = self.chart_series.count()
            if count > 0:
                self.chart_series.remove(0, count)
            for v in values:
                self.chart_series.append(float(v))
            self.axis_x.clear()
            self.axis_x.append(labels or ["-"])
            top = max(max(values, default=0) * 1.15, 10.0)
            self.axis_y.setRange(0, top)
        except Exception:
            pass

    def _on_invoice_double_click(self, row, col):
        item = self.recent_invoices_table.item(row, 0)
        if item:
            inv_id = item.data(Qt.UserRole)
            if inv_id:
                self._open_invoice(inv_id)

    def _open_invoice(self, inv_id: int):
        if self.main_window:
            inv_page = self.main_window.pages.get("invoices")
            if inv_page:
                inv_page._edit_row_by_id(inv_id)
                self.main_window.show_page("invoices")

    def _navigate_to(self, page_key: str, new_invoice: bool = False):
        if self.main_window:
            if new_invoice:
                inv_page = self.main_window.pages.get("invoices")
                if inv_page:
                    inv_page.start_new_invoice()
            self.main_window.show_page(page_key)
