"""Payment entry and history dialog."""
from __future__ import annotations

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
        btn_row.setSpacing(10)
        self.btn_full_pay = QPushButton("⚡ Pay Full Balance")
        self.btn_full_pay.setObjectName("fullPaymentBtn")
        self.btn_full_pay.setCursor(Qt.PointingHandCursor)
        self.btn_full_pay.setStyleSheet(
            "QPushButton { background: #059669; color: white; font-weight: 700; font-size: 12px; "
            "border: none; border-radius: 6px; padding: 7px 16px; }"
            "QPushButton:hover { background: #047857; }"
            "QPushButton:disabled { background: #E2E8F0; color: #94A3B8; }"
        )
        self.btn_full_pay.clicked.connect(self._pay_full_balance)
        btn_row.addWidget(self.btn_full_pay)

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

    def _sync_external_views(self):
        """Notify parent page and all main window pages of payment change."""
        p = self.parent()
        if p and hasattr(p, "refresh"):
            try:
                p.refresh()
            except Exception:
                pass
        if p and hasattr(p, "_load"):
            try:
                p._load()
            except Exception:
                pass
        mw = getattr(p, "main_window", None) or (p if hasattr(p, "refresh_all") else None)
        if mw and hasattr(mw, "refresh_all"):
            mw.refresh_all()

    def accept(self):
        self._sync_external_views()
        super().accept()

    def reject(self):
        self._sync_external_views()
        super().reject()

    def _update_summary(self):
        s = payment_service.invoice_payment_summary(self.invoice.id)
        total = round(float(s["total"] or 0), 2)
        paid = round(float(s["paid"] or 0), 2)
        out = round(max(float(s["outstanding"] or 0), 0.0), 2)
        if out <= 0.009:
            self.info.setText(
                f"Invoice Total: \u20B9 {total:,.2f}   |   "
                f"Paid: \u20B9 {paid:,.2f}   |   "
                f"\u2705 Fully Settled (\u20B9 0.00 Due)"
            )
            self.info.setStyleSheet("font-weight:700; color:#059669; font-size:12px;")
            if hasattr(self, "btn_full_pay"):
                self.btn_full_pay.setEnabled(False)
                self.btn_full_pay.setText("\u2705 Fully Settled")
            if hasattr(self, "f_amount"):
                self.f_amount.setText("")
        else:
            self.info.setText(
                f"Invoice Total: \u20B9 {total:,.2f}   |   "
                f"Paid: \u20B9 {paid:,.2f}   |   "
                f"Outstanding: \u20B9 {out:,.2f}"
            )
            self.info.setStyleSheet("font-weight:700; color:#DC2626; font-size:12px;")
            if hasattr(self, "btn_full_pay"):
                self.btn_full_pay.setEnabled(True)
                self.btn_full_pay.setText(f"\u26A1 Pay Full Balance (\u20B9 {out:,.2f})")
            if hasattr(self, "f_amount") and not self.f_amount.text().strip():
                self.f_amount.setText(f"{out:,.2f}".replace(",", ""))

    def _pay_full_balance(self):
        s = payment_service.invoice_payment_summary(self.invoice.id)
        out = round(float(s["outstanding"] or 0), 2)
        if out <= 0.009:
            show_toast(self, "This invoice is already fully paid.", "info")
            return
        mode = self.f_mode.currentText()
        ref = self.f_ref.text().strip() or "Full Settlement"
        notes = self.f_notes.text().strip() or "Full balance settled"
        reply = QMessageBox.question(
            self,
            "Confirm Full Settlement",
            f"Record full payment of \u20B9 {out:,.2f} via {mode} for Invoice #{self.invoice.invoice_number}?\n\nThis will mark the invoice as PAID.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if reply != QMessageBox.Yes:
            return
        try:
            payment_service.add_payment(
                self.invoice.id,
                out,
                date_value=self.f_date.date().toPython(),
                mode=mode,
                reference=ref,
                notes=notes,
            )
            show_toast(self, f"Invoice #{self.invoice.invoice_number} marked as FULLY PAID! (\u20B9 {out:,.2f})", "success")
            self._load()
            self._sync_external_views()
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

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
            amount = round(float(self.f_amount.text().strip()), 2)
        except ValueError:
            QMessageBox.warning(self, "Invalid amount", "Enter a valid amount.")
            return
        if amount <= 0:
            QMessageBox.warning(self, "Invalid amount", "Amount must be > 0.")
            return
        summary = payment_service.invoice_payment_summary(self.invoice.id)
        outstanding = round(float(summary["outstanding"] or 0), 2)
        if amount > round(outstanding + 0.009, 2):
            QMessageBox.warning(
                self, "Overpayment",
                f"Payment of \u20B9 {amount:,.2f} exceeds the outstanding "
                f"balance of \u20B9 {outstanding:,.2f}. Please enter an "
                "amount up to the outstanding balance.",
            )
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
            self._sync_external_views()
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
            self._sync_external_views()
