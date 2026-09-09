"""Invoices page: list/search invoices, manage payments, and launch the editor.

Features:
- Financial KPI summary cards (Total Invoices, Billed, Collected, Outstanding).
- Status filter pills with real-time counts (All, Unpaid, Partially Paid, Paid, Overdue, Draft).
- Debounced search across invoice number, customer name, and mobile number.
- High-contrast table with 44px rows, clear column alignment, and formatted badges.
- One-click row actions: 📄 Preview PDF, 💬 WhatsApp Share, 💵 Record Payment, ✎ Edit, 🗑 Delete.
- CSV export for accountant/tax reporting.
"""
from __future__ import annotations

import csv
from datetime import datetime, timezone

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.services import invoice_service
from app.services.invoice_service import compute_status, get_invoice_status
from app.ui.pages.base_page import BasePage
from app.ui.pages.invoice_editor import InvoiceEditor
from app.ui.widgets.common import show_toast


def _money(v) -> str:
    return f"\u20B9 {float(v or 0):,.2f}"


class InvoicesPage(BasePage):
    def __init__(self, main_window=None, parent=None):
        super().__init__(main_window, parent)
        self.editor = None
        self._editor_parent = None
        self._active_status_filter = "All"
        self._filter_pills = {}
        self._build()

    def _build(self):
        self.outer = QVBoxLayout(self)
        self.outer.setContentsMargins(0, 0, 0, 0)
        self.outer.setSpacing(0)

        # injected editor container
        self.editor_slot = QVBoxLayout()
        self.outer.addLayout(self.editor_slot)

        self.list_view = QVBoxLayout()
        self.outer.addLayout(self.list_view)
        self._build_list()

    def _build_list(self):
        lv = self.list_view
        lv.setContentsMargins(28, 20, 28, 20)
        lv.setSpacing(14)

        # --- 1. Top Financial KPI Summary Strip ---
        kpi_bar = QHBoxLayout()
        kpi_bar.setSpacing(14)

        def _kpi_card(title: str, val_lbl: QLabel, accent: str) -> QFrame:
            card = QFrame()
            card.setObjectName("invoicesKpiCard")
            card.setStyleSheet(f"QFrame#invoicesKpiCard {{ border-left: 4px solid {accent}; }}")
            v = QVBoxLayout(card)
            v.setContentsMargins(14, 10, 14, 10)
            v.setSpacing(3)
            lbl = QLabel(title)
            lbl.setObjectName("invoicesKpiLabel")
            val_lbl.setObjectName("invoicesKpiValue")
            if accent == "#059669":
                val_lbl.setStyleSheet("color: #059669; font-size: 18px; font-weight: 800;")
            elif accent in ("#DC2626", "#D97706"):
                val_lbl.setStyleSheet("color: #DC2626; font-size: 18px; font-weight: 800;")
            else:
                val_lbl.setStyleSheet("color: #0F172A; font-size: 18px; font-weight: 800;")
            v.addWidget(lbl)
            v.addWidget(val_lbl)
            return card

        self.lbl_kpi_count = QLabel("0")
        self.lbl_kpi_billed = QLabel("\u20B9 0.00")
        self.lbl_kpi_paid = QLabel("\u20B9 0.00")
        self.lbl_kpi_due = QLabel("\u20B9 0.00")

        kpi_bar.addWidget(_kpi_card("TOTAL INVOICES", self.lbl_kpi_count, "#2563EB"))
        kpi_bar.addWidget(_kpi_card("TOTAL BILLED", self.lbl_kpi_billed, "#173560"))
        kpi_bar.addWidget(_kpi_card("TOTAL COLLECTED", self.lbl_kpi_paid, "#059669"))
        kpi_bar.addWidget(_kpi_card("OUTSTANDING DUE", self.lbl_kpi_due, "#DC2626"))
        lv.addLayout(kpi_bar)

        # --- 2. Filter Pills Bar ---
        pills_lay = QHBoxLayout()
        pills_lay.setSpacing(8)

        pills = [
            ("All", "All"),
            ("Unpaid", "UNPAID"),
            ("Partially Paid", "PARTIALLY PAID"),
            ("Paid", "PAID"),
            ("Overdue", "OVERDUE"),
            ("Draft", "Draft"),
        ]
        for label, key in pills:
            btn = QPushButton(label)
            btn.setObjectName("invoiceFilterPill")
            btn.setCursor(Qt.PointingHandCursor)
            btn.setProperty("active", "true" if key == "All" else "false")
            btn.clicked.connect(lambda _, k=key: self._set_filter(k))
            pills_lay.addWidget(btn)
            self._filter_pills[key] = btn

        pills_lay.addStretch(1)
        lv.addLayout(pills_lay)

        # --- 3. Search + Action Toolbar ---
        top = QHBoxLayout()
        top.setSpacing(10)
        self.search = QLineEdit()
        self.search.setObjectName("invoiceSearch")
        self.search.setPlaceholderText("\uD83D\uDD0D Search by invoice no, customer, mobile...")
        self.search.setFixedWidth(340)
        self.search.setClearButtonEnabled(True)

        # Debounce search timer
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(250)
        self._search_timer.timeout.connect(self._load)
        self.search.textChanged.connect(self._search)

        # Hidden or legacy compatibility combo box
        self.status_filter = QComboBox()
        self.status_filter.setObjectName("invoiceStatusFilter")
        self.status_filter.addItems(["All", "Saved", "Draft", "PAID", "PARTIALLY PAID", "UNPAID", "OVERDUE"])
        self.status_filter.setVisible(False)
        self.status_filter.currentTextChanged.connect(self._search)

        btn_export = QPushButton("\uD83D\uDCE5 Export CSV")
        btn_export.setObjectName("invoiceExportBtn")
        btn_export.setCursor(Qt.PointingHandCursor)
        btn_export.clicked.connect(self._export_csv)

        btn_new = QPushButton("+ New Invoice")
        btn_new.setObjectName("invoiceNewBtn")
        btn_new.setCursor(Qt.PointingHandCursor)
        btn_new.clicked.connect(self._new_invoice)

        top.addWidget(self.search)
        top.addWidget(self.status_filter)
        top.addStretch(1)
        top.addWidget(btn_export)
        top.addWidget(btn_new)
        lv.addLayout(top)

        # --- 4. Invoice Table (7 Columns) ---
        self.table = QTableWidget(0, 7)
        self.table.setObjectName("invoiceTable")
        self.table.setHorizontalHeaderLabels([
            "INVOICE NO", "CUSTOMER & MOBILE", "DATE & DUE", "STATUS", "AMOUNT", "BALANCE DUE", "ACTIONS"
        ])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(44)
        self.table.setAlternatingRowColors(True)

        hh = self.table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.Interactive)  # Invoice No
        hh.setSectionResizeMode(1, QHeaderView.Stretch)      # Customer
        hh.setSectionResizeMode(2, QHeaderView.Interactive)  # Date
        hh.setSectionResizeMode(3, QHeaderView.Interactive)  # Status
        hh.setSectionResizeMode(4, QHeaderView.Interactive)  # Amount
        hh.setSectionResizeMode(5, QHeaderView.Interactive)  # Due
        hh.setSectionResizeMode(6, QHeaderView.Interactive)  # Actions

        self.table.setColumnWidth(0, 190)
        self.table.setColumnWidth(2, 120)
        self.table.setColumnWidth(3, 135)
        self.table.setColumnWidth(4, 130)
        self.table.setColumnWidth(5, 130)
        self.table.setColumnWidth(6, 185)

        self.table.cellDoubleClicked.connect(lambda r, c: self._edit_row(r))
        self.table.itemSelectionChanged.connect(self._selection_changed)

        self.empty_label = QLabel("No invoices found. Click '+ New Invoice' to create one.")
        self.empty_label.setObjectName("invoiceEmptyTitle")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color: #64748B; font-size: 13px; font-weight: 600; padding: 40px;")
        self.empty_label.setVisible(False)

        lv.addWidget(self.table, 1)
        lv.addWidget(self.empty_label)

        # --- 5. Bottom Selection Actions Bar ---
        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions_label = QLabel("SELECTED ROW:")
        actions_label.setObjectName("invoiceActionsLabel")
        actions_label.setStyleSheet("color: #64748B; font-size: 11px; font-weight: 700; letter-spacing: 0.5px;")
        actions.addWidget(actions_label)

        self.btn_preview = QToolButton()
        self.btn_preview.setText("Preview PDF")
        self.btn_preview.setObjectName("invoiceToolBtn")
        self.btn_preview.setPopupMode(QToolButton.InstantPopup)
        self._preview_menu = QMenu(self.btn_preview)
        act_colour = self._preview_menu.addAction("Preview PDF")
        act_colour.triggered.connect(self._preview_pdf)
        self.btn_preview.setMenu(self._preview_menu)

        self.btn_save_pdf = QToolButton()
        self.btn_save_pdf.setText("Save PDF")
        self.btn_save_pdf.setObjectName("invoiceToolBtn")
        self.btn_save_pdf.setPopupMode(QToolButton.InstantPopup)
        self._save_menu = QMenu(self.btn_save_pdf)
        act_save_colour = self._save_menu.addAction("Save PDF")
        act_save_colour.triggered.connect(self._save_pdf)
        self.btn_save_pdf.setMenu(self._save_menu)

        self.btn_print = QToolButton()
        self.btn_print.setText("Print")
        self.btn_print.setObjectName("invoiceToolBtn")
        self.btn_print.setPopupMode(QToolButton.InstantPopup)
        self._print_menu = QMenu(self.btn_print)
        act_print_colour = self._print_menu.addAction("Print")
        act_print_colour.triggered.connect(self._print_pdf)
        self.btn_print.setMenu(self._print_menu)

        self.btn_pay = QPushButton("Payments")
        self.btn_pay.setObjectName("invoicePayBtn")
        self.btn_pay.clicked.connect(self._payments)

        self.btn_wa = QPushButton("WhatsApp")
        self.btn_wa.setObjectName("invoiceActionBtn")
        self.btn_wa.clicked.connect(self._whatsapp)

        self.btn_edit = QPushButton("Edit Invoice")
        self.btn_edit.setObjectName("invoiceEditBtn")
        self.btn_edit.clicked.connect(self._edit_selected)

        self.btn_duplicate = QPushButton("Duplicate")
        self.btn_duplicate.setObjectName("invoiceActionBtn")
        self.btn_duplicate.clicked.connect(self._duplicate_selected)

        self._action_buttons = [
            self.btn_preview, self.btn_save_pdf, self.btn_print,
            self.btn_pay, self.btn_wa, self.btn_duplicate, self.btn_edit
        ]
        for b in self._action_buttons:
            actions.addWidget(b)
            b.setEnabled(False)
        actions.addStretch(1)
        lv.addLayout(actions)

        self._selected_invoice_id = None

    def on_first_show(self):
        self.refresh()

    def refresh(self):
        if self.editor is not None:
            return
        self._load()

    def _set_filter(self, key: str):
        self._active_status_filter = key
        for k, btn in self._filter_pills.items():
            is_active = (k == key)
            btn.setProperty("active", "true" if is_active else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self._load()

    def _cleanup_table_widgets(self):
        """Clean up all child cell widgets to avoid memory leaks and ghost widgets."""
        for r in range(self.table.rowCount()):
            for c in (1, 2, 3, 6):
                cw = self.table.cellWidget(r, c)
                if cw:
                    self.table.removeCellWidget(r, c)
                    cw.setParent(None)
                    cw.deleteLater()

    def _row_btn(self, glyph: str, tip: str, bg: str, border: str, color: str, hover_bg: str) -> QPushButton:
        b = QPushButton(glyph)
        b.setObjectName("invRowActionBtn")
        b.setCursor(Qt.PointingHandCursor)
        b.setToolTip(tip)
        b.setStyleSheet(
            f"QPushButton {{ background: {bg}; border: 1px solid {border}; border-radius: 5px; color: {color}; font-size: 12px; font-weight: 700; padding: 0; min-width: 28px; max-width: 28px; min-height: 28px; max-height: 28px; }}"
            f"QPushButton:hover {{ background: {hover_bg}; border-color: #94A3B8; }}"
            f"QPushButton:disabled {{ background: #F8FAFC; border-color: #E2E8F0; color: #CBD5E1; }}"
        )
        return b

    def _load(self):
        q = self.search.text().strip() if hasattr(self, "search") else ""
        filter_key = self._active_status_filter

        # 1. Fetch all matching invoices to compute overall KPIs and counts
        status_filter_arg = "SAVED" if filter_key == "Saved" else "DRAFT" if filter_key == "Draft" else ""
        invoices = invoice_service.search_invoices(q, status_filter_arg, 400)

        # Global stats across all retrieved invoices
        total_count = len(invoices)
        total_billed = sum(float(inv.grand_total or 0) for inv in invoices if inv.status != "DRAFT")
        total_paid = sum(sum(float(p.amount or 0) for p in (inv.payments or [])) for inv in invoices)
        total_due = max(total_billed - total_paid, 0.0)

        self.lbl_kpi_count.setText(str(total_count))
        self.lbl_kpi_billed.setText(_money(total_billed))
        self.lbl_kpi_paid.setText(_money(total_paid))
        self.lbl_kpi_due.setText(_money(total_due))

        # Count per category for pills
        counts = {"All": total_count, "UNPAID": 0, "PARTIALLY PAID": 0, "PAID": 0, "OVERDUE": 0, "Draft": 0}
        for inv in invoices:
            if inv.status == "DRAFT":
                counts["Draft"] += 1
            else:
                p_sum = sum(float(p.amount or 0) for p in (inv.payments or []))
                st = compute_status(inv.grand_total, p_sum, inv.status, inv.due_date)
                if st in counts:
                    counts[st] += 1

        for k, btn in self._filter_pills.items():
            base_label = {
                "All": "All",
                "UNPAID": "Unpaid",
                "PARTIALLY PAID": "Partially Paid",
                "PAID": "Paid",
                "OVERDUE": "Overdue",
                "Draft": "Draft",
            }.get(k, k)
            btn.setText(f"{base_label} ({counts.get(k, 0)})")

        # 2. Filter rows for display
        display_rows = []
        for inv in invoices:
            total = float(inv.grand_total or 0)
            paid = sum(float(p.amount or 0) for p in (inv.payments or []))
            outstanding = max(total - paid, 0.0)
            st = compute_status(inv.grand_total, paid, inv.status, inv.due_date)

            if filter_key == "Draft" and inv.status != "DRAFT":
                continue
            if filter_key not in ("All", "Draft", "Saved") and st != filter_key:
                continue

            display_rows.append((inv, total, paid, outstanding, st))

        self._cleanup_table_widgets()
        self.table.setRowCount(0)

        for inv, total, paid, outstanding, st in display_rows:
            r = self.table.rowCount()
            self.table.insertRow(r)

            # Col 0: Invoice No
            it_no = QTableWidgetItem(inv.invoice_number or "")
            it_no.setData(Qt.UserRole, inv.id)
            it_no.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            it_no.setForeground(Qt.GlobalColor.darkBlue)
            self.table.setItem(r, 0, it_no)

            # Col 1: Customer & Mobile (2-line widget)
            cust_name = inv.customer.name if inv.customer else "—"
            cust_mob = inv.customer.mobile if (inv.customer and inv.customer.mobile) else ""
            w_cust = QWidget()
            lay_cust = QVBoxLayout(w_cust)
            lay_cust.setContentsMargins(8, 2, 8, 2)
            lay_cust.setSpacing(1)
            lbl_name = QLabel(cust_name)
            lbl_name.setStyleSheet("font-weight: 700; color: #0F172A; font-size: 12px;")
            lbl_mob = QLabel(f"\u260E {cust_mob}" if cust_mob else "No mobile saved")
            lbl_mob.setStyleSheet("color: #64748B; font-size: 10px;")
            lay_cust.addWidget(lbl_name)
            lay_cust.addWidget(lbl_mob)
            it_cust = QTableWidgetItem("")
            it_cust.setData(Qt.UserRole, inv.id)
            self.table.setItem(r, 1, it_cust)
            self.table.setCellWidget(r, 1, w_cust)

            # Col 2: Date & Due Date (2-line widget)
            inv_date_str = inv.invoice_date.strftime("%d-%b-%Y") if inv.invoice_date else "—"
            due_date_str = inv.due_date.strftime("%d-%b-%Y") if inv.due_date else ""
            w_date = QWidget()
            lay_date = QVBoxLayout(w_date)
            lay_date.setContentsMargins(6, 2, 6, 2)
            lay_date.setSpacing(1)
            lbl_idate = QLabel(inv_date_str)
            lbl_idate.setStyleSheet("font-weight: 600; color: #0F172A; font-size: 11px;")
            lbl_due = QLabel(f"Due: {due_date_str}" if due_date_str else "Immediate")
            lbl_due.setStyleSheet("color: #94A3B8; font-size: 10px;")
            lay_date.addWidget(lbl_idate)
            lay_date.addWidget(lbl_due)
            it_date = QTableWidgetItem("")
            it_date.setData(Qt.UserRole, inv.id)
            self.table.setItem(r, 2, it_date)
            self.table.setCellWidget(r, 2, w_date)

            # Col 3: Status Badge
            w_st = QWidget()
            lay_st = QHBoxLayout(w_st)
            lay_st.setContentsMargins(4, 2, 4, 2)
            lay_st.setAlignment(Qt.AlignCenter)
            badge = QLabel(st)
            badge.setAlignment(Qt.AlignCenter)

            if st == "PAID":
                badge_style = "background: #ECFDF5; color: #059669; border: 1px solid #A7F3D0;"
            elif st == "PARTIALLY PAID":
                badge_style = "background: #FFFBEB; color: #D97706; border: 1px solid #FDE68A;"
            elif st == "OVERDUE":
                badge_style = "background: #FEF2F2; color: #DC2626; border: 1px solid #FECACA;"
            elif st == "UNPAID":
                badge_style = "background: #EFF6FF; color: #2563EB; border: 1px solid #BFDBFE;"
            else:
                badge_style = "background: #F1F5F9; color: #475569; border: 1px solid #CBD5E1;"

            badge.setStyleSheet(f"{badge_style} border-radius: 10px; font-weight: 700; font-size: 10px; padding: 3px 10px;")
            lay_st.addWidget(badge)
            it_st = QTableWidgetItem("")
            it_st.setData(Qt.UserRole, inv.id)
            self.table.setItem(r, 3, it_st)
            self.table.setCellWidget(r, 3, w_st)

            # Col 4: Amount
            it_amt = QTableWidgetItem(_money(total))
            it_amt.setData(Qt.UserRole, inv.id)
            it_amt.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
            it_amt.setForeground(Qt.GlobalColor.black)
            self.table.setItem(r, 4, it_amt)

            # Col 5: Balance Due
            it_due = QTableWidgetItem(_money(outstanding))
            it_due.setData(Qt.UserRole, inv.id)
            it_due.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
            if outstanding > 0:
                it_due.setForeground(Qt.GlobalColor.darkRed)
            else:
                it_due.setForeground(Qt.GlobalColor.darkGreen)
            self.table.setItem(r, 5, it_due)

            # Col 6: Row Action Buttons
            w_act = QWidget()
            lay_act = QHBoxLayout(w_act)
            lay_act.setContentsMargins(4, 2, 4, 2)
            lay_act.setSpacing(4)
            lay_act.setAlignment(Qt.AlignCenter)

            btn_prev = self._row_btn("\uD83D\uDCC4", "Preview & Print PDF", "#EFF6FF", "#BFDBFE", "#1D4ED8", "#DBEAFE")
            btn_prev.clicked.connect(lambda _, id=inv.id: self._preview_pdf_by_id(id))

            btn_wa = self._row_btn("\uD83D\uDCAC", "Share on WhatsApp", "#ECFDF5", "#A7F3D0", "#047857", "#D1FAE5")
            btn_wa.clicked.connect(lambda _, id=inv.id: self._whatsapp_by_id(id))
            btn_wa.setEnabled(bool(inv.customer and inv.customer.mobile))

            btn_pay = self._row_btn("\u20B9", "Record Payment", "#FFFBEB", "#FDE68A", "#B45309", "#FEF3C7")
            btn_pay.clicked.connect(lambda _, id=inv.id: self._payments_by_id(id))

            btn_edit = self._row_btn("\u270E", "Edit Invoice", "#F1F5F9", "#CBD5E1", "#1E293B", "#E2E8F0")
            btn_edit.clicked.connect(lambda _, id=inv.id: self._edit_row_by_id(id))

            btn_del = self._row_btn("\uD83D\uDDD1", "Delete Invoice", "#FEF2F2", "#FECACA", "#B91C1C", "#FEE2E2")
            btn_del.clicked.connect(lambda _, id=inv.id, no=inv.invoice_number: self._confirm_delete(id, no))

            lay_act.addWidget(btn_prev)
            lay_act.addWidget(btn_wa)
            lay_act.addWidget(btn_pay)
            lay_act.addWidget(btn_edit)
            lay_act.addWidget(btn_del)
            it_act = QTableWidgetItem("")
            it_act.setData(Qt.UserRole, inv.id)
            self.table.setItem(r, 6, it_act)
            self.table.setCellWidget(r, 6, w_act)

        has_rows = len(display_rows) > 0
        self.table.setVisible(has_rows)
        self.empty_label.setVisible(not has_rows)

    def _search(self, _=None):
        if self.editor is not None:
            return
        self._search_timer.start()

    def _selection_changed(self):
        rows = self.table.selectionModel().selectedRows()
        self._selected_invoice_id = None
        for b in self._action_buttons:
            b.setEnabled(False)
        if rows:
            row = rows[0].row()
            item = self.table.item(row, 0)
            if item:
                inv_id = item.data(Qt.UserRole)
                if inv_id:
                    self._selected_invoice_id = inv_id
                    db_status = get_invoice_status(inv_id)
                    is_saved = bool(db_status and db_status != "DRAFT")
                    for b in self._action_buttons:
                        b.setEnabled(True)
                    if not is_saved:
                        self.btn_preview.setEnabled(False)
                        self.btn_save_pdf.setEnabled(False)
                        self.btn_print.setEnabled(False)
                        self.btn_wa.setEnabled(False)

    def _edit_selected(self):
        if self._selected_invoice_id:
            self._edit_row_by_id(self._selected_invoice_id)

    def _edit_row_by_id(self, inv_id):
        inv = invoice_service.get_invoice(inv_id)
        if inv:
            self._open_editor(invoice=inv)

    def _duplicate_selected(self):
        if not self._selected_invoice_id:
            return
        try:
            new_inv = invoice_service.duplicate_invoice(self._selected_invoice_id)
            show_toast(self, f"Duplicated as new draft: {new_inv.invoice_number}", "success")
            self._load()
            self._open_editor(invoice=new_inv)
        except Exception as e:
            show_toast(self, f"Could not duplicate invoice: {e}", "error")

    def _payments(self):
        if self._selected_invoice_id:
            self._payments_by_id(self._selected_invoice_id)

    def _payments_by_id(self, inv_id):
        inv = invoice_service.get_invoice(inv_id)
        if inv is None:
            return
        from app.ui.pages.payment_dialog import PaymentDialog
        dlg = PaymentDialog(inv, self)
        dlg.exec()
        self._load()
        if hasattr(self.main_window, "refresh_current"):
            self.main_window.refresh_current()

    def _preview_pdf(self):
        if self._selected_invoice_id:
            self._preview_pdf_by_id(self._selected_invoice_id)

    def _preview_pdf_by_id(self, inv_id):
        self._ensure_pdf_engine()
        from app.pdf.pdf_service import PdfPreviewDialog
        dlg = PdfPreviewDialog(inv_id, self)
        dlg.exec()

    def _save_pdf(self):
        if not self._selected_invoice_id:
            return
        self._ensure_pdf_engine()
        from app.pdf.pdf_service import save_pdf
        p = save_pdf(self, self._selected_invoice_id)
        if p:
            show_toast(self, f"PDF saved: {p.name}", "success")

    def _print_pdf(self):
        if self._selected_invoice_id:
            self._preview_pdf_by_id(self._selected_invoice_id)

    def _whatsapp(self):
        if self._selected_invoice_id:
            self._whatsapp_by_id(self._selected_invoice_id)

    def _whatsapp_by_id(self, inv_id):
        inv = invoice_service.get_invoice(inv_id)
        if inv is None or inv.customer is None or not inv.customer.mobile:
            QMessageBox.warning(self, "WhatsApp", "This customer has no mobile number saved.")
            return
        from app.services.business_service import get_profile
        from app.services.whatsapp_service import share_invoice_pdf
        profile = get_profile()
        try:
            share_invoice_pdf(
                self,
                inv.id,
                inv.customer.name,
                profile.business_name if profile else "",
                inv.invoice_number,
                inv.customer.mobile,
            )
        except Exception as e:
            QMessageBox.warning(self, "WhatsApp", f"Share failed: {e}")

    def _confirm_delete(self, inv_id: int, inv_no: str):
        reply = QMessageBox.question(
            self,
            "Delete Invoice",
            f"Are you sure you want to permanently delete Invoice {inv_no}?\nThis action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            if invoice_service.delete_invoice(inv_id):
                show_toast(self, f"Invoice {inv_no} deleted.", "success")
                self._load()
                if hasattr(self.main_window, "refresh_current"):
                    self.main_window.refresh_current()
            else:
                show_toast(self, "Could not delete invoice.", "error")

    def _export_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Export Invoices to CSV", "invoices_export.csv", "CSV Files (*.csv)"
        )
        if not path:
            return
        try:
            invoices = invoice_service.search_invoices(self.search.text().strip(), "", 1000)
            with open(path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Invoice No", "Customer Name", "Mobile", "Date", "Due Date",
                    "Status", "Grand Total", "Paid Amount", "Outstanding Due"
                ])
                for inv in invoices:
                    total = float(inv.grand_total or 0)
                    paid = sum(float(p.amount or 0) for p in (inv.payments or []))
                    due = max(total - paid, 0.0)
                    st = compute_status(inv.grand_total, paid, inv.status, inv.due_date)
                    writer.writerow([
                        inv.invoice_number,
                        inv.customer.name if inv.customer else "",
                        inv.customer.mobile if (inv.customer and inv.customer.mobile) else "",
                        inv.invoice_date.strftime("%Y-%m-%d") if inv.invoice_date else "",
                        inv.due_date.strftime("%Y-%m-%d") if inv.due_date else "",
                        st,
                        f"{total:.2f}",
                        f"{paid:.2f}",
                        f"{due:.2f}",
                    ])
            show_toast(self, f"Exported {len(invoices)} invoices to CSV.", "success")
        except Exception as e:
            show_toast(self, f"Export failed: {e}", "error")

    @staticmethod
    def _ensure_pdf_engine():
        from PySide6 import QtWebEngineWidgets  # noqa: F401

    def _new_invoice(self):
        self._open_editor(invoice=None)

    def start_new_invoice(self, customer_id=None):
        self._open_editor(invoice=None, customer_id=customer_id)

    def _edit_row(self, row):
        if row < 0:
            return
        item = self.table.item(row, 0)
        if item:
            inv_id = item.data(Qt.UserRole)
            if inv_id:
                self._edit_row_by_id(inv_id)

    def _edit_from_data(self):
        pass

    def _open_editor(self, invoice=None, customer_id=None):
        while self.editor_slot.count():
            item = self.editor_slot.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self._set_list_visible(False)

        self.editor = InvoiceEditor(
            main_window=self.main_window, invoice=invoice,
            customer_id=customer_id, on_close_callback=self._on_editor_close
        )
        self.editor_slot.addWidget(self.editor)

    def _set_list_visible(self, visible):
        def apply(widget):
            widget.setVisible(visible)

        def walk(layout):
            for i in range(layout.count()):
                item = layout.itemAt(i)
                if item.widget():
                    apply(item.widget())
                elif item.layout():
                    walk(item.layout())

        walk(self.list_view)

    def _on_editor_close(self, refresh=False):
        while self.editor_slot.count():
            item = self.editor_slot.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        self.editor = None
        self._set_list_visible(True)
        if refresh:
            self._load()
        if hasattr(self.main_window, "refresh_current"):
            self.main_window.refresh_current()
