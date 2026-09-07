"""Invoices page: list/search invoices and launch the editor.

PDF / WhatsApp actions appear only for SAVED invoices and are wired up
in later steps; the editor itself is fully functional here.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
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
        lv.setContentsMargins(28, 22, 28, 22)
        lv.setSpacing(14)

        # --- Search + Filter + New Invoice (glass toolbar) ---
        top = QHBoxLayout()
        top.setSpacing(10)
        self.search = QLineEdit()
        self.search.setObjectName("invoiceSearch")
        self.search.setPlaceholderText("Search by invoice no, customer, mobile...")
        self.search.setFixedWidth(320)
        # Debounce search — fire query only after user pauses typing
        self._search_timer = QTimer(self)
        self._search_timer.setSingleShot(True)
        self._search_timer.setInterval(250)
        self._search_timer.timeout.connect(self._load)
        self.search.textChanged.connect(self._search)
        self.status_filter = QComboBox()
        self.status_filter.setObjectName("invoiceStatusFilter")
        self.status_filter.addItems(["All", "Saved", "Draft", "PAID", "PARTIALLY PAID", "UNPAID", "OVERDUE"])
        self.status_filter.currentTextChanged.connect(self._search)
        btn_new = QPushButton("+ New Invoice")
        btn_new.setObjectName("invoiceNewBtn")
        btn_new.setCursor(Qt.PointingHandCursor)
        btn_new.clicked.connect(self._new_invoice)
        top.addWidget(self.search)
        top.addWidget(self.status_filter)
        top.addStretch(1)
        top.addWidget(btn_new)
        lv.addLayout(top)

        # --- Invoice table (glass depth) ---
        self.table = QTableWidget(0, 6)
        self.table.setObjectName("invoiceTable")
        self.table.setHorizontalHeaderLabels(["Invoice No", "Customer", "Date", "Status", "Amount", "Outstanding"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.cellDoubleClicked.connect(lambda r, c: self._edit_row(r))
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.empty_label = QLabel("No invoices yet. Click '+ New Invoice' to create one.")
        self.empty_label.setObjectName("invoiceEmptyTitle")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setVisible(False)
        lv.addWidget(self.table, 1)
        lv.addWidget(self.empty_label)

        # --- Actions bar (glass) ---
        actions = QHBoxLayout()
        actions.setSpacing(8)
        actions_label = QLabel("ACTIONS")
        actions_label.setObjectName("invoiceActionsLabel")
        actions.addWidget(actions_label)

        # --- Preview PDF dropdown ---
        self.btn_preview = QToolButton()
        self.btn_preview.setText("Preview PDF")
        self.btn_preview.setObjectName("invoiceToolBtn")
        self.btn_preview.setPopupMode(QToolButton.InstantPopup)
        self._preview_menu = QMenu(self.btn_preview)
        act_colour = self._preview_menu.addAction("Preview PDF")
        act_colour.triggered.connect(self._preview_pdf)
        self.btn_preview.setMenu(self._preview_menu)

        # --- Save PDF dropdown ---
        self.btn_save_pdf = QToolButton()
        self.btn_save_pdf.setText("Save PDF")
        self.btn_save_pdf.setObjectName("invoiceToolBtn")
        self.btn_save_pdf.setPopupMode(QToolButton.InstantPopup)
        self._save_menu = QMenu(self.btn_save_pdf)
        act_save_colour = self._save_menu.addAction("Save PDF")
        act_save_colour.triggered.connect(self._save_pdf)
        self.btn_save_pdf.setMenu(self._save_menu)

        # --- Print dropdown ---
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
        self._action_buttons = [self.btn_preview, self.btn_save_pdf, self.btn_print,
                                self.btn_pay, self.btn_wa, self.btn_edit]
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

    def _load(self):
        q = self.search.text() if hasattr(self, "search") else ""
        status = self.status_filter.currentText() if hasattr(self, "status_filter") else "All"
        status_filter = {
            "Saved": "SAVED",
            "Draft": "DRAFT",
        }.get(status)
        invoices = invoice_service.search_invoices(q, status_filter or "", 300)
        self.table.setRowCount(0)
        self.table.setVisible(False)
        self.empty_label.setVisible(False)
        for inv in invoices:
            cust = inv.customer.name if inv.customer else "-"
            total = float(inv.grand_total or 0)
            paid = sum(float(p.amount or 0) for p in (inv.payments or []))
            outstanding = max(total - paid, 0)
            st = compute_status(inv.grand_total, paid, inv.status, inv.due_date)
            # Skip rows that don't match the computed status filter
            if status not in ("All", "Saved", "Draft") and st != status:
                continue
            r = self.table.rowCount()
            self.table.insertRow(r)
            vals = [inv.invoice_number, cust,
                    inv.invoice_date.strftime("%d-%b-%Y") if inv.invoice_date else "-",
                    st, _money(inv.grand_total), _money(outstanding)]
            for c, vv in enumerate(vals):
                item = QTableWidgetItem(str(vv))
                item.setData(Qt.UserRole, inv.id)
                self.table.setItem(r, c, item)
            status_item = self.table.item(r, 3)
            status_item.setForeground(
                Qt.GlobalColor.darkGreen if st == "PAID"
                else Qt.GlobalColor.darkRed if st in ("OVERDUE", "UNPAID")
                else Qt.GlobalColor.darkYellow if "PART" in st
                else Qt.GlobalColor.darkGray)
        self.table.setVisible(self.table.rowCount() > 0)
        self.empty_label.setVisible(self.table.rowCount() == 0)

    def _search(self, _=None):
        if self.editor is not None:
            return
        # Restart debounce timer — query fires after 250ms of no typing
        self._search_timer.start()

    def _selection_changed(self):
        rows = self.table.selectionModel().selectedRows()
        self._selected_invoice_id = None
        for b in self._action_buttons:
            b.setEnabled(False)
        if rows:
            row = rows[0].row()
            inv_id = self.table.item(row, 0).data(Qt.UserRole)
            if inv_id:
                self._selected_invoice_id = inv_id
                # Use lightweight status query instead of full eager-loaded fetch
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

    def _payments(self):
        if not self._selected_invoice_id:
            return
        inv = invoice_service.get_invoice(self._selected_invoice_id)
        if inv is None:
            return
        from app.ui.pages.payment_dialog import PaymentDialog
        dlg = PaymentDialog(inv, self)
        dlg.exec()
        self._load()
        if hasattr(self.main_window, "refresh_current"):
            self.main_window.refresh_current()

    def _preview_pdf(self):
        if not self._selected_invoice_id:
            return
        self._ensure_pdf_engine()
        from app.pdf.pdf_service import PdfPreviewDialog
        dlg = PdfPreviewDialog(self._selected_invoice_id, self)
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
        if not self._selected_invoice_id:
            return
        self._ensure_pdf_engine()
        from app.pdf.pdf_service import PdfPreviewDialog
        dlg = PdfPreviewDialog(self._selected_invoice_id, self)
        dlg.exec()

    def _whatsapp(self):
        if not self._selected_invoice_id:
            return
        inv = invoice_service.get_invoice(self._selected_invoice_id)
        if inv is None \
           or inv.customer is None \
           or not inv.customer.mobile:
            QMessageBox.warning(self, "WhatsApp",
                                "This customer has no mobile number saved.")
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
        except Exception as e:  # noqa: BLE001
            QMessageBox.warning(self, "WhatsApp", f"Share failed: {e}")

    @staticmethod
    def _ensure_pdf_engine():
        from PySide6 import QtWebEngineWidgets  # noqa: F401  ensure module loaded

    def _new_invoice(self):
        self._open_editor(invoice=None)

    def start_new_invoice(self, customer_id=None):
        self._open_editor(invoice=None, customer_id=customer_id)

    def _edit_row(self, row):
        if row < 0:
            return
        inv_id = self.table.item(row, 0).data(Qt.UserRole)
        inv = invoice_service.get_invoice(inv_id)
        if inv:
            self._open_editor(invoice=inv)

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
            customer_id=customer_id, on_close_callback=self._on_editor_close)
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
