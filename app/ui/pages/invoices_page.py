"""Invoices page: list/search invoices and launch the editor.

PDF / WhatsApp actions appear only for SAVED invoices and are wired up
in later steps; the editor itself is fully functional here.
"""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QMessageBox,
)

from app.services import invoice_service
from app.services.invoice_service import invoice_status, invoice_outstanding
from app.ui.pages.base_page import BasePage
from app.ui.pages.invoice_editor import InvoiceEditor
from app.ui.widgets.common import primary_button, show_toast
from app.ui.style import PRIMARY, SUCCESS, WARNING, DANGER
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
        lv.setContentsMargins(24, 20, 24, 20)
        lv.setSpacing(16)

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by invoice no, customer, mobile...")
        self.search.setFixedWidth(300)
        self.search.textChanged.connect(self._search)
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All", "Saved", "Draft", "PAID", "PARTIALLY PAID", "UNPAID", "OVERDUE"])
        self.status_filter.currentTextChanged.connect(self._search)
        btn_new = primary_button("+ New Invoice")
        btn_new.clicked.connect(self._new_invoice)
        top.addWidget(self.search)
        top.addWidget(self.status_filter)
        top.addStretch(1)
        top.addWidget(btn_new)
        lv.addLayout(top)

        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Invoice No", "Customer", "Date", "Status", "Amount", "Outstanding"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.cellDoubleClicked.connect(lambda r, c: self._edit_row(r))
        self.table.itemSelectionChanged.connect(self._selection_changed)
        self.empty_label = QLabel("No invoices yet. Click '+ New Invoice' to create one.")
        self.empty_label.setAlignment(Qt.AlignCenter)
        self.empty_label.setStyleSheet("color:#9CA3AF; font-size:14px; padding:40px;")
        self.empty_label.setVisible(False)
        lv.addWidget(self.table, 1)
        lv.addWidget(self.empty_label)

        # Actions bar for selected saved invoice
        actions = QHBoxLayout()
        actions.addWidget(QLabel("Actions:"))
        self.btn_preview = QPushButton("Preview PDF")
        self.btn_preview.clicked.connect(self._preview_pdf)
        self.btn_save_pdf = QPushButton("Save PDF")
        self.btn_save_pdf.clicked.connect(self._save_pdf)
        self.btn_print = QPushButton("Print")
        self.btn_print.clicked.connect(self._print_pdf)
        self.btn_pay = QPushButton("Payments")
        self.btn_pay.setObjectName("successButton")
        self.btn_pay.clicked.connect(self._payments)
        self.btn_wa = QPushButton("WhatsApp")
        self.btn_wa.clicked.connect(self._whatsapp)
        self.btn_edit = QPushButton("Edit Invoice")
        self.btn_edit.setObjectName("primaryButton")
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
        self.table.setVisible(len(invoices) > 0)
        self.empty_label.setVisible(len(invoices) == 0)
        for inv in invoices:
            r = self.table.rowCount()
            self.table.insertRow(r)
            cust = inv.customer.name if inv.customer else "-"
            # Compute status and outstanding in-memory (payments already loaded
            # via selectinload in search_invoices, so no extra DB round-trips).
            total = float(inv.grand_total or 0)
            paid = sum(float(p.amount or 0) for p in (inv.payments or []))
            outstanding = max(total - paid, 0)
            if total == 0:
                st = "DRAFT" if inv.status == "DRAFT" else "UNPAID"
            elif paid <= 0:
                if inv.due_date and inv.due_date < date.today():
                    st = "OVERDUE"
                else:
                    st = "UNPAID"
            elif paid >= total:
                st = "PAID"
            else:
                if inv.due_date and inv.due_date < date.today():
                    st = "OVERDUE"
                else:
                    st = "PARTIALLY PAID"
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

    def _search(self, _=None):
        if self.editor is not None:
            return
        self._load()

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
                inv = invoice_service.get_invoice(inv_id)
                is_saved = bool(inv and inv.status != "DRAFT")
                # enable all actions for any invoice; editing always allowed
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
        # Open the preview dialog, where the A4 PDF is loaded and the
        # user can click the "Print..." button for native printing.
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
        from app.services import whatsapp_service
        from app.services.business_service import get_profile
        profile = get_profile()
        biz_name = profile.business_name if profile else ""
        total = float(inv.grand_total or 0)
        paid = total - invoice_outstanding(inv)
        out = invoice_outstanding(inv)
        msg = whatsapp_service.build_whatsapp_message(
            inv.customer.name, biz_name, inv.invoice_number, total, paid, out)
        try:
            whatsapp_service.open_whatsapp(inv.customer.mobile, msg)
            QMessageBox.information(
                self, "WhatsApp",
                "WhatsApp has been opened with a pre-filled message.\n\n"
                "Note: WhatsApp's system does not allow attaching the PDF "
                "automatically from a local file. Please attach the invoice "
                "PDF manually if needed (use 'Save PDF' first).")
        except ValueError as e:
            QMessageBox.warning(self, "WhatsApp", str(e))

    @staticmethod
    def _ensure_pdf_engine():
        from PySide6 import QtWebEngineWidgets  # noqa: F401  ensure module loaded
        pass

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
        # clear editor slot
        while self.editor_slot.count():
            item = self.editor_slot.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()
        # hide list
        self._set_list_visible(False)

        self.editor = InvoiceEditor(
            main_window=self.main_window, invoice=invoice,
            customer_id=customer_id, on_close_callback=self._on_editor_close)
        self.editor_slot.addWidget(self.editor)

    def _set_list_visible(self, visible):
        # Toggle every widget in the list layout, including those inside
        # nested sub-layouts (the search bar and actions bar are addLayout).
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
        # remove editor
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
