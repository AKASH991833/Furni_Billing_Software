"""Customer management page.

Add / Edit / Delete / Search customers, plus a detail view showing
invoice and payment history.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.services import customer_service
from app.services.invoice_service import invoice_status
from app.ui.pages.base_page import BasePage
from app.ui.widgets.common import card, empty_state, primary_button, show_toast


class CustomerDialog(QDialog):
    def __init__(self, parent=None, customer=None):
        super().__init__(parent)
        self.customer = customer
        self.setWindowTitle("Edit Customer" if customer else "Add Customer")
        self.setMinimumWidth(480)
        self.resize(520, 600)
        v = QVBoxLayout(self)

        title = QLabel("Edit Customer" if customer else "Add Customer")
        title.setObjectName("dialogTitle")
        v.addWidget(title)

        form = QFormLayout()
        form.setVerticalSpacing(10)

        def _lab(t):
            l = QLabel(t)
            l.setObjectName("fieldLabel")
            return l

        self.f_name = QLineEdit()
        self.f_mobile = QLineEdit()
        self.f_alt = QLineEdit()
        self.f_email = QLineEdit()
        self.f_address = QTextEdit()
        self.f_address.setFixedHeight(70)
        self.f_city = QLineEdit()
        self.f_state = QLineEdit()
        self.f_gstin = QLineEdit()
        self.f_notes = QTextEdit()
        self.f_notes.setFixedHeight(70)

        form.addRow(_lab("Name *"), self.f_name)
        form.addRow(_lab("Mobile"), self.f_mobile)
        form.addRow(_lab("Alternate Mobile"), self.f_alt)
        form.addRow(_lab("Email"), self.f_email)
        form.addRow(_lab("Address"), self.f_address)
        form.addRow(_lab("City"), self.f_city)
        form.addRow(_lab("State"), self.f_state)
        form.addRow(_lab("GSTIN"), self.f_gstin)
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
        cancel.clicked.connect(self.reject)
        save = primary_button("Save")
        save.clicked.connect(self._save)
        btns.addWidget(cancel)
        btns.addWidget(save)
        v.addLayout(btns)

    def _save(self):
        name = self.f_name.text().strip()
        if not name:
            show_toast(self, "Customer name is required.", "error")
            return
        self._data = {
            "name": name,
            "mobile": self.f_mobile.text().strip(),
            "alternate_mobile": self.f_alt.text().strip(),
            "email": self.f_email.text().strip(),
            "address": self.f_address.toPlainText().strip(),
            "city": self.f_city.text().strip(),
            "state": self.f_state.text().strip(),
            "gstin": self.f_gstin.text().strip(),
            "notes": self.f_notes.toPlainText().strip(),
        }
        self.accept()

    def result_data(self) -> dict:
        return getattr(self, "_data", {})


class CustomersPage(BasePage):
    def __init__(self, main_window=None, parent=None):
        super().__init__(main_window, parent)
        self._current_customer_id = None
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(24, 20, 24, 20)
        outer.setSpacing(16)

        top = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search customers by name, mobile, email...")
        self.search.setFixedWidth(320)
        self.search.textChanged.connect(self._search)
        btn_add = primary_button("+ Add Customer")
        btn_add.clicked.connect(self._add_customer)
        top.addWidget(self.search)
        top.addStretch(1)
        top.addWidget(btn_add)
        outer.addLayout(top)

        splitter = QSplitter(Qt.Horizontal)

        left_card = card("Customers")
        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Name", "Mobile", "Email", "City"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setAlternatingRowColors(True)
        self.table.itemSelectionChanged.connect(self._selection_changed)
        left_card.layout().addWidget(self.table)
        splitter.addWidget(left_card)

        right_card = card("Customer Details")
        self.detail_widget = QWidget()
        self._build_detail(self.detail_widget)
        right_card.layout().addWidget(self.detail_widget)
        splitter.addWidget(right_card)

        splitter.setSizes([620, 460])
        outer.addWidget(splitter, 1)

    def _build_detail(self, w):
        v = QVBoxLayout(w)
        v.setContentsMargins(0, 0, 0, 0)
        v.setSpacing(12)

        self.d_name = QLabel("-")
        self.d_name.setObjectName("cardTitle")
        self.d_contact = QLabel("")
        self.d_contact.setWordWrap(True)
        self.d_contact.setStyleSheet("color:#6B7280;")
        self.d_address = QLabel("")
        self.d_address.setWordWrap(True)
        self.d_address.setStyleSheet("color:#6B7280;")

        self.d_invoiced = QLabel("")
        self.d_paid = QLabel("")
        self.d_outstanding = QLabel("")

        v.addWidget(self.d_name)
        v.addWidget(self.d_contact)
        v.addWidget(self.d_address)
        v.addSpacing(6)

        stats = QHBoxLayout()
        stats.addWidget(self.d_invoiced)
        stats.addWidget(self.d_paid)
        stats.addWidget(self.d_outstanding)
        v.addLayout(stats)

        btn_row = QHBoxLayout()
        btn_edit = QPushButton("Edit")
        btn_edit.clicked.connect(self._edit_customer)
        btn_del = QPushButton("Delete")
        btn_del.clicked.connect(self._delete_customer)
        btn_new_inv = QPushButton("+ New Invoice")
        btn_new_inv.clicked.connect(self._new_invoice_for_customer)
        btn_row.addWidget(btn_edit)
        btn_row.addWidget(btn_del)
        btn_row.addWidget(btn_new_inv)
        btn_row.addStretch(1)
        v.addLayout(btn_row)

        v.addWidget(QLabel("Invoice History"))
        self.hist_inv = QTableWidget(0, 4)
        self.hist_inv.setHorizontalHeaderLabels(["Invoice", "Date", "Status", "Amount"])
        self.hist_inv.setEditTriggers(QTableWidget.NoEditTriggers)
        self.hist_inv.verticalHeader().setVisible(False)
        self.hist_inv.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.hist_inv.setMaximumHeight(200)
        v.addWidget(self.hist_inv)

        v.addWidget(QLabel("Payment History"))
        self.hist_pay = QTableWidget(0, 4)
        self.hist_pay.setHorizontalHeaderLabels(["Date", "Invoice", "Mode", "Amount"])
        self.hist_pay.setEditTriggers(QTableWidget.NoEditTriggers)
        self.hist_pay.verticalHeader().setVisible(False)
        self.hist_pay.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.hist_pay.setMaximumHeight(200)
        v.addWidget(self.hist_pay)
        v.addStretch(1)

    def on_first_show(self):
        self.refresh()

    def refresh(self):
        self._load(self.search.text())

    def _load(self, q=""):
        customers = customer_service.search_customers(q)
        self.table.setRowCount(0)
        for c in customers:
            r = self.table.rowCount()
            self.table.insertRow(r)
            for col, val in enumerate([c.name, c.mobile or "-", c.email or "-", c.city or "-"]):
                item = QTableWidgetItem(str(val))
                item.setData(Qt.UserRole, c.id)
                self.table.setItem(r, col, item)

    def _search(self, text):
        self._load(text)

    def _selection_changed(self):
        if not self.table.selectedItems():
            return
        row = self.table.selectedItems()[0].row()
        cid = self.table.item(row, 0).data(Qt.UserRole)
        if cid is not None:
            self._current_customer_id = cid
            self._show_detail(cid)

    def _show_detail(self, cid):
        c = customer_service.get_customer(cid)
        if not c:
            return
        self.d_name.setText(c.name or "-")
        contact = " | ".join(x for x in [c.mobile, c.email, c.gstin and f"GST: {c.gstin}"] if x)
        self.d_contact.setText(contact or "No contact info")
        addr = " | ".join(x for x in [c.address, c.city, c.state] if x)
        self.d_address.setText(addr or "")
        totals = customer_service.customer_totals(cid)
        self.d_invoiced.setText(f"Invoiced: \u20B9 {totals['total_invoiced']:,.2f}")
        self.d_paid.setText(f"Paid: \u20B9 {totals['total_paid']:,.2f}")
        self.d_outstanding.setText(f"Outstanding: \u20B9 {totals['outstanding']:,.2f}")

        invs = customer_service.customer_invoices(cid)
        self.hist_inv.setRowCount(0)
        for inv in invs:
            r = self.hist_inv.rowCount()
            self.hist_inv.insertRow(r)
            vals = [inv.invoice_number,
                    inv.invoice_date.strftime("%d-%b-%Y") if inv.invoice_date else "-",
                    inv.status,
                    f"\u20B9 {float(inv.grand_total or 0):,.2f}"]
            for col, vv in enumerate(vals):
                self.hist_inv.setItem(r, col, QTableWidgetItem(str(vv)))

        pays = customer_service.customer_payments(cid)
        self.hist_pay.setRowCount(0)
        for p in pays:
            r = self.hist_pay.rowCount()
            self.hist_pay.insertRow(r)
            inv_no = p.invoice.invoice_number if p.invoice else "-"
            vals = [p.date.strftime("%d-%b-%Y") if p.date else "-", inv_no, p.mode,
                    f"\u20B9 {float(p.amount or 0):,.2f}"]
            for col, vv in enumerate(vals):
                self.hist_pay.setItem(r, col, QTableWidgetItem(str(vv)))

    def _add_customer(self):
        dlg = CustomerDialog(self, None)
        if dlg.exec():
            data = dlg.result_data()
            try:
                customer_service.add_customer(data)
                show_toast(self, "Customer added.", "success")
                self._load(self.search.text())
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
                show_toast(self, "Customer updated.", "success")
                self._load(self.search.text())
                self._show_detail(cid)
            except Exception as e:  # noqa: BLE001
                show_toast(self, f"Error: {e}", "error")

    def _delete_customer(self):
        cid = self._current_customer_id
        if not cid:
            show_toast(self, "Select a customer first.", "error")
            return
        # Count related data before warning
        from app.services.customer_service import customer_totals
        totals = customer_totals(cid)
        inv_count = totals.get("invoice_count", 0)
        outstanding = totals.get("outstanding", 0)
        warning_parts = [f"Delete customer '{self.d_name.text()}'?"]
        if inv_count:
            warning_parts.append(f"\n\nThis will also delete {inv_count} invoice(s).")
        if outstanding > 0:
            warning_parts.append(f"\nOutstanding amount of \u20B9 {outstanding:,.2f} will be lost.")
        warning_parts.append("\n\nThis action cannot be undone.")
        if QMessageBox.question(self, "Delete Customer",
                                "".join(warning_parts),
                                QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            try:
                customer_service.delete_customer(cid)
                show_toast(self, "Customer deleted.", "success")
                self._current_customer_id = None
                self._load(self.search.text())
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
