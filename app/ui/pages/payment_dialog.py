"""Payment entry and history dialog."""
from __future__ import annotations

from datetime import date

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from app.services import payment_service
from app.ui.widgets.common import primary_button, show_toast


class PaymentDialog(QDialog):
    def __init__(self, invoice, parent=None):
        super().__init__(parent)
        self.invoice = invoice
        self.setWindowTitle(f"Payments - {invoice.invoice_number}")
        self.resize(560, 560)
        v = QVBoxLayout(self)

        title = QLabel(f"Payments for Invoice #{invoice.invoice_number}")
        title.setObjectName("dialogTitle")
        v.addWidget(title)

        initial = payment_service.invoice_payment_summary(self.invoice.id)
        initial_out = float(initial["outstanding"] or 0)
        self.info = QLabel()
        self.info.setStyleSheet("font-weight:600; color:#2563EB;")
        self._update_summary()
        v.addWidget(self.info)

        # Entry form
        form = QFormLayout()
        form.setVerticalSpacing(8)
        self.f_amount = QLineEdit()
        self.f_amount.setPlaceholderText("0.00")
        self.f_amount.setText(str(initial_out) if initial_out > 0 else "")
        self.f_date = QDateEdit(QDate.currentDate())
        self.f_date.setCalendarPopup(True)
        self.f_mode = QComboBox()
        self.f_mode.addItems(["Cash", "UPI", "Bank Transfer", "Cheque", "Other"])
        self.f_ref = QLineEdit()
        self.f_ref.setPlaceholderText("UPI txn / cheque / ref no")
        self.f_notes = QLineEdit()
        self.f_notes.setPlaceholderText("Notes (optional)")

        form.addRow("Amount", self.f_amount)
        form.addRow("Date", self.f_date)
        form.addRow("Payment Mode", self.f_mode)
        form.addRow("Reference No", self.f_ref)
        form.addRow("Notes", self.f_notes)
        v.addLayout(form)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_add = primary_button("+ Add Payment")
        btn_add.clicked.connect(self._add)
        btn_row.addWidget(btn_add)
        v.addLayout(btn_row)

        # history table
        v.addWidget(QLabel("Payment History"))
        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Date", "Mode", "Reference", "Amount", ""])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.setMinimumHeight(200)
        v.addWidget(self.table, 1)

        close = QPushButton("Close")
        close.clicked.connect(self.accept)
        v.addWidget(close, alignment=Qt.AlignRight)

        self._load()

    def _update_summary(self):
        s = payment_service.invoice_payment_summary(self.invoice.id)
        total = float(s["total"] or 0)
        paid = float(s["paid"] or 0)
        out = float(s["outstanding"] or 0)
        self.info.setText(
            f"Invoice Total: \u20B9 {total:,.2f}   |   "
            f"Paid: \u20B9 {paid:,.2f}   |   "
            f"Outstanding: \u20B9 {out:,.2f}"
        )

    def _load(self):
        pays = payment_service.list_payments_for_invoice(self.invoice.id)
        self.table.setRowCount(0)
        self._update_summary()
        for p in pays:
            r = self.table.rowCount()
            self.table.insertRow(r)
            vals = [p.date.strftime("%d-%b-%Y") if p.date else "-",
                    p.mode, p.reference or "-", f"\u20B9 {float(p.amount or 0):,.2f}"]
            for c, vv in enumerate(vals):
                self.table.setItem(r, c, QTableWidgetItem(str(vv)))
            del_btn = QPushButton("Delete")
            del_btn.setFixedWidth(70)
            del_btn.clicked.connect(lambda _=False, pid=p.id: self._delete_payment(pid))
            self.table.setCellWidget(r, 4, del_btn)

    def _add(self):
        try:
            amount = float(self.f_amount.text().strip())
        except ValueError:
            QMessageBox.warning(self, "Invalid amount", "Enter a valid amount.")
            return
        if amount <= 0:
            QMessageBox.warning(self, "Invalid amount", "Amount must be > 0.")
            return
        try:
            payment_service.add_payment(
                self.invoice.id, amount,
                date_value=self.f_date.date().toPython(),
                mode=self.f_mode.currentText(),
                reference=self.f_ref.text().strip(),
                notes=self.f_notes.text().strip(),
            )
            show_toast(self, f"Payment of \u20B9 {amount:,.2f} added.", "success")
            self._load()
            self.f_amount.setText("")
            self.f_ref.setText("")
            self.f_notes.setText("")
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Error", str(e))

    def _delete_payment(self, pid):
        if QMessageBox.question(self, "Delete payment",
                                "Remove this payment?", QMessageBox.Yes | QMessageBox.No) == QMessageBox.Yes:
            payment_service.delete_payment(pid)
            self._load()
