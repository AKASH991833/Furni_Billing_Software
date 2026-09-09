"""Customer management page — Executive Client Directory & Dossier.

Features:
- Top KPI ribbon: Total Clients, Active Accounts, Total Receivables, Fully Settled
- Segmented filter pills with live counts: All, With Balance Due, Fully Settled, GST Registered (B2B)
- High-contrast client directory table with live balances, GST badges, and contact details
- Executive Client Dossier (Right Panel):
  - Initials avatar badge, contact info, GSTIN badge
  - Financial health cards (Invoiced, Collected, Balance Due)
  - One-click action hub: + New Invoice, WhatsApp Balance Reminder, Statement PDF, Edit, Delete
  - Tabbed history: Complete Invoices ledger and Payments history
- CSV Export with UTF-8 BOM encoding for Excel compatibility
"""
from __future__ import annotations

import csv
import os
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.pdf.customer_statement_pdf import save_customer_statement_pdf
from app.services import business_service, customer_service
from app.ui.pages.base_page import BasePage
from app.ui.style import PRIMARY, SUCCESS, WARNING
from app.ui.widgets.common import card, primary_button, show_toast


def _money(v) -> str:
    return f"\u20B9 {float(v or 0):,.2f}"


class CustomerDialog(QDialog):
    """Add / Edit customer modal dialog."""

    def __init__(self, parent=None, customer=None):
        super().__init__(parent)
        self.customer = customer
        self.setWindowTitle("Edit Customer Profile" if customer else "Add New Customer")
        self.setMinimumWidth(480)
        self.resize(520, 600)
        v = QVBoxLayout(self)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(14)

        title = QLabel("Edit Customer Profile" if customer else "Add New Customer")
        title.setStyleSheet("font-size: 16px; font-weight: 800; color: #0F172A;")
        v.addWidget(title)

        form = QFormLayout()
        form.setVerticalSpacing(10)

        def _lab(t):
            l = QLabel(t)
            l.setStyleSheet("font-size: 11px; font-weight: 700; color: #475569;")
            return l

        self.f_name = QLineEdit()
        self.f_name.setPlaceholderText("Customer or Business Name")
        self.f_mobile = QLineEdit()
        self.f_mobile.setPlaceholderText("10-digit mobile number")
        self.f_alt = QLineEdit()
        self.f_alt.setPlaceholderText("Optional alternate contact")
        self.f_email = QLineEdit()
        self.f_email.setPlaceholderText("client@example.com")
        self.f_address = QTextEdit()
        self.f_address.setFixedHeight(65)
        self.f_address.setPlaceholderText("Street / Building / Area")
        self.f_city = QLineEdit()
        self.f_city.setPlaceholderText("e.g. Mumbai, Pune, Thane")
        self.f_state = QLineEdit()
        self.f_state.setPlaceholderText("e.g. Maharashtra")
        self.f_gstin = QLineEdit()
        self.f_gstin.setPlaceholderText("15-digit GSTIN (e.g. 27AAAAA0000A1Z5)")
        self.f_notes = QTextEdit()
        self.f_notes.setFixedHeight(60)
        self.f_notes.setPlaceholderText("Internal preferences or notes")

        form.addRow(_lab("Customer Name *"), self.f_name)
        form.addRow(_lab("Mobile Number"), self.f_mobile)
        form.addRow(_lab("Alternate Mobile"), self.f_alt)
        form.addRow(_lab("Email Address"), self.f_email)
        form.addRow(_lab("Site / Billing Address"), self.f_address)
        form.addRow(_lab("City"), self.f_city)
        form.addRow(_lab("State"), self.f_state)
        form.addRow(_lab("GSTIN (Tax ID)"), self.f_gstin)
        form.addRow(_lab("Notes"), self.f_notes)
        v.addLayout(form)

        if customer:
            self.f_name.setText(customer.name or "")
            self.f_mobile.setText(customer.mobile or "")
            self.f_alt.setText(customer.alternate_mobile or "")
            self.f_email.setText(customer.email or "")
            self.f_address.setPlainText(customer.address or "")
            self.f_city.setText(customer.city or "")
            self.f_state.setText(customer.state or "")
            self.f_gstin.setText(customer.gstin or "")
            self.f_notes.setPlainText(customer.notes or "")

        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(
            "QPushButton { background: #F1F5F9; color: #475569; font-weight: 600; "
            "border: 1px solid #CBD5E1; border-radius: 6px; padding: 7px 16px; font-size: 12px; } "
            "QPushButton:hover { background: #E2E8F0; }"
        )
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save Customer")
        save.setStyleSheet(
            "QPushButton { background: #2563EB; color: #FFFFFF; font-weight: 700; "
            "border: none; border-radius: 6px; padding: 7px 20px; font-size: 12px; } "
            "QPushButton:hover { background: #1D4ED8; }"
        )
        save.clicked.connect(self._save)
        btns.addWidget(cancel)
        btns.addWidget(save)
        v.addLayout(btns)

    def _save(self):
        data = {
            "name": self.f_name.text().strip(),
            "mobile": self.f_mobile.text().strip(),
            "alternate_mobile": self.f_alt.text().strip(),
            "email": self.f_email.text().strip(),
            "address": self.f_address.toPlainText().strip(),
            "city": self.f_city.text().strip(),
            "state": self.f_state.text().strip(),
            "gstin": self.f_gstin.text().strip(),
            "notes": self.f_notes.toPlainText().strip(),
        }
        from app.utils.validators import validate_customer
        errors = validate_customer(data)
        if errors:
            show_toast(self, errors[0].message, "error")
            return
        self._data = data
        self.accept()

    def result_data(self) -> dict:
        return getattr(self, "_data", {})


class CustomersPage(BasePage):
    """Modernized Customer Management & Accounts Receivable Workstation."""

    def __init__(self, main_window=None, parent=None):
        super().__init__(main_window, parent)
        self.setObjectName("customersPage")
        self._current_customer_id: int | None = None
        self._customers_cache: list[dict] = []
        self._active_filter: str = "ALL"
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 20)
        root.setSpacing(14)

        # 1. Top Executive KPI Ribbon
        kpi_ribbon = self._build_kpi_ribbon()
        root.addLayout(kpi_ribbon)

        # 2. Directory Toolbar & Filter Pill Strip
        toolbar = self._build_toolbar()
        root.addLayout(toolbar)

        # 3. Two-Column Splitter (Directory Table vs Customer Dossier)
        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setHandleWidth(8)

        # Left: Customer Directory Table Container
        left_box = self._build_directory_panel()
        self.splitter.addWidget(left_box)

        # Right: Customer Dossier Panel
        right_box = self._build_dossier_panel()
        self.splitter.addWidget(right_box)

        # 53% directory / 47% dossier
        self.splitter.setSizes([640, 560])
        root.addWidget(self.splitter, 1)


    # -------------------------------------------------------------------------
    # 1. Top KPI Summary Ribbon
    # -------------------------------------------------------------------------
    def _build_kpi_ribbon(self) -> QHBoxLayout:
        ribbon = QHBoxLayout()
        ribbon.setSpacing(12)

        cards = [
            ("total_clients", "TOTAL CLIENTS", "Registered in Directory", "#1E293B"),
            ("active_clients", "ACTIVE ACCOUNTS", "With Billed Invoices", "#2563EB"),
            ("total_receivables", "TOTAL RECEIVABLES", "Outstanding Across Accounts", "#E11D48"),
            ("total_settled", "SETTLED ACCOUNTS", "Zero Balance Due", "#059669"),
        ]

        self.kpi_labels = {}
        for key, title, sub, accent in cards:
            c = QFrame()
            c.setObjectName("reportKpiCard")
            c.setStyleSheet(
                f"QFrame#reportKpiCard {{ background: #FFFFFF; border: 1px solid #E2E8F0; "
                f"border-top: 3.5px solid {accent}; border-radius: 10px; padding: 8px 14px; }}"
                f"QFrame#reportKpiCard:hover {{ border-color: {accent}; background: #F8FAFC; }}"
            )
            lay = QVBoxLayout(c)
            lay.setContentsMargins(2, 2, 2, 2)
            lay.setSpacing(2)

            lbl_t = QLabel(title)
            lbl_t.setStyleSheet("font-size: 10px; font-weight: 700; color: #64748B; letter-spacing: 0.5px;")

            lbl_v = QLabel("—")
            lbl_v.setStyleSheet(f"font-size: 18px; font-weight: 800; color: {accent}; letter-spacing: -0.2px;")

            lbl_s = QLabel(sub)
            lbl_s.setStyleSheet("font-size: 11px; font-weight: 500; color: #94A3B8;")

            lay.addWidget(lbl_t)
            lay.addWidget(lbl_v)
            lay.addWidget(lbl_s)

            ribbon.addWidget(c, 1)
            self.kpi_labels[key] = (lbl_v, lbl_s)

        return ribbon

    # -------------------------------------------------------------------------
    # 2. Directory Toolbar & Segmented Filter Bar
    # -------------------------------------------------------------------------
    def _build_toolbar(self) -> QVBoxLayout:
        vbox = QVBoxLayout()
        vbox.setSpacing(10)

        row = QHBoxLayout()
        row.setSpacing(10)

        # Search Bar
        self.search = QLineEdit()
        self.search.setPlaceholderText("🔍 Search clients by name, mobile, GSTIN, city...")
        self.search.setMinimumWidth(340)
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._on_search_changed)
        row.addWidget(self.search)

        row.addStretch(1)

        # Action Buttons
        btn_add = QPushButton(" + Add Customer ")
        btn_add.setStyleSheet(
            "QPushButton { background: #2563EB; color: #FFFFFF; font-weight: 700; "
            "border: none; border-radius: 7px; padding: 7px 16px; font-size: 12px; } "
            "QPushButton:hover { background: #1D4ED8; }"
        )
        btn_add.clicked.connect(self._add_customer)
        row.addWidget(btn_add)

        btn_export = QPushButton(" 📥 Export CSV ")
        btn_export.setStyleSheet(
            "QPushButton { background: #F1F5F9; color: #1E293B; font-weight: 600; "
            "border: 1px solid #CBD5E1; border-radius: 7px; padding: 7px 13px; font-size: 12px; } "
            "QPushButton:hover { background: #E2E8F0; }"
        )
        btn_export.clicked.connect(self._export_csv)
        row.addWidget(btn_export)

        btn_refresh = QPushButton(" 🔄 Refresh ")
        btn_refresh.setStyleSheet(
            "QPushButton { background: #F8FAFC; color: #475569; font-weight: 600; "
            "border: 1px solid #E2E8F0; border-radius: 7px; padding: 7px 12px; font-size: 12px; } "
            "QPushButton:hover { background: #F1F5F9; color: #0F172A; }"
        )
        btn_refresh.clicked.connect(self.refresh)
        row.addWidget(btn_refresh)

        vbox.addLayout(row)

        # Filter Pills Strip
        pill_row = QHBoxLayout()
        pill_row.setSpacing(8)

        self.pill_btns = {}
        filters = [
            ("ALL", "All Clients", "#1E293B"),
            ("DUE", "With Balance Due", "#DC2626"),
            ("SETTLED", "Fully Settled", "#059669"),
            ("B2B", "GST Registered (B2B)", "#2563EB"),
        ]
        for fkey, flabel, faccent in filters:
            btn = QPushButton(flabel)
            btn.setCheckable(True)
            btn.setChecked(fkey == "ALL")
            btn.clicked.connect(lambda checked=False, k=fkey: self._set_filter(k))
            pill_row.addWidget(btn)
            self.pill_btns[fkey] = (btn, flabel, faccent)

        pill_row.addStretch(1)
        self._update_pill_styles()
        vbox.addLayout(pill_row)

        return vbox

    def _update_pill_styles(self):
        for fkey, (btn, base_label, accent) in self.pill_btns.items():
            is_active = (fkey == self._active_filter)
            if is_active:
                btn.setStyleSheet(
                    f"QPushButton {{ background: {accent}; color: #FFFFFF; font-weight: 700; "
                    f"border: none; border-radius: 14px; padding: 5px 14px; font-size: 11px; }}"
                )
            else:
                btn.setStyleSheet(
                    "QPushButton { background: #F1F5F9; color: #475569; font-weight: 600; "
                    "border: 1px solid #E2E8F0; border-radius: 14px; padding: 5px 14px; font-size: 11px; } "
                    "QPushButton:hover { background: #E2E8F0; color: #0F172A; }"
                )

    def _set_filter(self, filter_key: str):
        self._active_filter = filter_key
        for k, (btn, _, _) in self.pill_btns.items():
            btn.setChecked(k == filter_key)
        self._update_pill_styles()
        self._render_directory_table()

    # -------------------------------------------------------------------------
    # 3. Left Panel: Customer Directory Table
    # -------------------------------------------------------------------------
    def _build_directory_panel(self) -> QWidget:
        container = QFrame()
        container.setObjectName("customerDetail")
        lay = QVBoxLayout(container)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(10)

        # Header title
        lbl_dir = QLabel("Client Directory")
        lbl_dir.setStyleSheet("font-size: 14px; font-weight: 800; color: #0F172A;")
        lay.addWidget(lbl_dir)

        # 5 Columns: Client & City, Mobile, GSTIN / Type, Total Billed, Balance Due
        headers = ["Customer & City", "Contact Mobile", "GSTIN / Category", "Total Billed (₹)", "Balance Due (₹)"]
        self.table = QTableWidget(0, len(headers))
        self.table.setHorizontalHeaderLabels(headers)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setAlternatingRowColors(True)

        hh = self.table.horizontalHeader()
        hh.setStretchLastSection(False)
        hh.setSectionResizeMode(0, QHeaderView.Stretch)      # Customer Name & City
        hh.setSectionResizeMode(1, QHeaderView.Interactive)  # Mobile
        hh.setSectionResizeMode(2, QHeaderView.Interactive)  # GSTIN
        hh.setSectionResizeMode(3, QHeaderView.Interactive)  # Total Billed
        hh.setSectionResizeMode(4, QHeaderView.Interactive)  # Balance Due

        self.table.setColumnWidth(1, 115)
        self.table.setColumnWidth(2, 135)
        self.table.setColumnWidth(3, 115)
        self.table.setColumnWidth(4, 125)

        self.table.itemSelectionChanged.connect(self._selection_changed)
        lay.addWidget(self.table, 1)

        self.lbl_table_footer = QLabel("Showing 0 clients")
        self.lbl_table_footer.setStyleSheet("font-size: 11px; font-weight: 600; color: #64748B;")
        lay.addWidget(self.lbl_table_footer)

        return container

    # -------------------------------------------------------------------------
    # 4. Right Panel: Executive Customer Dossier Card
    # -------------------------------------------------------------------------
    def _build_dossier_panel(self) -> QWidget:
        self.dossier_container = QFrame()
        self.dossier_container.setObjectName("customerDetail")
        self.dossier_layout = QVBoxLayout(self.dossier_container)
        self.dossier_layout.setContentsMargins(16, 16, 16, 16)
        self.dossier_layout.setSpacing(12)

        # Dossier Header: Avatar + Name + Subtitle
        header_row = QHBoxLayout()
        header_row.setSpacing(12)

        self.avatar_frame = QFrame()
        self.avatar_frame.setObjectName("customerAvatar")
        av_lay = QVBoxLayout(self.avatar_frame)
        av_lay.setContentsMargins(0, 0, 0, 0)
        self.avatar_text = QLabel("CL")
        self.avatar_text.setObjectName("customerAvatarText")
        self.avatar_text.setAlignment(Qt.AlignCenter)
        av_lay.addWidget(self.avatar_text)
        header_row.addWidget(self.avatar_frame)

        name_box = QVBoxLayout()
        name_box.setSpacing(2)
        self.d_name = QLabel("Select a Customer")
        self.d_name.setObjectName("customerDetailName")
        self.d_contact_strip = QLabel("Contact details and account ledger will appear here.")
        self.d_contact_strip.setStyleSheet("font-size: 11px; color: #64748B;")
        self.d_contact_strip.setWordWrap(True)
        name_box.addWidget(self.d_name)
        name_box.addWidget(self.d_contact_strip)
        header_row.addLayout(name_box, 1)

        self.d_b2b_badge = QLabel("B2B")
        self.d_b2b_badge.setStyleSheet(
            "background: #ECFDF5; color: #065F46; border: 1px solid #A7F3D0; "
            "border-radius: 4px; font-weight: 700; font-size: 10px; padding: 3px 8px;"
        )
        self.d_b2b_badge.setVisible(False)
        header_row.addWidget(self.d_b2b_badge)

        self.dossier_layout.addLayout(header_row)

        # Address & GST info row
        self.d_address_info = QLabel("")
        self.d_address_info.setStyleSheet("font-size: 11px; color: #475569; background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; padding: 6px 10px;")
        self.d_address_info.setWordWrap(True)
        self.dossier_layout.addWidget(self.d_address_info)

        # 3 Mini Financial KPI Cards
        mini_kpi_row = QHBoxLayout()
        mini_kpi_row.setSpacing(8)

        self.kpi_invoiced_frame, self.d_invoiced_val = self._create_mini_kpi("TOTAL INVOICED", "#0F172A")
        self.kpi_paid_frame, self.d_paid_val = self._create_mini_kpi("TOTAL COLLECTED", "#059669")
        self.kpi_due_frame, self.d_due_val = self._create_mini_kpi("OUTSTANDING DUE", "#DC2626")

        mini_kpi_row.addWidget(self.kpi_invoiced_frame, 1)
        mini_kpi_row.addWidget(self.kpi_paid_frame, 1)
        mini_kpi_row.addWidget(self.kpi_due_frame, 1)
        self.dossier_layout.addLayout(mini_kpi_row)

        # Action Toolbar Row
        action_row = QHBoxLayout()
        action_row.setSpacing(6)

        self.btn_new_inv = QPushButton(" + New Invoice ")
        self.btn_new_inv.setStyleSheet(
            "QPushButton { background: #059669; color: #FFFFFF; font-weight: 700; "
            "border: none; border-radius: 6px; padding: 6px 11px; font-size: 11px; } "
            "QPushButton:hover { background: #047857; }"
        )
        self.btn_new_inv.clicked.connect(self._new_invoice_for_customer)

        self.btn_wa = QPushButton(" 💬 Remind ")
        self.btn_wa.setStyleSheet(
            "QPushButton { background: #16A34A; color: #FFFFFF; font-weight: 700; "
            "border: none; border-radius: 6px; padding: 6px 11px; font-size: 11px; } "
            "QPushButton:hover { background: #15803D; }"
        )
        self.btn_wa.clicked.connect(self._send_whatsapp_reminder)

        self.btn_statement = QPushButton(" 📄 Statement PDF ")
        self.btn_statement.setStyleSheet(
            "QPushButton { background: #2563EB; color: #FFFFFF; font-weight: 700; "
            "border: none; border-radius: 6px; padding: 6px 11px; font-size: 11px; } "
            "QPushButton:hover { background: #1D4ED8; }"
        )
        self.btn_statement.clicked.connect(self._download_statement_pdf)

        self.btn_edit = QPushButton(" ✎ Edit ")
        self.btn_edit.setStyleSheet(
            "QPushButton { background: #F1F5F9; color: #1E293B; font-weight: 600; "
            "border: 1px solid #CBD5E1; border-radius: 6px; padding: 6px 10px; font-size: 11px; } "
            "QPushButton:hover { background: #E2E8F0; }"
        )
        self.btn_edit.clicked.connect(self._edit_customer)

        self.btn_del = QPushButton(" 🗑 ")
        self.btn_del.setStyleSheet(
            "QPushButton { background: #FEF2F2; color: #DC2626; font-weight: 700; "
            "border: 1px solid #FECACA; border-radius: 6px; padding: 6px 10px; font-size: 11px; } "
            "QPushButton:hover { background: #FEE2E2; }"
        )
        self.btn_del.clicked.connect(self._delete_customer)

        action_row.addWidget(self.btn_new_inv)
        action_row.addWidget(self.btn_wa)
        action_row.addWidget(self.btn_statement)
        action_row.addWidget(self.btn_edit)
        action_row.addWidget(self.btn_del)
        action_row.addStretch(1)
        self.dossier_layout.addLayout(action_row)

        # Tabbed History (Invoices vs Payments)
        self.detail_tabs = QTabWidget()
        self.detail_tabs.setObjectName("reportTabs")
        self.detail_tabs.tabBar().setObjectName("reportTabBar")

        # Invoices History Tab
        inv_w = QWidget()
        inv_lay = QVBoxLayout(inv_w)
        inv_lay.setContentsMargins(4, 8, 4, 4)
        inv_lay.setSpacing(6)

        self.hist_inv = QTableWidget(0, 5)
        self.hist_inv.setHorizontalHeaderLabels(["Invoice #", "Date", "Status", "Total (₹)", "Balance (₹)"])
        self.hist_inv.setEditTriggers(QTableWidget.NoEditTriggers)
        self.hist_inv.setSelectionBehavior(QTableWidget.SelectRows)
        self.hist_inv.verticalHeader().setVisible(False)
        self.hist_inv.verticalHeader().setDefaultSectionSize(36)
        self.hist_inv.setAlternatingRowColors(True)

        ihh = self.hist_inv.horizontalHeader()
        ihh.setSectionResizeMode(0, QHeaderView.Stretch)      # Invoice #
        ihh.setSectionResizeMode(1, QHeaderView.Interactive)  # Date
        ihh.setSectionResizeMode(2, QHeaderView.Interactive)  # Status
        ihh.setSectionResizeMode(3, QHeaderView.Interactive)  # Total
        ihh.setSectionResizeMode(4, QHeaderView.Interactive)  # Balance

        self.hist_inv.setColumnWidth(1, 84)
        self.hist_inv.setColumnWidth(2, 74)
        self.hist_inv.setColumnWidth(3, 110)
        self.hist_inv.setColumnWidth(4, 110)



        inv_lay.addWidget(self.hist_inv)
        self.detail_tabs.addTab(inv_w, " Invoices History ")

        # Payments History Tab
        pay_w = QWidget()
        pay_lay = QVBoxLayout(pay_w)
        pay_lay.setContentsMargins(4, 8, 4, 4)
        pay_lay.setSpacing(6)

        self.hist_pay = QTableWidget(0, 4)
        self.hist_pay.setHorizontalHeaderLabels(["Date", "Invoice #", "Mode", "Amount (₹)"])
        self.hist_pay.setEditTriggers(QTableWidget.NoEditTriggers)
        self.hist_pay.setSelectionBehavior(QTableWidget.SelectRows)
        self.hist_pay.verticalHeader().setVisible(False)
        self.hist_pay.verticalHeader().setDefaultSectionSize(36)
        self.hist_pay.setAlternatingRowColors(True)

        phh = self.hist_pay.horizontalHeader()
        phh.setSectionResizeMode(0, QHeaderView.Interactive)  # Date
        phh.setSectionResizeMode(1, QHeaderView.Stretch)      # Invoice #
        phh.setSectionResizeMode(2, QHeaderView.Interactive)  # Mode
        phh.setSectionResizeMode(3, QHeaderView.Interactive)  # Amount

        self.hist_pay.setColumnWidth(0, 85)
        self.hist_pay.setColumnWidth(2, 90)
        self.hist_pay.setColumnWidth(3, 110)

        pay_lay.addWidget(self.hist_pay)

        self.detail_tabs.addTab(pay_w, " Payments Ledger ")

        self.dossier_layout.addWidget(self.detail_tabs, 1)

        # Initially disable action buttons until a customer is chosen
        self._set_dossier_enabled(False)

        return self.dossier_container

    def _create_mini_kpi(self, title: str, accent: str) -> tuple[QFrame, QLabel]:
        f = QFrame()
        f.setObjectName("customerKpiMini")
        lay = QVBoxLayout(f)
        lay.setContentsMargins(6, 4, 6, 4)
        lay.setSpacing(1)

        lbl_t = QLabel(title)
        lbl_t.setObjectName("customerKpiMiniLbl")
        lbl_v = QLabel("—")
        lbl_v.setObjectName("customerKpiMiniVal")
        lbl_v.setStyleSheet(f"color: {accent};")

        lay.addWidget(lbl_t)
        lay.addWidget(lbl_v)
        return f, lbl_v

    def _set_dossier_enabled(self, enabled: bool):
        self.btn_new_inv.setEnabled(enabled)
        self.btn_wa.setEnabled(enabled)
        self.btn_statement.setEnabled(enabled)
        self.btn_edit.setEnabled(enabled)
        self.btn_del.setEnabled(enabled)

    # -------------------------------------------------------------------------
    # Data Loading & Lifecycle
    # -------------------------------------------------------------------------
    def on_first_show(self):
        self.refresh()

    def refresh(self):
        # 1. Load directory KPI overview
        kpi_data = customer_service.customers_kpi_overview()
        total_c = kpi_data.get("total_customers", 0)
        active_c = kpi_data.get("active_clients", 0)
        receivables = kpi_data.get("total_receivables", 0)

        # 2. Batch-load all customers with their financials
        self._customers_cache = customer_service.get_customers_with_summary(self.search.text().strip())

        settled_count = sum(1 for c in self._customers_cache if c["is_settled"])
        due_count = len(self._customers_cache) - settled_count
        b2b_count = sum(1 for c in self._customers_cache if c["has_gstin"])

        # Update KPI Ribbon
        self.kpi_labels["total_clients"][0].setText(str(total_c))
        self.kpi_labels["total_clients"][1].setText(f"{total_c} Registered in Directory")

        self.kpi_labels["active_clients"][0].setText(str(active_c))
        self.kpi_labels["active_clients"][1].setText(f"{active_c} Accounts with Orders")

        self.kpi_labels["total_receivables"][0].setText(_money(receivables))
        self.kpi_labels["total_receivables"][1].setText(f"{due_count} Clients with Pending Due")

        self.kpi_labels["total_settled"][0].setText(str(settled_count))
        self.kpi_labels["total_settled"][1].setText(f"{settled_count} Fully Cleared (100%)")

        # Update Filter Pill Counts
        self.pill_btns["ALL"][0].setText(f"All Clients ({len(self._customers_cache)})")
        self.pill_btns["DUE"][0].setText(f"With Balance Due ({due_count})")
        self.pill_btns["SETTLED"][0].setText(f"Fully Settled ({settled_count})")
        self.pill_btns["B2B"][0].setText(f"GST Registered ({b2b_count})")

        # Render Directory Table
        self._render_directory_table()

    def _on_search_changed(self, text: str):
        self._customers_cache = customer_service.get_customers_with_summary(text.strip())
        self._render_directory_table()

    def _render_directory_table(self):
        f = self._active_filter
        filtered = []
        for c in self._customers_cache:
            if f == "DUE" and c["is_settled"]:
                continue
            if f == "SETTLED" and not c["is_settled"]:
                continue
            if f == "B2B" and not c["has_gstin"]:
                continue
            filtered.append(c)

        self.table.setRowCount(0)
        for r_idx, c in enumerate(filtered):
            self.table.insertRow(r_idx)

            # Col 0: Name & City
            name_text = c["name"]
            sub_text = f"  ({c['city']})" if c["city"] != "-" else ""
            it0 = QTableWidgetItem(f"{name_text}{sub_text}")
            it0.setFont(QFont("Segoe UI", 9, QFont.Bold))
            it0.setForeground(QColor("#0F172A"))
            it0.setData(Qt.UserRole, c["id"])
            self.table.setItem(r_idx, 0, it0)

            # Col 1: Contact Mobile
            it1 = QTableWidgetItem(c["mobile"])
            it1.setForeground(QColor("#475569"))
            self.table.setItem(r_idx, 1, it1)

            # Col 2: GSTIN / Category Pill
            self.table.setItem(r_idx, 2, QTableWidgetItem(""))
            cat_pill = QLabel(c["gstin"] if c["has_gstin"] else "B2C Consumer")
            cat_pill.setAlignment(Qt.AlignCenter)
            if c["has_gstin"]:
                cat_pill.setStyleSheet(
                    "background: #ECFDF5; color: #065F46; border: 1px solid #A7F3D0; "
                    "border-radius: 4px; font-weight: 700; font-family: Consolas; font-size: 10px; padding: 2px 6px;"
                )
            else:
                cat_pill.setStyleSheet(
                    "background: #F1F5F9; color: #64748B; border: 1px solid #CBD5E1; "
                    "border-radius: 4px; font-weight: 600; font-size: 10px; padding: 2px 6px;"
                )
            cw = QWidget()
            cw.setStyleSheet("background: transparent;")
            clay = QHBoxLayout(cw)
            clay.setContentsMargins(4, 8, 4, 8)
            clay.setAlignment(Qt.AlignCenter)
            clay.addWidget(cat_pill)
            self.table.setCellWidget(r_idx, 2, cw)

            # Col 3: Total Billed (₹)
            it3 = QTableWidgetItem(_money(c["total_invoiced"]))
            it3.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it3.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
            it3.setForeground(QColor("#0F172A"))
            self.table.setItem(r_idx, 3, it3)

            # Col 4: Balance Due (₹) & Status
            due = c["outstanding"]
            self.table.setItem(r_idx, 4, QTableWidgetItem(""))
            due_pill = QLabel(_money(due) if due > 0.01 else "Settled")
            due_pill.setAlignment(Qt.AlignCenter)
            if due > 0.01:
                due_pill.setStyleSheet(
                    "background: #FEF2F2; color: #DC2626; border: 1px solid #FECACA; "
                    "border-radius: 4px; font-weight: 800; font-size: 10px; padding: 2px 6px;"
                )
            else:
                due_pill.setStyleSheet(
                    "background: #ECFDF5; color: #059669; border: 1px solid #A7F3D0; "
                    "border-radius: 4px; font-weight: 700; font-size: 10px; padding: 2px 6px;"
                )
            dw = QWidget()
            dw.setStyleSheet("background: transparent;")
            dlay = QHBoxLayout(dw)
            dlay.setContentsMargins(4, 8, 4, 8)
            dlay.setAlignment(Qt.AlignCenter)
            dlay.addWidget(due_pill)
            self.table.setCellWidget(r_idx, 4, dw)

        tot_shown_due = sum(c["outstanding"] for c in filtered)
        self.lbl_table_footer.setText(
            f"Showing {len(filtered)} of {len(self._customers_cache)} clients  •  "
            f"Cumulative Balance Across Shown: {_money(tot_shown_due)}"
        )

        # Re-select previous customer or select first row
        if filtered:
            target_row = 0
            if self._current_customer_id:
                for idx, c in enumerate(filtered):
                    if c["id"] == self._current_customer_id:
                        target_row = idx
                        break
            self.table.selectRow(target_row)
        else:
            self._clear_dossier()

    def _selection_changed(self):
        items = self.table.selectedItems()
        if not items:
            return
        row = items[0].row()
        item0 = self.table.item(row, 0)
        if not item0:
            return
        cid = item0.data(Qt.UserRole)
        if cid is not None:
            self._current_customer_id = cid
            self._show_detail(cid)

    def _clear_dossier(self):
        self._current_customer_id = None
        self.avatar_text.setText("—")
        self.d_name.setText("No Client Selected")
        self.d_contact_strip.setText("Select a customer from the directory list.")
        self.d_address_info.setText("")
        self.d_b2b_badge.setVisible(False)
        self.d_invoiced_val.setText("—")
        self.d_paid_val.setText("—")
        self.d_due_val.setText("—")
        self.hist_inv.setRowCount(0)
        self.hist_pay.setRowCount(0)
        self._set_dossier_enabled(False)

    def _show_detail(self, cid: int):
        c = customer_service.get_customer(cid)
        if not c:
            self._clear_dossier()
            return

        self._set_dossier_enabled(True)

        # Initials Avatar
        name_parts = (c.name or "Client").strip().split()
        initials = (name_parts[0][0] + (name_parts[1][0] if len(name_parts) > 1 else "")).upper()
        self.avatar_text.setText(initials[:2])

        self.d_name.setText(c.name or "Unnamed Client")

        # Contact strip
        contacts = []
        if c.mobile:
            contacts.append(f"📞 {c.mobile}")
        if c.email:
            contacts.append(f"✉️ {c.email}")
        if c.city:
            contacts.append(f"📍 {c.city}")
        self.d_contact_strip.setText("   •   ".join(contacts) or "No direct contact info")

        # GST badge
        if c.gstin and c.gstin.strip():
            self.d_b2b_badge.setText(f"GSTIN: {c.gstin.strip()}")
            self.d_b2b_badge.setVisible(True)
        else:
            self.d_b2b_badge.setVisible(False)

        # Address box
        addr_parts = [p for p in (c.address, c.city, c.state) if p and p.strip()]
        if addr_parts or (c.notes and c.notes.strip()):
            addr_text = "  |  ".join(addr_parts)
            if c.notes and c.notes.strip():
                addr_text += f"\nNote: {c.notes.strip()}"
            self.d_address_info.setText(addr_text)
            self.d_address_info.setVisible(True)
        else:
            self.d_address_info.setVisible(False)

        # Financial Totals
        totals = customer_service.customer_totals(cid)
        inv_f = float(totals.get("total_invoiced", 0))
        paid_f = float(totals.get("total_paid", 0))
        due_f = float(totals.get("outstanding", 0))

        self.d_invoiced_val.setText(_money(inv_f))
        self.d_paid_val.setText(_money(paid_f))
        self.d_due_val.setText(_money(due_f))
        if due_f > 0.01:
            self.d_due_val.setStyleSheet("color: #DC2626;")
        else:
            self.d_due_val.setStyleSheet("color: #059669;")

        # Invoices History Tab
        invs = customer_service.customer_invoices(cid)
        self.detail_tabs.setTabText(0, f" Invoices ({len(invs)}) ")
        self.hist_inv.setRowCount(0)
        for inv in invs:
            r = self.hist_inv.rowCount()
            self.hist_inv.insertRow(r)

            # Col 0: Invoice #
            it0 = QTableWidgetItem(inv.invoice_number)
            it0.setFont(QFont("Segoe UI", 9, QFont.Bold))
            it0.setForeground(QColor("#0F172A"))
            self.hist_inv.setItem(r, 0, it0)

            # Col 1: Date
            d_str = inv.invoice_date.strftime("%d-%b-%y") if inv.invoice_date else "-"
            it1 = QTableWidgetItem(d_str)
            it1.setTextAlignment(Qt.AlignCenter)
            it1.setForeground(QColor("#475569"))
            self.hist_inv.setItem(r, 1, it1)

            # Col 2: Status Pill Widget
            paid_inv = sum(float(p.amount or 0) for p in (inv.payments or []))
            bal_inv = max(float(inv.grand_total or 0) - paid_inv, 0.0)

            from app.services.invoice_service import compute_status
            st_text = compute_status(inv.grand_total, paid_inv, inv.status, inv.due_date)

            self.hist_inv.setItem(r, 2, QTableWidgetItem(""))
            pill = QLabel(st_text)
            pill.setAlignment(Qt.AlignCenter)
            if st_text == "PAID":
                pill.setStyleSheet("background: #ECFDF5; color: #065F46; border: 1px solid #A7F3D0; border-radius: 4px; font-weight: 700; font-size: 9px; padding: 2px 4px;")
            elif st_text == "PARTIALLY PAID":
                pill.setStyleSheet("background: #FEF3C7; color: #92400E; border: 1px solid #FDE68A; border-radius: 4px; font-weight: 700; font-size: 9px; padding: 2px 4px;")
            elif st_text == "OVERDUE":
                pill.setStyleSheet("background: #FEF2F2; color: #991B1B; border: 1px solid #FECACA; border-radius: 4px; font-weight: 700; font-size: 9px; padding: 2px 4px;")
            else:
                pill.setStyleSheet("background: #F1F5F9; color: #475569; border: 1px solid #CBD5E1; border-radius: 4px; font-weight: 600; font-size: 9px; padding: 2px 4px;")

            pw = QWidget()
            pw.setStyleSheet("background: transparent;")
            play = QHBoxLayout(pw)
            play.setContentsMargins(2, 4, 2, 4)
            play.setAlignment(Qt.AlignCenter)
            play.addWidget(pill)
            self.hist_inv.setCellWidget(r, 2, pw)

            # Col 3: Total (₹)
            it3 = QTableWidgetItem(_money(inv.grand_total))
            it3.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it3.setFont(QFont("Segoe UI", 9, QFont.DemiBold))
            it3.setForeground(QColor("#0F172A"))
            self.hist_inv.setItem(r, 3, it3)

            # Col 4: Balance (₹)
            it4 = QTableWidgetItem(_money(bal_inv))
            it4.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it4.setFont(QFont("Segoe UI", 9, QFont.Bold))
            it4.setForeground(QColor("#DC2626" if bal_inv > 0.01 else "#059669"))
            self.hist_inv.setItem(r, 4, it4)

        # Payments History Tab
        pays = customer_service.customer_payments(cid)
        self.detail_tabs.setTabText(1, f" Payments ({len(pays)}) ")
        self.hist_pay.setRowCount(0)
        for p in pays:
            r = self.hist_pay.rowCount()
            self.hist_pay.insertRow(r)

            d_str = p.date.strftime("%d-%b-%y") if p.date else "-"
            it0 = QTableWidgetItem(d_str)
            it0.setTextAlignment(Qt.AlignCenter)
            it0.setForeground(QColor("#475569"))
            self.hist_pay.setItem(r, 0, it0)

            inv_no = p.invoice.invoice_number if p.invoice else "-"
            it1 = QTableWidgetItem(inv_no)
            it1.setFont(QFont("Segoe UI", 9, QFont.Bold))
            it1.setForeground(QColor("#0F172A"))
            self.hist_pay.setItem(r, 1, it1)

            it2 = QTableWidgetItem(p.mode or "Cash")
            it2.setTextAlignment(Qt.AlignCenter)
            it2.setForeground(QColor("#475569"))
            self.hist_pay.setItem(r, 2, it2)

            it3 = QTableWidgetItem(_money(p.amount))
            it3.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            it3.setFont(QFont("Segoe UI", 9, QFont.Bold))
            it3.setForeground(QColor("#059669"))
            self.hist_pay.setItem(r, 3, it3)

    # -------------------------------------------------------------------------
    # Actions Hub
    # -------------------------------------------------------------------------
    def _add_customer(self):
        dlg = CustomerDialog(self, None)
        if dlg.exec():
            data = dlg.result_data()
            try:
                c = customer_service.add_customer(data)
                show_toast(self, f"Customer '{c.name}' added.", "success")
                self.refresh()
                if c.id:
                    self._current_customer_id = c.id
                    self._show_detail(c.id)
            except Exception as e:  # noqa: BLE001
                show_toast(self, f"Error: {e}", "error")

    def _edit_customer(self):
        cid = self._current_customer_id
        if not cid:
            show_toast(self, "Select a customer first.", "error")
            return
        c = customer_service.get_customer(cid)
        dlg = CustomerDialog(self, c)
        if dlg.exec():
            try:
                customer_service.update_customer(cid, dlg.result_data())
                show_toast(self, "Customer updated successfully.", "success")
                self.refresh()
                self._show_detail(cid)
            except Exception as e:  # noqa: BLE001
                show_toast(self, f"Error: {e}", "error")

    def _delete_customer(self):
        cid = self._current_customer_id
        if not cid:
            show_toast(self, "Select a customer first.", "error")
            return
        totals = customer_service.customer_totals(cid)
        inv_count = totals.get("invoice_count", 0)
        outstanding = totals.get("outstanding", 0)

        warning_parts = [f"Delete customer '{self.d_name.text()}'?"]
        if inv_count:
            warning_parts.append(f"\n\nThis will also delete {inv_count} associated invoice(s).")
        if outstanding > 0:
            warning_parts.append(f"\nOutstanding balance of \u20B9 {outstanding:,.2f} will be erased.")
        warning_parts.append("\n\nThis action cannot be undone.")

        if QMessageBox.question(
            self, "Delete Customer Account",
            "".join(warning_parts),
            QMessageBox.Yes | QMessageBox.No
        ) == QMessageBox.Yes:
            try:
                customer_service.delete_customer(cid)
                show_toast(self, "Customer account removed.", "success")
                self._current_customer_id = None
                self.refresh()
            except Exception as e:  # noqa: BLE001
                show_toast(self, f"Error: {e}", "error")

    def _new_invoice_for_customer(self):
        cid = self._current_customer_id
        if not cid:
            show_toast(self, "Select a customer first.", "error")
            return
        if self.main_window is not None:
            inv_page = self.main_window.pages.get("invoices")
            if inv_page:
                inv_page.start_new_invoice(customer_id=cid)
                self.main_window.show_page("invoices")

    def _download_statement_pdf(self):
        cid = self._current_customer_id
        if not cid:
            show_toast(self, "Select a customer first.", "error")
            return
        c = customer_service.get_customer(cid)
        if not c:
            return

        clean_name = "".join(ch for ch in c.name if ch.isalnum() or ch in (" ", "_")).replace(" ", "_")
        default_name = f"Statement_{clean_name}_{datetime.now(tz=timezone.utc).strftime('%Y%m%d')}.pdf"
        dest, _ = QFileDialog.getSaveFileName(self, "Save Customer Statement PDF", default_name, "PDF Files (*.pdf)")
        if not dest:
            return
        try:
            save_customer_statement_pdf(cid, Path(dest))
            show_toast(self, f"Statement PDF saved to {os.path.basename(dest)}", "success")
        except Exception as e:  # noqa: BLE001
            show_toast(self, f"Could not generate statement: {e}", "error")

    def _send_whatsapp_reminder(self):
        cid = self._current_customer_id
        if not cid:
            show_toast(self, "Select a customer first.", "error")
            return
        c = customer_service.get_customer(cid)
        if not c or not c.mobile:
            QMessageBox.warning(self, "WhatsApp Follow-up", "Customer has no mobile number saved.")
            return

        profile = business_service.get_profile()
        biz_name = profile.business_name if profile else "Our Store"
        totals = customer_service.customer_totals(cid)
        outstanding = float(totals.get("outstanding", 0) or 0)

        if outstanding <= 0:
            show_toast(self, "Customer has no outstanding balance due (100% Settled).", "info")
            return

        mob = "".join(filter(str.isdigit, c.mobile))
        if len(mob) == 10:
            mob = f"91{mob}"

        msg = (
            f"Dear {c.name},\n\n"
            f"Greetings from *{biz_name}*!\n\n"
            f"This is a gentle reminder regarding your outstanding balance of *₹ {outstanding:,.2f}*.\n"
        )
        if profile and profile.upi_id:
            msg += f"You can pay conveniently via UPI: *{profile.upi_id}*\n"
        if profile and profile.bank_name:
            msg += f"Bank Details: *{profile.bank_name}* | A/C: *{profile.account_number}* | IFSC: *{profile.ifsc_code}*\n"
        msg += "\nPlease let us know once transferred or if you require an itemized statement.\nThank you for choosing us!"

        url = f"https://wa.me/{mob}?text={quote(msg)}"
        QDesktopServices.openUrl(QUrl(url))

    def _export_csv(self):
        """Export customer directory with complete financials to CSV."""
        if not self._customers_cache:
            show_toast(self, "No customer accounts to export.", "warning")
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Export Customer Directory",
            os.path.expanduser("~/Customer_Directory_Ledger.csv"),
            "CSV Files (*.csv)",
        )
        if not path:
            return
        if not path.lower().endswith(".csv"):
            path += ".csv"

        try:
            headers = [
                "Customer ID", "Customer Name", "Contact Mobile", "Email Address",
                "City", "State", "GSTIN", "Invoices Count",
                "Total Billed (INR)", "Total Collected (INR)", "Outstanding Balance (INR)",
                "Settlement Status"
            ]
            export_rows = []
            for c in self._customers_cache:
                export_rows.append([
                    c["id"],
                    c["name"],
                    c["mobile"],
                    c["email"],
                    c["city"],
                    c["state"],
                    c["gstin"],
                    c["invoice_count"],
                    f"{c['total_invoiced']:.2f}",
                    f"{c['total_paid']:.2f}",
                    f"{c['outstanding']:.2f}",
                    "Settled" if c["is_settled"] else "Pending Due",
                ])

            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(headers)
                writer.writerows(export_rows)

            show_toast(self, f"Exported {len(export_rows)} customers to {os.path.basename(path)}", "success")
        except Exception as e:  # noqa: BLE001
            show_toast(self, f"Export failed: {e}", "error")
