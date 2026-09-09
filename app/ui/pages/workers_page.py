"""Workers Management Page — Attendance, Advances, Travel Expenses & Payroll Suite.

Meets all requirements of Master Prompt:
- Worker Directory with search (ID, Name, Mobile, Work Type) and filter pills.
- Fast Daily Attendance Entry with 1-click status pills (0, 0.5, 1, 1.5, 2, custom).
- Monthly Attendance History with rate preservation and bottom unit summary.
- Travel/Rickshaw Expenses & Other Adjustments (strictly separated additions/deductions).
- Advance Payments tracking.
- Monthly Settlement & Final Payment management.
- Formatted Monthly Summary Slip & WhatsApp generator.
"""
from __future__ import annotations

import calendar
from datetime import date, datetime
from decimal import Decimal
from urllib.parse import quote

from PySide6.QtCore import QDate, Qt, QUrl
from PySide6.QtGui import QColor, QDesktopServices, QFont, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QSplitter,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.services import business_service, worker_service
from app.ui.pages.base_page import BasePage
from app.ui.style import DANGER, GOLD, PRIMARY, SUCCESS, WARNING
from app.ui.widgets.common import _dark_or_light, card, show_toast


def _money(v) -> str:
    """Standard currency formatter."""
    try:
        return f"\u20B9 {float(v or 0):,.2f}"
    except (TypeError, ValueError):
        return "\u20B9 0.00"


# ===========================================================================
# Dialog 1: Add / Edit Worker
# ===========================================================================

class WorkerDialog(QDialog):
    """Add or edit worker profile."""

    def __init__(self, parent=None, worker=None):
        super().__init__(parent)
        self.worker = worker
        self.setWindowTitle("Edit Worker Profile" if worker else "Add New Worker")
        self.setMinimumWidth(440)
        self.resize(480, 520)

        v = QVBoxLayout(self)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(14)

        title = QLabel("Edit Worker Profile" if worker else "Add New Worker")
        title.setStyleSheet("font-size: 16px; font-weight: 800; color: #0F172A;")
        v.addWidget(title)

        form = QFormLayout()
        form.setVerticalSpacing(10)

        def _lab(t):
            l = QLabel(t)
            l.setStyleSheet("font-size: 11px; font-weight: 700; color: #475569;")
            return l

        self.f_code = QLineEdit()
        self.f_code.setReadOnly(True)
        self.f_code.setStyleSheet("background: #F1F5F9; color: #64748B; font-weight: 700;")
        if worker:
            self.f_code.setText(worker.worker_code or "")
        else:
            self.f_code.setText(worker_service.generate_next_worker_code())

        self.f_name = QLineEdit()
        self.f_name.setPlaceholderText("Worker Full Name *")

        self.f_mobile = QLineEdit()
        self.f_mobile.setPlaceholderText("10-digit mobile number")

        self.f_work_type = QComboBox()
        self.f_work_type.setEditable(True)
        self.f_work_type.addItems([
            "Mistri",
            "Labour",
            "Carpenter",
            "Helper",
            "Painter",
            "Electrician",
            "Plumber",
            "Other",
        ])

        self.f_daily_rate = QDoubleSpinBox()
        self.f_daily_rate.setRange(0, 100000)
        self.f_daily_rate.setPrefix("₹ ")
        self.f_daily_rate.setValue(800.0)

        self.f_joining = QDateEdit()
        self.f_joining.setCalendarPopup(True)
        self.f_joining.setDate(QDate.currentDate())

        self.f_address = QLineEdit()
        self.f_address.setPlaceholderText("Worker local / permanent address")

        self.f_notes = QTextEdit()
        self.f_notes.setFixedHeight(60)
        self.f_notes.setPlaceholderText("Optional notes or specializations")

        # Worker ID is auto-maintained in the background; user only needs name and details
        form.addRow(_lab("Worker Name *"), self.f_name)
        form.addRow(_lab("Work Type / Skill"), self.f_work_type)
        form.addRow(_lab("Daily Rate (₹ / Day) *"), self.f_daily_rate)
        form.addRow(_lab("Mobile Number"), self.f_mobile)
        form.addRow(_lab("Joining Date"), self.f_joining)
        form.addRow(_lab("Address"), self.f_address)
        form.addRow(_lab("Notes"), self.f_notes)
        v.addLayout(form)

        if worker:
            self.f_name.setText(worker.name or "")
            self.f_mobile.setText(worker.mobile or "")
            self.f_work_type.setCurrentText(worker.work_type or "Mistri")
            self.f_daily_rate.setValue(float(worker.daily_rate or 0))
            if worker.joining_date:
                self.f_joining.setDate(QDate(worker.joining_date.year, worker.joining_date.month, worker.joining_date.day))
            self.f_address.setText(worker.address or "")
            self.f_notes.setPlainText(worker.notes or "")

        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(
            "QPushButton { background: #F1F5F9; color: #475569; font-weight: 600; "
            "border: 1px solid #CBD5E1; border-radius: 6px; padding: 7px 16px; font-size: 12px; } "
            "QPushButton:hover { background: #E2E8F0; }"
        )
        cancel.clicked.connect(self.reject)

        save = QPushButton("Save Worker")
        save.setStyleSheet(
            "QPushButton { background: #173560; color: #FFFFFF; font-weight: 700; "
            "border: none; border-radius: 6px; padding: 7px 20px; font-size: 12px; } "
            "QPushButton:hover { background: #0F2342; }"
        )
        save.clicked.connect(self._save)

        btns.addWidget(cancel)
        btns.addWidget(save)
        v.addLayout(btns)

    def _save(self):
        name = self.f_name.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Worker name cannot be empty.")
            return

        rate = self.f_daily_rate.value()
        if rate < 0:
            QMessageBox.warning(self, "Validation Error", "Daily rate cannot be negative.")
            return

        q_date = self.f_joining.date()
        joining_d = date(q_date.year(), q_date.month(), q_date.day())

        self._data = {
            "worker_code": self.f_code.text().strip(),
            "name": name,
            "work_type": self.f_work_type.currentText().strip() or "Mistri",
            "daily_rate": rate,
            "mobile": self.f_mobile.text().strip(),
            "joining_date": joining_d,
            "address": self.f_address.text().strip(),
            "notes": self.f_notes.toPlainText().strip(),
        }
        self.accept()

    def get_data(self) -> dict:
        return getattr(self, "_data", {})


# ===========================================================================
# Dialog 2: Record Advance Payment
# ===========================================================================

class AdvanceDialog(QDialog):
    """Dialog to record an advance payment given to a worker."""

    def __init__(self, parent=None, workers=None, preselected_worker_id=None):
        super().__init__(parent)
        self.setWindowTitle("Record Advance Payment")
        self.setMinimumWidth(400)
        self.resize(440, 360)

        v = QVBoxLayout(self)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(14)

        title = QLabel("💵 Record Advance Payment")
        title.setStyleSheet("font-size: 16px; font-weight: 800; color: #DC2626;")
        v.addWidget(title)

        hint = QLabel("Advance payments are deducted from the worker's monthly final settlement.")
        hint.setStyleSheet("color: #64748B; font-size: 11px;")
        v.addWidget(hint)

        form = QFormLayout()
        form.setVerticalSpacing(10)

        def _lab(t):
            l = QLabel(t)
            l.setStyleSheet("font-size: 11px; font-weight: 700; color: #475569;")
            return l

        self.f_worker = QComboBox()
        self._worker_ids = []
        for idx, w in enumerate(workers or [], 1):
            self.f_worker.addItem(f"{idx}. {w.name} ({w.work_type} - ₹{float(w.daily_rate or 0):,.0f}/दिन)")
            self._worker_ids.append(w.id)

        if preselected_worker_id and preselected_worker_id in self._worker_ids:
            self.f_worker.setCurrentIndex(self._worker_ids.index(preselected_worker_id))

        self.f_date = QDateEdit()
        self.f_date.setCalendarPopup(True)
        self.f_date.setDate(QDate.currentDate())

        self.f_amount = QDoubleSpinBox()
        self.f_amount.setRange(1, 1000000)
        self.f_amount.setPrefix("₹ ")
        self.f_amount.setValue(1000.0)

        self.f_method = QComboBox()
        self.f_method.addItems(["Cash", "UPI", "Bank", "Other"])

        self.f_notes = QLineEdit()
        self.f_notes.setPlaceholderText("Personal, emergency, festival kharcha, etc.")

        form.addRow(_lab("Worker *"), self.f_worker)
        form.addRow(_lab("Date *"), self.f_date)
        form.addRow(_lab("Amount *"), self.f_amount)
        form.addRow(_lab("Payment Method"), self.f_method)
        form.addRow(_lab("Note / Reason"), self.f_notes)
        v.addLayout(form)

        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(
            "QPushButton { background: #F1F5F9; color: #475569; font-weight: 600; "
            "border: 1px solid #CBD5E1; border-radius: 6px; padding: 7px 16px; font-size: 12px; }"
        )
        cancel.clicked.connect(self.reject)

        save = QPushButton("Save Advance")
        save.setStyleSheet(
            "QPushButton { background: #DC2626; color: #FFFFFF; font-weight: 700; "
            "border: none; border-radius: 6px; padding: 7px 20px; font-size: 12px; } "
            "QPushButton:hover { background: #B91C1C; }"
        )
        save.clicked.connect(self._save)

        btns.addWidget(cancel)
        btns.addWidget(save)
        v.addLayout(btns)

    def _save(self):
        if not self._worker_ids:
            QMessageBox.warning(self, "Error", "No worker selected.")
            return
        worker_id = self._worker_ids[self.f_worker.currentIndex()]
        qd = self.f_date.date()
        adv_date = date(qd.year(), qd.month(), qd.day())
        amount = self.f_amount.value()
        if amount <= 0:
            QMessageBox.warning(self, "Validation Error", "Amount must be greater than 0.")
            return

        self._data = {
            "worker_id": worker_id,
            "date": adv_date,
            "amount": amount,
            "method": self.f_method.currentText(),
            "notes": self.f_notes.text().strip(),
        }
        self.accept()

    def get_data(self) -> dict:
        return getattr(self, "_data", {})


# ===========================================================================
# Dialog 3: Record Travel / Rickshaw Expense
# ===========================================================================

class TravelExpenseDialog(QDialog):
    """Dialog to record travel or rickshaw expenses."""

    def __init__(self, parent=None, workers=None, preselected_worker_id=None):
        super().__init__(parent)
        self.setWindowTitle("Record Travel / Rickshaw Expense")
        self.setMinimumWidth(400)
        self.resize(440, 360)

        v = QVBoxLayout(self)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(14)

        title = QLabel("🛵 Travel / Rickshaw Expense")
        title.setStyleSheet("font-size: 16px; font-weight: 800; color: #059669;")
        v.addWidget(title)

        hint = QLabel("Travel expenses are added to the worker's gross payable settlement.")
        hint.setStyleSheet("color: #64748B; font-size: 11px;")
        v.addWidget(hint)

        form = QFormLayout()
        form.setVerticalSpacing(10)

        def _lab(t):
            l = QLabel(t)
            l.setStyleSheet("font-size: 11px; font-weight: 700; color: #475569;")
            return l

        self.f_worker = QComboBox()
        self._worker_ids = []
        for idx, w in enumerate(workers or [], 1):
            self.f_worker.addItem(f"{idx}. {w.name} ({w.work_type} - ₹{float(w.daily_rate or 0):,.0f}/दिन)")
            self._worker_ids.append(w.id)

        if preselected_worker_id and preselected_worker_id in self._worker_ids:
            self.f_worker.setCurrentIndex(self._worker_ids.index(preselected_worker_id))

        self.f_date = QDateEdit()
        self.f_date.setCalendarPopup(True)
        self.f_date.setDate(QDate.currentDate())

        self.f_amount = QDoubleSpinBox()
        self.f_amount.setRange(1, 100000)
        self.f_amount.setPrefix("₹ ")
        self.f_amount.setValue(150.0)

        self.f_category = QComboBox()
        self.f_category.setEditable(True)
        self.f_category.addItems(["Rickshaw", "Travel", "Bus", "Site travel", "Other"])

        self.f_notes = QLineEdit()
        self.f_notes.setPlaceholderText("Site location, trip details, or ticket note")

        form.addRow(_lab("Worker *"), self.f_worker)
        form.addRow(_lab("Date *"), self.f_date)
        form.addRow(_lab("Amount *"), self.f_amount)
        form.addRow(_lab("Category"), self.f_category)
        form.addRow(_lab("Note / Details"), self.f_notes)
        v.addLayout(form)

        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(
            "QPushButton { background: #F1F5F9; color: #475569; font-weight: 600; "
            "border: 1px solid #CBD5E1; border-radius: 6px; padding: 7px 16px; font-size: 12px; }"
        )
        cancel.clicked.connect(self.reject)

        save = QPushButton("Save Expense")
        save.setStyleSheet(
            "QPushButton { background: #059669; color: #FFFFFF; font-weight: 700; "
            "border: none; border-radius: 6px; padding: 7px 20px; font-size: 12px; } "
            "QPushButton:hover { background: #047857; }"
        )
        save.clicked.connect(self._save)

        btns.addWidget(cancel)
        btns.addWidget(save)
        v.addLayout(btns)

    def _save(self):
        if not self._worker_ids:
            QMessageBox.warning(self, "Error", "No worker selected.")
            return
        worker_id = self._worker_ids[self.f_worker.currentIndex()]
        qd = self.f_date.date()
        exp_date = date(qd.year(), qd.month(), qd.day())
        amount = self.f_amount.value()
        if amount <= 0:
            QMessageBox.warning(self, "Validation Error", "Amount must be greater than 0.")
            return

        self._data = {
            "worker_id": worker_id,
            "date": exp_date,
            "amount": amount,
            "category": self.f_category.currentText().strip() or "Rickshaw",
            "notes": self.f_notes.text().strip(),
        }
        self.accept()

    def get_data(self) -> dict:
        return getattr(self, "_data", {})


# ===========================================================================
# Dialog 4: Record Other Adjustment (Addition vs Deduction)
# ===========================================================================

class AdjustmentDialog(QDialog):
    """Dialog to record bonus additions or penalty deductions."""

    def __init__(self, parent=None, workers=None, preselected_worker_id=None):
        super().__init__(parent)
        self.setWindowTitle("Record Payment Adjustment")
        self.setMinimumWidth(420)
        self.resize(450, 380)

        v = QVBoxLayout(self)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(14)

        title = QLabel("⚖ Payment Adjustment")
        title.setStyleSheet("font-size: 16px; font-weight: 800; color: #173560;")
        v.addWidget(title)

        form = QFormLayout()
        form.setVerticalSpacing(10)

        def _lab(t):
            l = QLabel(t)
            l.setStyleSheet("font-size: 11px; font-weight: 700; color: #475569;")
            return l

        self.f_worker = QComboBox()
        self._worker_ids = []
        for idx, w in enumerate(workers or [], 1):
            self.f_worker.addItem(f"{idx}. {w.name} ({w.work_type} - ₹{float(w.daily_rate or 0):,.0f}/दिन)")
            self._worker_ids.append(w.id)

        if preselected_worker_id and preselected_worker_id in self._worker_ids:
            self.f_worker.setCurrentIndex(self._worker_ids.index(preselected_worker_id))

        self.f_type = QComboBox()
        self.f_type.addItems(["ADDITION (+ Increase Pay)", "DEDUCTION (- Decrease Pay)"])

        self.f_date = QDateEdit()
        self.f_date.setCalendarPopup(True)
        self.f_date.setDate(QDate.currentDate())

        self.f_amount = QDoubleSpinBox()
        self.f_amount.setRange(1, 100000)
        self.f_amount.setPrefix("₹ ")
        self.f_amount.setValue(300.0)

        self.f_category = QComboBox()
        self.f_category.setEditable(True)
        self.f_category.addItems(["Bonus", "Extra payment", "Food allowance", "Penalty deduction", "Other"])

        self.f_notes = QLineEdit()
        self.f_notes.setPlaceholderText("Specific reason for adjustment")

        form.addRow(_lab("Worker *"), self.f_worker)
        form.addRow(_lab("Adjustment Type *"), self.f_type)
        form.addRow(_lab("Date *"), self.f_date)
        form.addRow(_lab("Amount *"), self.f_amount)
        form.addRow(_lab("Category"), self.f_category)
        form.addRow(_lab("Note"), self.f_notes)
        v.addLayout(form)

        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(
            "QPushButton { background: #F1F5F9; color: #475569; font-weight: 600; "
            "border: 1px solid #CBD5E1; border-radius: 6px; padding: 7px 16px; font-size: 12px; }"
        )
        cancel.clicked.connect(self.reject)

        save = QPushButton("Save Adjustment")
        save.setStyleSheet(
            "QPushButton { background: #173560; color: #FFFFFF; font-weight: 700; "
            "border: none; border-radius: 6px; padding: 7px 20px; font-size: 12px; } "
            "QPushButton:hover { background: #0F2342; }"
        )
        save.clicked.connect(self._save)

        btns.addWidget(cancel)
        btns.addWidget(save)
        v.addLayout(btns)

    def _save(self):
        if not self._worker_ids:
            QMessageBox.warning(self, "Error", "No worker selected.")
            return
        worker_id = self._worker_ids[self.f_worker.currentIndex()]
        qd = self.f_date.date()
        adj_date = date(qd.year(), qd.month(), qd.day())
        amount = self.f_amount.value()
        if amount <= 0:
            QMessageBox.warning(self, "Validation Error", "Amount must be greater than 0.")
            return

        adj_type = "ADDITION" if self.f_type.currentIndex() == 0 else "DEDUCTION"

        self._data = {
            "worker_id": worker_id,
            "date": adj_date,
            "amount": amount,
            "type": adj_type,
            "category": self.f_category.currentText().strip() or "Bonus",
            "notes": self.f_notes.text().strip(),
        }
        self.accept()

    def get_data(self) -> dict:
        return getattr(self, "_data", {})


# ===========================================================================
# Dialog 5: Settle Month / Record Final Payment
# ===========================================================================

class SettlementDialog(QDialog):
    """Dialog to confirm and record monthly settlement payment."""

    def __init__(self, parent=None, summary=None):
        super().__init__(parent)
        self.summary = summary or {}
        self.setWindowTitle("Settle Month & Record Payment")
        self.setMinimumWidth(440)
        self.resize(460, 420)

        v = QVBoxLayout(self)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(14)

        title = QLabel(f"💰 Settle Month — {self.summary.get('name', 'Worker')}")
        title.setStyleSheet("font-size: 16px; font-weight: 800; color: #173560;")
        v.addWidget(title)

        # Overview Card
        box = QFrame()
        box.setStyleSheet("background: #F8FAFC; border: 1px solid #CBD5E1; border-radius: 8px; padding: 12px;")
        b_lay = QGridLayout(box)
        b_lay.setVerticalSpacing(6)

        def _row(row_idx, label, val_str, color="#0F172A", bold=False):
            l = QLabel(label)
            l.setStyleSheet(f"font-size: 12px; color: #475569; {'font-weight:700;' if bold else ''}")
            vl = QLabel(val_str)
            vl.setAlignment(Qt.AlignRight)
            vl.setStyleSheet(f"font-size: 12px; color: {color}; {'font-weight:800;' if bold else 'font-weight:600;'}")
            b_lay.addWidget(l, row_idx, 0)
            b_lay.addWidget(vl, row_idx, 1)

        _row(0, "Month:", f"{self.summary.get('month_name', '')} {self.summary.get('year', '')}")
        _row(1, "Total Work Earnings:", _money(self.summary.get("total_work_earning", 0)))
        _row(2, "(+) Travel Expenses:", f"+ {_money(self.summary.get('total_travel', 0))}", color="#059669")
        _row(3, "(+) Other Additions:", f"+ {_money(self.summary.get('total_additions', 0))}", color="#059669")
        _row(4, "Gross Payable:", _money(self.summary.get("gross_payable", 0)), bold=True)
        _row(5, "(-) Advance Payments:", f"- {_money(self.summary.get('total_advance', 0))}", color="#DC2626")
        _row(6, "(-) Other Deductions:", f"- {_money(self.summary.get('total_deductions', 0))}", color="#DC2626")

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #94A3B8;")
        b_lay.addWidget(line, 7, 0, 1, 2)

        _row(8, "NET PAYABLE:", _money(self.summary.get("net_payable", 0)), color="#173560", bold=True)
        v.addWidget(box)

        form = QFormLayout()
        form.setVerticalSpacing(10)

        def _lab(t):
            l = QLabel(t)
            l.setStyleSheet("font-size: 11px; font-weight: 700; color: #475569;")
            return l

        net_val = float(self.summary.get("net_payable", 0))
        self.f_amount = QDoubleSpinBox()
        self.f_amount.setRange(0, 1000000)
        self.f_amount.setPrefix("₹ ")
        self.f_amount.setValue(max(0.0, net_val))

        self.f_method = QComboBox()
        self.f_method.addItems(["Cash", "UPI", "Bank", "Other"])

        self.f_notes = QLineEdit()
        self.f_notes.setText(f"Final settlement for {self.summary.get('month_name', '')} {self.summary.get('year', '')}")

        form.addRow(_lab("Payment Amount *"), self.f_amount)
        form.addRow(_lab("Payment Method"), self.f_method)
        form.addRow(_lab("Notes"), self.f_notes)
        v.addLayout(form)

        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(
            "QPushButton { background: #F1F5F9; color: #475569; font-weight: 600; "
            "border: 1px solid #CBD5E1; border-radius: 6px; padding: 7px 16px; font-size: 12px; }"
        )
        cancel.clicked.connect(self.reject)

        save = QPushButton("Confirm Settlement")
        save.setStyleSheet(
            "QPushButton { background: #173560; color: #FFFFFF; font-weight: 700; "
            "border: none; border-radius: 6px; padding: 7px 20px; font-size: 12px; } "
            "QPushButton:hover { background: #0F2342; }"
        )
        save.clicked.connect(self._save)

        btns.addWidget(cancel)
        btns.addWidget(save)
        v.addLayout(btns)

    def _save(self):
        self._data = {
            "paid_amount": self.f_amount.value(),
            "method": self.f_method.currentText(),
            "notes": self.f_notes.text().strip(),
        }
        self.accept()

    def get_data(self) -> dict:
        return getattr(self, "_data", {})


# ===========================================================================
# Dialog 6: Formatted Monthly Summary Slip & WhatsApp
# ===========================================================================

class MonthlySummarySlipDialog(QDialog):
    """Clean printable/preview salary card matching Master Prompt Section 16, with 1-click Photo Card Export."""

    def __init__(self, parent=None, summary=None, business_name=""):
        super().__init__(parent)
        self.summary = summary or {}
        self.business_name = business_name
        self.setWindowTitle(f"Salary Slip Card — {self.summary.get('name', 'Worker')}")
        self.resize(680, 820)
        self.setMinimumWidth(640)

        main_v = QVBoxLayout(self)
        main_v.setContentsMargins(18, 16, 18, 16)
        main_v.setSpacing(12)

        # Scroll area in case screen height is compact
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        scroll_content = QWidget()
        sc_lay = QVBoxLayout(scroll_content)
        sc_lay.setContentsMargins(4, 4, 4, 4)
        sc_lay.setAlignment(Qt.AlignHCenter)

        # -------------------------------------------------------------
        # THE SALARY CARD (This widget gets captured as photo/PNG)
        # -------------------------------------------------------------
        self.slip_card = QFrame()
        self.slip_card.setObjectName("workerSalaryCard")
        self.slip_card.setFixedWidth(600)
        self.slip_card.setStyleSheet("""
            QFrame#workerSalaryCard {
                background: #FFFFFF;
                border: 2px solid #CBD5E1;
                border-radius: 12px;
            }
        """)

        card_lay = QVBoxLayout(self.slip_card)
        card_lay.setContentsMargins(16, 16, 16, 16)
        card_lay.setSpacing(10)

        # 1. Royal Header Banner
        header = QFrame()
        header.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #173560, stop:1 #1E4B85);
            border-radius: 8px;
            padding: 12px 16px;
        """)
        h_lay = QVBoxLayout(header)
        h_lay.setSpacing(3)
        h_lay.setContentsMargins(0, 0, 0, 0)

        shop_name = self.business_name.strip() or "FURNITURE WORKSHOP"
        lbl_shop = QLabel(shop_name.upper())
        lbl_shop.setStyleSheet("font-size: 16px; font-weight: 800; color: #F59E0B; letter-spacing: 0.5px;")

        top_row = QHBoxLayout()
        lbl_title = QLabel("WORKER SALARY & ATTENDANCE SLIP")
        lbl_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #FFFFFF;")

        m_name = self.summary.get("month_name", "")
        yr = self.summary.get("year", "")
        lbl_month_badge = QLabel(f"📅 {m_name} {yr}")
        lbl_month_badge.setStyleSheet("""
            background: #FFFFFF; color: #173560; font-size: 11px; font-weight: 800;
            border-radius: 4px; padding: 2px 8px;
        """)
        top_row.addWidget(lbl_title)
        top_row.addStretch(1)
        top_row.addWidget(lbl_month_badge)

        h_lay.addWidget(lbl_shop)
        h_lay.addLayout(top_row)
        card_lay.addWidget(header)

        # 2. Worker Profile Strip
        prof = QFrame()
        prof.setStyleSheet("background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 10px 14px;")
        p_lay = QGridLayout(prof)
        p_lay.setContentsMargins(0, 0, 0, 0)
        p_lay.setHorizontalSpacing(16)
        p_lay.setVerticalSpacing(4)

        w_name = self.summary.get("name", "")
        w_code = self.summary.get("worker_code", "")
        w_role = self.summary.get("work_type", "Mistri")
        rate = self.summary.get("current_daily_rate", 0)

        l_name = QLabel(f"👤 {w_name}")
        l_name.setStyleSheet("font-size: 15px; font-weight: 800; color: #1E293B;")
        s_no = self.summary.get("serial_no")
        s_str = f"S.No.: <b>{s_no}</b> | " if s_no else ""
        l_code = QLabel(f"{s_str}Role: <b>{w_role}</b>")
        l_code.setStyleSheet("font-size: 12px; color: #64748B;")

        l_rate = QLabel(f"Daily Rate (Pagar): <b style='color:#173560;'>{_money(rate)}/day</b>")
        l_rate.setStyleSheet("font-size: 12px; color: #475569;")
        l_rate.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        p_lay.addWidget(l_name, 0, 0)
        p_lay.addWidget(l_rate, 0, 1)
        p_lay.addWidget(l_code, 1, 0)

        card_lay.addWidget(prof)

        # 2b. Calculation Formula Banner
        tot_u = self.summary.get("total_units", 0)
        earn_amt = self.summary.get("total_work_earning", 0)
        calc_bar = QFrame()
        calc_bar.setStyleSheet("background: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 6px; padding: 6px 12px;")
        cb_lay = QHBoxLayout(calc_bar)
        cb_lay.setContentsMargins(0, 0, 0, 0)
        lbl_formula = QLabel(f"🧮 <b>Calculation:</b> {tot_u:.1f} Days × {_money(rate)}/day = <b style='color:#1E40AF;'>{_money(earn_amt)}</b>")
        lbl_formula.setStyleSheet("font-size: 11px; color: #1E3A8A;")
        cb_lay.addWidget(lbl_formula)
        card_lay.addWidget(calc_bar)

        # 3. Attendance Badges Grid
        att_frame = QFrame()
        att_frame.setStyleSheet("background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 8px 12px;")
        af_lay = QVBoxLayout(att_frame)
        af_lay.setContentsMargins(0, 0, 0, 0)
        af_lay.setSpacing(6)

        af_title = QLabel("ATTENDANCE SUMMARY")
        af_title.setStyleSheet("font-size: 10px; font-weight: 800; color: #64748B; letter-spacing: 0.5px;")
        af_lay.addWidget(af_title)

        pills_row = QHBoxLayout()
        pills_row.setSpacing(6)

        def _pill(lbl, val, bg, fg):
            p = QLabel(f"{lbl}: <b>{val}</b>")
            p.setStyleSheet(f"background: {bg}; color: {fg}; font-size: 11px; font-weight: 700; border-radius: 4px; padding: 4px 8px;")
            p.setAlignment(Qt.AlignCenter)
            return p

        pills_row.addWidget(_pill("Full (1.0)", self.summary.get("full_days", 0), "#ECFDF5", "#059669"))
        pills_row.addWidget(_pill("Half (0.5)", self.summary.get("half_days", 0), "#E0F2FE", "#0284C7"))
        pills_row.addWidget(_pill("1.5 Day", self.summary.get("one_and_half_days", 0), "#F5F3FF", "#7C3AED"))
        pills_row.addWidget(_pill("Double (2.0)", self.summary.get("double_days", 0), "#FEF3C7", "#D97706"))
        pills_row.addWidget(_pill("Absent", self.summary.get("absent_days", 0), "#FEF2F2", "#DC2626"))

        pills_row.addWidget(_pill("Total Units", f"{tot_u:.1f} D", "#EFF6FF", "#1E40AF"))
        af_lay.addLayout(pills_row)
        card_lay.addWidget(att_frame)

        # 4. Earnings & Reimbursals Card
        earn_frame = QFrame()
        earn_frame.setStyleSheet("background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 10px 14px;")
        ef_lay = QVBoxLayout(earn_frame)
        ef_lay.setContentsMargins(0, 0, 0, 0)
        ef_lay.setSpacing(6)

        ef_title = QLabel("EARNINGS & TRAVEL REIMBURSEMENT")
        ef_title.setStyleSheet("font-size: 10px; font-weight: 800; color: #64748B; letter-spacing: 0.5px;")
        ef_lay.addWidget(ef_title)

        eg = QGridLayout()
        eg.setVerticalSpacing(4)

        def _erow(row_idx, label, val_str, color="#1E293B", bold=False):
            l = QLabel(label)
            l.setStyleSheet(f"font-size: 12px; color: #475569; {'font-weight:700;' if bold else ''}")
            v = QLabel(val_str)
            v.setAlignment(Qt.AlignRight)
            v.setStyleSheet(f"font-size: 12px; color: {color}; {'font-weight:800;' if bold else 'font-weight:600;'}")
            eg.addWidget(l, row_idx, 0)
            eg.addWidget(v, row_idx, 1)

        _erow(0, f"Work Earnings ({tot_u:.1f} Days × {_money(rate)}):", _money(self.summary.get("total_work_earning", 0)))

        travel_amt = self.summary.get("total_travel", 0)
        _erow(1, "(+) Travel / Rickshaw Expense:", f"+ {_money(travel_amt)}", color="#059669")

        add_amt = self.summary.get("total_additions", 0)
        if add_amt > 0:
            _erow(2, "(+) Bonus / Other Additions:", f"+ {_money(add_amt)}", color="#059669")

        _erow(3, "Gross Payable Amount:", _money(self.summary.get("gross_payable", 0)), color="#173560", bold=True)
        ef_lay.addLayout(eg)

        # Travel breakdown box
        travel_list = self.summary.get("travel_expenses", [])
        if travel_list:
            t_box = QFrame()
            t_box.setStyleSheet("background: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 6px; padding: 6px 10px;")
            tb_lay = QVBoxLayout(t_box)
            tb_lay.setContentsMargins(0, 0, 0, 0)
            tb_lay.setSpacing(3)
            tb_hdr = QLabel("<b>Travel / Rickshaw Breakdown:</b>")
            tb_hdr.setStyleSheet("font-size: 10px; font-weight: 700; color: #166534;")
            tb_lay.addWidget(tb_hdr)
            for e in travel_list:
                desc = f"• {e['date_str']}: <b>{_money(e['amount'])}</b> — {e['category']}"
                if e['notes']:
                    desc += f" <i>({e['notes']})</i>"
                el = QLabel(desc)
                el.setStyleSheet("font-size: 10px; color: #15803D;")
                tb_lay.addWidget(el)
            ef_lay.addWidget(t_box)

        card_lay.addWidget(earn_frame)

        # 5. Advances & Deductions Card
        adv_frame = QFrame()
        adv_frame.setStyleSheet("background: #FEF2F2; border: 1px solid #FECACA; border-radius: 8px; padding: 10px 14px;")
        av_lay = QVBoxLayout(adv_frame)
        av_lay.setContentsMargins(0, 0, 0, 0)
        av_lay.setSpacing(6)

        av_title = QLabel("ADVANCES & DEDUCTIONS")
        av_title.setStyleSheet("font-size: 10px; font-weight: 800; color: #991B1B; letter-spacing: 0.5px;")
        av_lay.addWidget(av_title)

        avg = QGridLayout()
        avg.setVerticalSpacing(4)

        def _arow(row_idx, label, val_str):
            l = QLabel(label)
            l.setStyleSheet("font-size: 12px; color: #7F1D1D;")
            v = QLabel(val_str)
            v.setAlignment(Qt.AlignRight)
            v.setStyleSheet("font-size: 12px; color: #DC2626; font-weight: 700;")
            avg.addWidget(l, row_idx, 0)
            avg.addWidget(v, row_idx, 1)

        tot_adv = self.summary.get("total_advance", 0)
        _arow(0, "(-) Advance Payments Taken:", f"- {_money(tot_adv)}")

        tot_ded = self.summary.get("total_deductions", 0)
        if tot_ded > 0:
            _arow(1, "(-) Other Deductions:", f"- {_money(tot_ded)}")

        av_lay.addLayout(avg)

        # Advances breakdown box
        adv_list = self.summary.get("advances", [])
        if adv_list:
            adv_box = QFrame()
            adv_box.setStyleSheet("background: #FFF1F2; border: 1px solid #FECDD3; border-radius: 6px; padding: 6px 10px;")
            ab_lay = QVBoxLayout(adv_box)
            ab_lay.setContentsMargins(0, 0, 0, 0)
            ab_lay.setSpacing(3)
            ab_hdr = QLabel("<b>Advances Taken Breakdown:</b>")
            ab_hdr.setStyleSheet("font-size: 10px; font-weight: 700; color: #9F1239;")
            ab_lay.addWidget(ab_hdr)
            for a in adv_list:
                adesc = f"• {a['date_str']}: <b>{_money(a['amount'])}</b> via <b>{a['payment_method']}</b>"
                if a['notes']:
                    adesc += f" <i>({a['notes']})</i>"
                al = QLabel(adesc)
                al.setStyleSheet("font-size: 10px; color: #BE123C;")
                ab_lay.addWidget(al)
            av_lay.addWidget(adv_box)

        card_lay.addWidget(adv_frame)

        # 5b. Adjustments Breakdown (if any)
        adj_list = self.summary.get("adjustments", [])
        if adj_list:
            adj_box = QFrame()
            adj_box.setStyleSheet("background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 10px 14px;")
            ajb_lay = QVBoxLayout(adj_box)
            ajb_lay.setContentsMargins(0, 0, 0, 0)
            ajb_lay.setSpacing(4)
            ajb_hdr = QLabel("<b>OTHER ADJUSTMENTS BREAKDOWN:</b>")
            ajb_hdr.setStyleSheet("font-size: 10px; font-weight: 800; color: #334155; letter-spacing: 0.5px;")
            ajb_lay.addWidget(ajb_hdr)
            for j in adj_list:
                sign = "+" if j["type"] == "ADDITION" else "-"
                clr = "#15803D" if j["type"] == "ADDITION" else "#BE123C"
                jdesc = f"• {j['date_str']}: <b>{sign} {_money(j['amount'])}</b> — {j['category']}"
                if j['notes']:
                    jdesc += f" <i>({j['notes']})</i>"
                jl = QLabel(jdesc)
                jl.setStyleSheet(f"font-size: 10px; color: {clr}; font-weight: 600;")
                ajb_lay.addWidget(jl)
            card_lay.addWidget(adj_box)

        # 6. Hero Net Payable Box (The Star of the Card)
        hero = QFrame()
        hero.setStyleSheet("""
            background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #064E3B, stop:1 #047857);
            border: 2px solid #10B981;
            border-radius: 8px;
            padding: 12px 16px;
        """)
        hero_lay = QHBoxLayout(hero)
        hero_lay.setContentsMargins(0, 0, 0, 0)

        hl_box = QVBoxLayout()
        hl_box.setSpacing(2)
        hl_title = QLabel("FINAL NET PAYABLE AMOUNT")
        hl_title.setStyleSheet("font-size: 11px; font-weight: 800; color: #A7F3D0; letter-spacing: 0.5px;")

        status_text = "✓ PAID IN FULL" if self.summary.get("is_settled") else "⏳ PENDING PAYMENT"
        hl_sub = QLabel(f"Status: {status_text}")
        hl_sub.setStyleSheet("font-size: 10px; font-weight: 700; color: #FFFFFF;")
        hl_box.addWidget(hl_title)
        hl_box.addWidget(hl_sub)

        net_val = self.summary.get("net_payable", 0)
        hr_val = QLabel(_money(net_val))
        hr_val.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        hr_val.setStyleSheet("font-size: 24px; font-weight: 900; color: #FFFFFF; letter-spacing: -0.5px;")

        hero_lay.addLayout(hl_box)
        hero_lay.addStretch(1)
        hero_lay.addWidget(hr_val)
        card_lay.addWidget(hero)

        # 7. Verification Seal Strip
        seal = QHBoxLayout()
        now_str = datetime.now().strftime("%d-%b-%Y %I:%M %p")
        lbl_verified = QLabel(f"✔ Verified & Generated via Furniture Bill Software • {now_str}")
        lbl_verified.setStyleSheet("font-size: 9px; color: #94A3B8;")
        seal.addWidget(lbl_verified)
        seal.addStretch(1)
        card_lay.addLayout(seal)

        sc_lay.addWidget(self.slip_card)
        scroll.setWidget(scroll_content)
        main_v.addWidget(scroll, 1)

        # -------------------------------------------------------------
        # Action Bar (Save Image / Copy to Clipboard / WhatsApp)
        # -------------------------------------------------------------
        actions = QHBoxLayout()
        actions.setSpacing(10)

        btn_save_img = QPushButton("📸 Save Image (PNG / Photo)")
        btn_save_img.setCursor(Qt.PointingHandCursor)
        btn_save_img.setStyleSheet("""
            QPushButton { background: #173560; color: #FFFFFF; font-weight: 700;
            border: none; border-radius: 6px; padding: 9px 16px; font-size: 12px; }
            QPushButton:hover { background: #0F2342; }
        """)
        btn_save_img.clicked.connect(self._save_as_image)
        actions.addWidget(btn_save_img)

        btn_copy_img = QPushButton("📋 Copy Image (Ctrl+V in WhatsApp)")
        btn_copy_img.setCursor(Qt.PointingHandCursor)
        btn_copy_img.setStyleSheet("""
            QPushButton { background: #059669; color: #FFFFFF; font-weight: 700;
            border: none; border-radius: 6px; padding: 9px 16px; font-size: 12px; }
            QPushButton:hover { background: #047857; }
        """)
        btn_copy_img.clicked.connect(self._copy_image_to_clipboard)
        actions.addWidget(btn_copy_img)

        btn_wa = QPushButton("💬 Send on WhatsApp (Text)")
        btn_wa.setCursor(Qt.PointingHandCursor)
        btn_wa.setStyleSheet("""
            QPushButton { background: #25D366; color: #FFFFFF; font-weight: 700;
            border: none; border-radius: 6px; padding: 9px 16px; font-size: 12px; }
            QPushButton:hover { background: #1EBE5D; }
        """)
        btn_wa.clicked.connect(self._send_wa)
        actions.addWidget(btn_wa)

        actions.addStretch(1)

        btn_close = QPushButton("Close")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.setStyleSheet("""
            QPushButton { background: #F1F5F9; color: #475569; font-weight: 600;
            border: 1px solid #CBD5E1; border-radius: 6px; padding: 9px 16px; font-size: 12px; }
            QPushButton:hover { background: #E2E8F0; }
        """)
        btn_close.clicked.connect(self.accept)
        actions.addWidget(btn_close)

        main_v.addLayout(actions)

    def _render_card_pixmap(self) -> QPixmap:
        """Render high-resolution 2x super-sampled card for WhatsApp photo sharing and export."""
        self.slip_card.adjustSize()
        size = self.slip_card.size()
        dpr = 2.0  # 2x Retina super-sampling for HD photo quality
        pix = QPixmap(int(size.width() * dpr), int(size.height() * dpr))
        pix.setDevicePixelRatio(dpr)
        pix.fill(Qt.white)
        self.slip_card.render(pix)
        return pix

    def _save_as_image(self):
        pixmap = self._render_card_pixmap()
        w_code = self.summary.get("worker_code", "Worker")
        w_name = self.summary.get("name", "").replace(" ", "_")
        m_name = self.summary.get("month_name", "Month")
        yr = self.summary.get("year", "2026")
        default_filename = f"Salary_Card_{w_code}_{w_name}_{m_name}_{yr}.png"

        fname, _ = QFileDialog.getSaveFileName(
            self,
            "Save Worker Salary Card as Image",
            default_filename,
            "PNG Image (*.png);;JPEG Image (*.jpg)"
        )
        if fname:
            success = pixmap.save(fname)
            if success:
                QMessageBox.information(
                    self,
                    "Image Saved Successfully",
                    f"Salary card image has been saved to:\n{fname}\n\nYou can now share this photo with the worker."
                )

    def _copy_image_to_clipboard(self):
        pixmap = self._render_card_pixmap()
        clipboard = QGuiApplication.clipboard()
        clipboard.setPixmap(pixmap)
        QMessageBox.information(
            self,
            "Card Image Copied!",
            "Salary card photo has been copied to your clipboard!\n\n"
            "Now open WhatsApp Web or Desktop, click on the worker's chat, and press Ctrl + V to paste and send the photo directly."
        )

    def _send_wa(self):
        worker_id = self.summary.get("worker_id")
        year = self.summary.get("year")
        month = self.summary.get("month")
        if not worker_id:
            return
        text = worker_service.generate_whatsapp_summary_text(worker_id, year, month, self.business_name)
        mobile = (self.summary.get("mobile") or "").replace("+", "").replace("-", "").replace(" ", "").strip()
        if mobile and len(mobile) == 10:
            mobile = f"91{mobile}"
        url = f"https://wa.me/{mobile}?text={quote(text)}" if mobile else f"https://wa.me/?text={quote(text)}"
        QDesktopServices.openUrl(QUrl(url))


# ===========================================================================
# Dialog 7b: Edit a Single Day's Record (Attendance + Travel + Advance)
# ===========================================================================

class DailyRecordEditDialog(QDialog):
    """Edit attendance, travel expense, and advance for a specific worker-date."""

    def __init__(self, parent=None, worker_id: int = 0, worker_name: str = "",
                 att_date: date = None, existing: dict = None):
        super().__init__(parent)
        self.worker_id = worker_id
        self.att_date = att_date
        self.existing = existing or {}
        self.setWindowTitle(f"Edit Record — {worker_name} | {att_date.strftime('%d %b %Y') if att_date else ''}")
        self.setMinimumWidth(500)
        self.resize(520, 520)

        v = QVBoxLayout(self)
        v.setContentsMargins(20, 16, 20, 16)
        v.setSpacing(12)

        # Header
        hdr = QLabel(f"Edit Daily Record")
        hdr.setStyleSheet("font-size: 15px; font-weight: 800; color: #173560;")
        v.addWidget(hdr)
        sub = QLabel(f"Worker: <b>{worker_name}</b>   |   Date: <b>{att_date.strftime('%d %b %Y') if att_date else ''}</b>")
        sub.setStyleSheet("font-size: 11px; color: #64748B;")
        v.addWidget(sub)

        # Separator
        sep = QFrame(); sep.setFrameShape(QFrame.HLine)
        sep.setStyleSheet("color: #E2E8F0;"); v.addWidget(sep)

        form = QFormLayout()
        form.setVerticalSpacing(10)

        def _lab(t):
            l = QLabel(t)
            l.setStyleSheet("font-size: 11px; font-weight: 700; color: #475569;")
            return l

        # 1. Attendance
        self.f_status = QComboBox()
        self.f_status.addItem("-- No Change (keep existing) --", None)
        self.f_status.addItem("Full Day (1.0)", 1.0)
        self.f_status.addItem("Half Day (0.5)", 0.5)
        self.f_status.addItem("1.5 Day (Dedhi)", 1.5)
        self.f_status.addItem("Double Day (2.0)", 2.0)
        self.f_status.addItem("Absent (0.0)", 0.0)
        # Pre-select current
        cur_mult = self.existing.get("att_multiplier")
        if cur_mult is not None:
            for i in range(self.f_status.count()):
                if self.f_status.itemData(i) is not None and abs(self.f_status.itemData(i) - cur_mult) < 0.01:
                    self.f_status.setCurrentIndex(i)
                    break
        form.addRow(_lab("Attendance Status:"), self.f_status)

        self.f_att_note = QLineEdit(self.existing.get("att_notes", ""))
        self.f_att_note.setPlaceholderText("Attendance note (optional)")
        form.addRow(_lab("Attendance Note:"), self.f_att_note)

        v.addLayout(form)

        # 2. Travel Card
        trv_card = QFrame()
        trv_card.setStyleSheet("background:#ECFDF5; border:1px solid #A7F3D0; border-radius:8px; padding:10px 12px;")
        tc = QVBoxLayout(trv_card)
        tc.setContentsMargins(0,0,0,0); tc.setSpacing(6)
        tc.addWidget(QLabel("Travel / Rickshaw Expense (optional)"))
        tc.children()[0].widget().setStyleSheet("font-size:11px;font-weight:800;color:#059669;")

        trv_row = QHBoxLayout(); trv_row.setSpacing(8)
        self.f_trv = QDoubleSpinBox()
        self.f_trv.setRange(0, 100000); self.f_trv.setPrefix("Rs. ")
        self.f_trv.setValue(self.existing.get("travel_amount", 0.0))
        trv_row.addWidget(self.f_trv, 2)
        self.f_trv_cat = QComboBox(); self.f_trv_cat.setEditable(True)
        self.f_trv_cat.addItems(["Rickshaw", "Travel", "Bus", "Site travel", "Other"])
        trv_row.addWidget(self.f_trv_cat, 2)
        self.f_trv_note = QLineEdit(self.existing.get("travel_notes", ""))
        self.f_trv_note.setPlaceholderText("Trip or site details...")
        trv_row.addWidget(self.f_trv_note, 3)
        tc.addLayout(trv_row)
        v.addWidget(trv_card)

        # 3. Advance Card
        adv_card = QFrame()
        adv_card.setStyleSheet("background:#FEF2F2; border:1px solid #FECACA; border-radius:8px; padding:10px 12px;")
        ac = QVBoxLayout(adv_card)
        ac.setContentsMargins(0,0,0,0); ac.setSpacing(6)
        ac.addWidget(QLabel("Advance Payment (optional)"))
        ac.children()[0].widget().setStyleSheet("font-size:11px;font-weight:800;color:#DC2626;")

        adv_row = QHBoxLayout(); adv_row.setSpacing(8)
        self.f_adv = QDoubleSpinBox()
        self.f_adv.setRange(0, 1000000); self.f_adv.setPrefix("Rs. ")
        self.f_adv.setValue(0.0)
        adv_row.addWidget(self.f_adv, 2)
        self.f_adv_method = QComboBox()
        self.f_adv_method.addItems(["Cash", "UPI", "Bank", "Other"])
        adv_row.addWidget(self.f_adv_method, 1)
        self.f_adv_note = QLineEdit()
        self.f_adv_note.setPlaceholderText("Reason: festival, grocery...")
        adv_row.addWidget(self.f_adv_note, 3)
        ac.addLayout(adv_row)
        v.addWidget(adv_card)

        # Buttons
        v.addStretch(1)
        btns = QHBoxLayout()
        btns.addStretch(1)
        btn_cancel = QPushButton("Cancel")
        btn_cancel.setStyleSheet("background:#F1F5F9;color:#475569;font-weight:600;border:1px solid #CBD5E1;border-radius:6px;padding:7px 18px;")
        btn_cancel.clicked.connect(self.reject)
        btn_save = QPushButton("Save Changes")
        btn_save.setStyleSheet("background:#173560;color:#FFFFFF;font-weight:800;border:none;border-radius:6px;padding:7px 22px;")
        btn_save.clicked.connect(self._save)
        btns.addWidget(btn_cancel)
        btns.addWidget(btn_save)
        v.addLayout(btns)

    def _save(self):
        mult = self.f_status.currentData()
        self._result = {
            "att_multiplier": mult,
            "att_notes": self.f_att_note.text().strip(),
            "travel_amount": self.f_trv.value(),
            "travel_category": self.f_trv_cat.currentText().strip() or "Rickshaw",
            "travel_notes": self.f_trv_note.text().strip(),
            "advance_amount": self.f_adv.value(),
            "advance_method": self.f_adv_method.currentText(),
            "advance_notes": self.f_adv_note.text().strip(),
        }
        self.accept()

    def get_result(self) -> dict:
        return getattr(self, "_result", {})


# ===========================================================================
# Dialog 7: Quick All-in-One Attendance & Daily Expense Entry
# ===========================================================================

class AttendanceEntryDialog(QDialog):
    """Fast, all-in-one dialog to mark daily attendance, advance payment, and travel expense."""

    def __init__(self, parent=None, workers=None, preselected_worker_id=None, default_date: date | None = None):
        super().__init__(parent)
        self.setWindowTitle("➕ Add Attendance Entry")
        self.setMinimumWidth(540)
        self.resize(560, 600)
        self.workers = workers or []
        self._worker_map = {w.id: w for w in self.workers}

        v = QVBoxLayout(self)
        v.setContentsMargins(20, 20, 20, 20)
        v.setSpacing(12)

        title = QLabel("➕ Add Daily Attendance & Expenses")
        title.setStyleSheet("font-size: 16px; font-weight: 800; color: #173560;")
        v.addWidget(title)

        hint = QLabel("Select worker & date, then record attendance, advance, and travel expense — all in one step.")
        hint.setStyleSheet("font-size: 11px; color: #64748B;")
        v.addWidget(hint)

        form = QFormLayout()
        form.setVerticalSpacing(10)

        def _lab(t):
            l = QLabel(t)
            l.setStyleSheet("font-size: 11px; font-weight: 700; color: #475569;")
            return l

        # 1. Date Selection
        self.f_date = QDateEdit()
        self.f_date.setCalendarPopup(True)
        self.f_date.setMaximumDate(QDate.currentDate())  # No future dates allowed
        if default_date:
            # Clamp to today if someone passes a future date
            clamped = min(default_date, date.today())
            self.f_date.setDate(QDate(clamped.year, clamped.month, clamped.day))
        else:
            self.f_date.setDate(QDate.currentDate())
        form.addRow(_lab("Date *"), self.f_date)

        # 2. Worker Selection
        self.f_worker = QComboBox()
        for idx, w in enumerate(self.workers, 1):
            self.f_worker.addItem(f"{idx}. {w.name} ({w.work_type})", w.id)

        if preselected_worker_id:
            idx = self.f_worker.findData(preselected_worker_id)
            if idx >= 0:
                self.f_worker.setCurrentIndex(idx)

        self.f_worker.currentIndexChanged.connect(self._on_worker_changed)
        form.addRow(_lab("Worker *"), self.f_worker)

        # 3. Live Rate Information Banner
        self.lbl_rate_banner = QLabel("")
        self.lbl_rate_banner.setWordWrap(True)
        self.lbl_rate_banner.setStyleSheet("""
            background: #EFF6FF; border: 1px solid #BFDBFE; border-radius: 6px;
            padding: 8px 12px; font-size: 12px; color: #1E40AF; font-weight: 700;
        """)
        form.addRow("", self.lbl_rate_banner)

        # 4. Attendance Status
        self.f_status = QComboBox()
        self.f_status.addItem("✓ Full Day (1.0)", 1.0)
        self.f_status.addItem("½ Half Day (0.5)", 0.5)
        self.f_status.addItem("⭐ 1.5 Day (Dedhi)", 1.5)
        self.f_status.addItem("⚡ Double Day (2.0)", 2.0)
        self.f_status.addItem("❌ Absent (0.0)", 0.0)
        form.addRow(_lab("Attendance *"), self.f_status)

        # 5. Work Note
        self.f_att_notes = QLineEdit()
        self.f_att_notes.setPlaceholderText("Work details, site name, or any note (Optional)")
        form.addRow(_lab("Work Note"), self.f_att_notes)

        v.addLayout(form)

        # 6. Advance Section (Card)
        adv_card = QFrame()
        adv_card.setStyleSheet("background: #FEF2F2; border: 1px solid #FECACA; border-radius: 8px; padding: 10px 12px;")
        ac_lay = QVBoxLayout(adv_card)
        ac_lay.setContentsMargins(0, 0, 0, 0)
        ac_lay.setSpacing(6)

        lbl_adv_head = QLabel("💵 Did you give Advance today? (Optional)")
        lbl_adv_head.setStyleSheet("font-size: 11px; font-weight: 800; color: #DC2626;")
        ac_lay.addWidget(lbl_adv_head)

        adv_row = QHBoxLayout()
        adv_row.setSpacing(8)

        self.f_adv_amount = QDoubleSpinBox()
        self.f_adv_amount.setRange(0, 1000000)
        self.f_adv_amount.setPrefix("₹ ")
        self.f_adv_amount.setValue(0.0)
        adv_row.addWidget(self.f_adv_amount, 2)

        self.f_adv_method = QComboBox()
        self.f_adv_method.addItems(["Cash", "UPI", "Bank", "Other"])
        adv_row.addWidget(self.f_adv_method, 1)

        self.f_adv_note = QLineEdit()
        self.f_adv_note.setPlaceholderText("Reason: Festival, grocery, personal...")
        adv_row.addWidget(self.f_adv_note, 3)

        ac_lay.addLayout(adv_row)
        v.addWidget(adv_card)

        # 7. Travel Section (Card)
        trv_card = QFrame()
        trv_card.setStyleSheet("background: #ECFDF5; border: 1px solid #A7F3D0; border-radius: 8px; padding: 10px 12px;")
        tc_lay = QVBoxLayout(trv_card)
        tc_lay.setContentsMargins(0, 0, 0, 0)
        tc_lay.setSpacing(6)

        lbl_trv_head = QLabel("🛵 Any travel / rickshaw expense today? (Optional)")
        lbl_trv_head.setStyleSheet("font-size: 11px; font-weight: 800; color: #059669;")
        tc_lay.addWidget(lbl_trv_head)

        trv_row = QHBoxLayout()
        trv_row.setSpacing(8)

        self.f_trv_amount = QDoubleSpinBox()
        self.f_trv_amount.setRange(0, 100000)
        self.f_trv_amount.setPrefix("₹ ")
        self.f_trv_amount.setValue(0.0)
        trv_row.addWidget(self.f_trv_amount, 2)

        self.f_trv_cat = QComboBox()
        self.f_trv_cat.setEditable(True)
        self.f_trv_cat.addItems(["Rickshaw", "Travel", "Bus", "Site travel", "Other"])
        trv_row.addWidget(self.f_trv_cat, 2)

        self.f_trv_note = QLineEdit()
        self.f_trv_note.setPlaceholderText("Trip or site details...")
        trv_row.addWidget(self.f_trv_note, 3)

        tc_lay.addLayout(trv_row)
        v.addWidget(trv_card)

        # Buttons
        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(
            "QPushButton { background: #F1F5F9; color: #475569; font-weight: 600; "
            "border: 1px solid #CBD5E1; border-radius: 6px; padding: 8px 18px; font-size: 12px; } "
            "QPushButton:hover { background: #E2E8F0; }"
        )
        cancel.clicked.connect(self.reject)

        save = QPushButton("✓ Save Attendance")
        save.setStyleSheet(
            "QPushButton { background: #173560; color: #FFFFFF; font-weight: 800; "
            "border: none; border-radius: 6px; padding: 8px 24px; font-size: 12px; } "
            "QPushButton:hover { background: #0F2342; }"
        )
        save.clicked.connect(self._save)

        btns.addWidget(cancel)
        btns.addWidget(save)
        v.addLayout(btns)

        self._on_worker_changed()

    def _on_worker_changed(self):
        w_id = self.f_worker.currentData()
        w = self._worker_map.get(w_id)
        if w:
            rate_str = _money(w.daily_rate)
            self.lbl_rate_banner.setText(f"💰 Daily Rate: {rate_str} / day  |  Role: {w.work_type}")
        else:
            self.lbl_rate_banner.setText("Daily Rate: —")

    def _save(self):
        w_id = self.f_worker.currentData()
        if not w_id:
            QMessageBox.warning(self, "Validation Error", "Please select a worker.")
            return

        qd = self.f_date.date()
        att_d = date(qd.year(), qd.month(), qd.day())
        mult = float(self.f_status.currentData())
        status_lbl = self.f_status.currentText().split("(")[0].strip()

        self._data = {
            "worker_id": w_id,
            "date": att_d,
            "multiplier": mult,
            "status_label": status_lbl,
            "att_notes": self.f_att_notes.text().strip(),
            "advance_amount": self.f_adv_amount.value(),
            "advance_method": self.f_adv_method.currentText(),
            "advance_notes": self.f_adv_note.text().strip(),
            "travel_amount": self.f_trv_amount.value(),
            "travel_category": self.f_trv_cat.currentText().strip() or "Rickshaw",
            "travel_notes": self.f_trv_note.text().strip(),
        }
        self.accept()

    def get_data(self) -> dict:
        return getattr(self, "_data", {})


# ===========================================================================
# MAIN PAGE: WorkersPage
# ===========================================================================

class WorkersPage(BasePage):
    """Main Worker Attendance & Payment Management Workstation."""

    def __init__(self, main_window=None, parent=None):
        super().__init__(main_window, parent)
        self.setObjectName("workersPage")
        self._build_ui()

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 18, 24, 20)
        root.setSpacing(14)

        # 1. Top Executive KPI Ribbon
        kpi_ribbon = self._build_kpi_ribbon()
        root.addLayout(kpi_ribbon)

        # 2. Main Tabbed Workstation
        self.tabs = QTabWidget()
        self.tabs.setObjectName("workerTabs")
        self.tabs.setStyleSheet("""
            QTabWidget::pane { border: 1px solid #E2E8F0; background: #FFFFFF; border-radius: 8px; }
            QTabBar::tab { font-weight: 700; font-size: 12px; padding: 10px 18px; color: #475569; background: #F8FAFC; border: 1px solid #E2E8F0; border-bottom: none; border-top-left-radius: 6px; border-top-right-radius: 6px; margin-right: 4px; }
            QTabBar::tab:selected { color: #173560; background: #FFFFFF; border-bottom: 2px solid #173560; }
            QTabBar::tab:hover { color: #173560; background: #EDF2F7; }
        """)

        self.tab_directory = self._build_directory_tab()
        self.tab_attendance = self._build_attendance_tab()
        self.tab_history = self._build_history_tab()
        self.tab_settlement = self._build_settlement_tab()

        self.tabs.addTab(self.tab_directory, "👥 Worker List")
        self.tabs.addTab(self.tab_attendance, "⚡ Daily Attendance")
        self.tabs.addTab(self.tab_history, "📋 Monthly History")
        self.tabs.addTab(self.tab_settlement, "💵 Payments & Settlement")

        self.tabs.currentChanged.connect(self._on_tab_changed)
        root.addWidget(self.tabs, 1)

    # -------------------------------------------------------------------------
    # KPI Ribbon
    # -------------------------------------------------------------------------
    def _build_kpi_ribbon(self) -> QHBoxLayout:
        ribbon = QHBoxLayout()
        ribbon.setSpacing(10)

        cards = [
            ("total_workers", "TOTAL WORKERS", "Registered Staff", PRIMARY),
            ("active_workers", "ACTIVE WORKERS", "Available for Work", SUCCESS),
            ("month_work_cost", "MONTH WORK COST", "Earnings + Travel + Additions", "#2563EB"),
            ("advances_taken", "TOTAL ADVANCES", "Advances Deductible", DANGER),
            ("pending_payments", "PENDING NET DUE", "Pending Worker Payouts", GOLD),
        ]

        self.kpi_labels = {}
        for key, title, sub, accent in cards:
            c = QFrame()
            c.setObjectName("workerKpiCard")
            c.setStyleSheet(
                f"QFrame#workerKpiCard {{ background: #FFFFFF; border: 1px solid #E2E8F0; "
                f"border-top: 3.5px solid {accent}; border-radius: 8px; padding: 8px 12px; }}"
                f"QFrame#workerKpiCard:hover {{ border-color: {accent}; background: #F8FAFC; }}"
            )
            lay = QVBoxLayout(c)
            lay.setContentsMargins(2, 2, 2, 2)
            lay.setSpacing(2)

            lbl_t = QLabel(title)
            lbl_t.setStyleSheet("font-size: 9px; font-weight: 700; color: #64748B; letter-spacing: 0.5px;")

            lbl_v = QLabel("—")
            lbl_v.setStyleSheet(f"font-size: 16px; font-weight: 800; color: {accent}; letter-spacing: -0.2px;")

            lbl_s = QLabel(sub)
            lbl_s.setStyleSheet("font-size: 9px; color: #94A3B8;")

            lay.addWidget(lbl_t)
            lay.addWidget(lbl_v)
            lay.addWidget(lbl_s)

            ribbon.addWidget(c)
            self.kpi_labels[key] = lbl_v

        return ribbon

    # -------------------------------------------------------------------------
    # Tab 1: Worker List & Directory
    # -------------------------------------------------------------------------
    def _build_directory_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        # Toolbar
        tb = QHBoxLayout()
        tb.setSpacing(10)

        self.f_dir_search = QLineEdit()
        self.f_dir_search.setPlaceholderText("Search by Name, Mobile, Work Type...")
        self.f_dir_search.setFixedWidth(320)
        self.f_dir_search.textChanged.connect(self._load_directory_data)
        tb.addWidget(self.f_dir_search)

        self.cb_dir_type = QComboBox()
        self.cb_dir_type.addItems(["All Types", "Mistri", "Labour", "Carpenter", "Helper", "Painter", "Electrician", "Plumber", "Other"])
        self.cb_dir_type.currentIndexChanged.connect(self._load_directory_data)
        tb.addWidget(self.cb_dir_type)

        self.cb_dir_status = QComboBox()
        self.cb_dir_status.addItems(["All Status", "Active Only", "Inactive Only"])
        self.cb_dir_status.currentIndexChanged.connect(self._load_directory_data)
        tb.addWidget(self.cb_dir_status)

        tb.addStretch(1)

        btn_add = QPushButton("+ Add Worker")
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.setStyleSheet(
            "QPushButton { background: #173560; color: #FFFFFF; font-weight: 700; "
            "border: none; border-radius: 6px; padding: 7px 16px; font-size: 12px; } "
            "QPushButton:hover { background: #0F2342; }"
        )
        btn_add.clicked.connect(self._open_add_worker_dialog)
        tb.addWidget(btn_add)

        lay.addLayout(tb)

        # Month label strip (shows which month's data is displayed)
        import calendar as _cal
        _today = date.today()
        _month_label = QLabel(f"📅  Showing: {_cal.month_name[_today.month]} {_today.year}  (Current Month)")
        _month_label.setStyleSheet(
            "background: #EFF6FF; color: #1E40AF; font-size: 11px; font-weight: 700; "
            "border: 1px solid #BFDBFE; border-radius: 4px; padding: 4px 12px;"
        )
        lay.addWidget(_month_label)

        # Table
        self.table_dir = QTableWidget()
        self.table_dir.setColumnCount(9)
        self.table_dir.setHorizontalHeaderLabels([
            "S.No.", "Worker Name", "Work Type", "Mobile", "Daily Rate",
            "Monthly Total Payment", "Advance", "Net Payable", "Actions"
        ])
        hh_dir = self.table_dir.horizontalHeader()
        hh_dir.setMinimumSectionSize(50)
        hh_dir.setSectionResizeMode(0, QHeaderView.Interactive)
        hh_dir.setSectionResizeMode(1, QHeaderView.Stretch)
        hh_dir.setSectionResizeMode(2, QHeaderView.Interactive)
        hh_dir.setSectionResizeMode(3, QHeaderView.Interactive)
        hh_dir.setSectionResizeMode(4, QHeaderView.Interactive)
        hh_dir.setSectionResizeMode(5, QHeaderView.Interactive)
        hh_dir.setSectionResizeMode(6, QHeaderView.Interactive)
        hh_dir.setSectionResizeMode(7, QHeaderView.Interactive)
        hh_dir.setSectionResizeMode(8, QHeaderView.Interactive)

        self.table_dir.setColumnWidth(0, 55)
        self.table_dir.setColumnWidth(2, 110)
        self.table_dir.setColumnWidth(3, 110)
        self.table_dir.setColumnWidth(4, 110)
        self.table_dir.setColumnWidth(5, 150)
        self.table_dir.setColumnWidth(6, 110)
        self.table_dir.setColumnWidth(7, 115)
        self.table_dir.setColumnWidth(8, 160)

        self.table_dir.verticalHeader().setVisible(False)
        self.table_dir.verticalHeader().setDefaultSectionSize(42)
        self.table_dir.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_dir.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_dir.setStyleSheet("""
            QTableWidget { border: 1px solid #E2E8F0; gridline-color: #F1F5F9; font-size: 13px; background: #FFFFFF; }
            QTableWidget::item { padding-left: 8px; padding-right: 8px; padding-top: 2px; padding-bottom: 2px; }
            QHeaderView::section { background: #F8FAFC; color: #334155; font-weight: 700; border: none; border-bottom: 2px solid #CBD5E1; border-right: 1px solid #E2E8F0; padding: 8px; font-size: 12px; }
        """)
        lay.addWidget(self.table_dir, 1)

        return w

    # -------------------------------------------------------------------------
    # Tab 2: Fast Daily Attendance Entry
    # -------------------------------------------------------------------------
    def _build_attendance_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        # Toolbar
        tb = QHBoxLayout()
        tb.setSpacing(10)

        tb.addWidget(QLabel("Date:"))

        btn_prev = QPushButton("◀ Prev")
        btn_prev.setCursor(Qt.PointingHandCursor)
        btn_prev.setStyleSheet("font-size: 11px; padding: 5px 10px; background: #F1F5F9; border-radius: 4px;")
        btn_prev.clicked.connect(lambda: self.att_date_edit.setDate(self.att_date_edit.date().addDays(-1)))
        tb.addWidget(btn_prev)

        self.att_date_edit = QDateEdit()
        self.att_date_edit.setCalendarPopup(True)
        self.att_date_edit.setDate(QDate.currentDate())
        self.att_date_edit.setMaximumDate(QDate.currentDate())  # Cannot go to future
        self.att_date_edit.dateChanged.connect(self._load_daily_attendance_data)
        self.att_date_edit.setStyleSheet("font-size: 12px; font-weight: 700; padding: 4px 8px;")
        tb.addWidget(self.att_date_edit)

        self.btn_att_next = QPushButton("Next ▶")
        self.btn_att_next.setCursor(Qt.PointingHandCursor)
        self.btn_att_next.setStyleSheet("font-size: 11px; padding: 5px 10px; background: #F1F5F9; border-radius: 4px;")
        self.btn_att_next.clicked.connect(self._att_go_next_day)
        tb.addWidget(self.btn_att_next)

        btn_today = QPushButton("Today")
        btn_today.setCursor(Qt.PointingHandCursor)
        btn_today.setStyleSheet("font-size: 11px; font-weight: 700; padding: 5px 12px; background: #E2E8F0; border-radius: 4px;")
        btn_today.clicked.connect(lambda: self.att_date_edit.setDate(QDate.currentDate()))
        tb.addWidget(btn_today)

        tb.addStretch(1)

        self.lbl_daily_att_counts = QLabel("")
        self.lbl_daily_att_counts.setStyleSheet("font-size: 12px; font-weight: 700; color: #1E293B;")
        tb.addWidget(self.lbl_daily_att_counts)

        btn_add_haaziri = QPushButton("➕ + Add Attendance")
        btn_add_haaziri.setCursor(Qt.PointingHandCursor)
        btn_add_haaziri.setStyleSheet(
            "QPushButton { background: #173560; color: #FFFFFF; font-weight: 700; "
            "border: none; border-radius: 6px; padding: 6px 14px; font-size: 12px; } "
            "QPushButton:hover { background: #0F2342; }"
        )
        btn_add_haaziri.clicked.connect(lambda: self._open_add_attendance_dialog())
        tb.addWidget(btn_add_haaziri)

        btn_all_full = QPushButton("✓ Mark All Full Day")
        btn_all_full.setCursor(Qt.PointingHandCursor)
        btn_all_full.setStyleSheet(
            "QPushButton { background: #059669; color: #FFFFFF; font-weight: 700; "
            "border: none; border-radius: 6px; padding: 6px 14px; font-size: 12px; } "
            "QPushButton:hover { background: #047857; }"
        )
        btn_all_full.clicked.connect(self._mark_all_full_day)
        tb.addWidget(btn_all_full)

        lay.addLayout(tb)

        # Table (6 Clean Columns - No redundant Units or Earning columns)
        self.table_att = QTableWidget()
        self.table_att.setColumnCount(6)
        self.table_att.setHorizontalHeaderLabels([
            "S.No.", "Worker Name", "Work Type", "Daily Rate", "Mark Attendance", "Notes"
        ])
        hh_att = self.table_att.horizontalHeader()
        hh_att.setMinimumSectionSize(50)
        hh_att.setSectionResizeMode(0, QHeaderView.Interactive)
        hh_att.setSectionResizeMode(1, QHeaderView.Stretch)
        hh_att.setSectionResizeMode(2, QHeaderView.Interactive)
        hh_att.setSectionResizeMode(3, QHeaderView.Interactive)
        hh_att.setSectionResizeMode(4, QHeaderView.Interactive)
        hh_att.setSectionResizeMode(5, QHeaderView.Stretch)

        self.table_att.setColumnWidth(0, 60)
        self.table_att.setColumnWidth(2, 120)
        self.table_att.setColumnWidth(3, 130)
        self.table_att.setColumnWidth(4, 380)

        self.table_att.verticalHeader().setVisible(False)
        self.table_att.verticalHeader().setDefaultSectionSize(44)
        self.table_att.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_att.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_att.setStyleSheet("""
            QTableWidget { border: 1px solid #E2E8F0; gridline-color: #F1F5F9; font-size: 13px; background: #FFFFFF; }
            QTableWidget::item { padding-left: 8px; padding-right: 8px; padding-top: 2px; padding-bottom: 2px; }
            QHeaderView::section { background: #F8FAFC; color: #334155; font-weight: 700; border: none; border-bottom: 2px solid #CBD5E1; border-right: 1px solid #E2E8F0; padding: 8px; font-size: 12px; }
        """)
        lay.addWidget(self.table_att, 1)

        return w

    # -------------------------------------------------------------------------
    # Tab 3: Monthly Attendance Table & History
    # -------------------------------------------------------------------------
    def _build_history_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        # Toolbar
        tb = QHBoxLayout()
        tb.setSpacing(10)

        tb.addWidget(QLabel("Select Worker:"))
        self.cb_hist_worker = QComboBox()
        self.cb_hist_worker.setFixedWidth(240)
        self.cb_hist_worker.currentIndexChanged.connect(self._load_monthly_history_data)
        tb.addWidget(self.cb_hist_worker)

        tb.addWidget(QLabel("Month & Year:"))
        self.cb_hist_month = QComboBox()
        for m in range(1, 13):
            self.cb_hist_month.addItem(calendar.month_name[m], m)
        self.cb_hist_month.setCurrentIndex(date.today().month - 1)
        self.cb_hist_month.currentIndexChanged.connect(self._load_monthly_history_data)
        tb.addWidget(self.cb_hist_month)

        self.cb_hist_year = QComboBox()
        cur_year = date.today().year
        for y in range(cur_year - 2, cur_year + 3):
            self.cb_hist_year.addItem(str(y), y)
        self.cb_hist_year.setCurrentText(str(cur_year))
        self.cb_hist_year.currentIndexChanged.connect(self._load_monthly_history_data)
        tb.addWidget(self.cb_hist_year)

        tb.addStretch(1)

        btn_add_haaziri = QPushButton("+ Add Attendance")
        btn_add_haaziri.setCursor(Qt.PointingHandCursor)
        btn_add_haaziri.setStyleSheet("background: #173560; color: white; font-weight: 700; border-radius: 4px; padding: 6px 14px; font-size: 11px;")
        btn_add_haaziri.clicked.connect(lambda: self._open_add_attendance_dialog())
        tb.addWidget(btn_add_haaziri)

        btn_whatsapp = QPushButton("WhatsApp Summary")
        btn_whatsapp.setCursor(Qt.PointingHandCursor)
        btn_whatsapp.setStyleSheet("background: #25D366; color: white; font-weight: 700; border-radius: 4px; padding: 6px 12px; font-size: 11px;")
        btn_whatsapp.clicked.connect(self._copy_whatsapp_summary)
        tb.addWidget(btn_whatsapp)

        btn_view_slip = QPushButton("Share Salary Card")
        btn_view_slip.setCursor(Qt.PointingHandCursor)
        btn_view_slip.setStyleSheet("background: #059669; color: white; font-weight: 700; border-radius: 4px; padding: 6px 14px; font-size: 11px;")
        btn_view_slip.clicked.connect(self._open_summary_slip)
        tb.addWidget(btn_view_slip)

        lay.addLayout(tb)

        # History Table - 9 Columns (DATE, DAY, ATTENDANCE, RATE, TRAVEL, ADVANCE, NET, NOTES, ACTION)
        self.table_hist = QTableWidget()
        self.table_hist.setColumnCount(9)
        self.table_hist.setHorizontalHeaderLabels([
            "DATE", "DAY", "ATTENDANCE", "DAILY RATE", "TRAVEL (+)", "ADVANCE (-)", "DAILY NET", "NOTES & DETAILS", "ACTION"
        ])
        hh = self.table_hist.horizontalHeader()
        hh.setMinimumSectionSize(50)
        hh.setSectionResizeMode(0, QHeaderView.Interactive)
        hh.setSectionResizeMode(1, QHeaderView.Interactive)
        hh.setSectionResizeMode(2, QHeaderView.Interactive)
        hh.setSectionResizeMode(3, QHeaderView.Interactive)
        hh.setSectionResizeMode(4, QHeaderView.Interactive)
        hh.setSectionResizeMode(5, QHeaderView.Interactive)
        hh.setSectionResizeMode(6, QHeaderView.Interactive)
        hh.setSectionResizeMode(7, QHeaderView.Stretch)
        hh.setSectionResizeMode(8, QHeaderView.Interactive)

        self.table_hist.setColumnWidth(0, 110)
        self.table_hist.setColumnWidth(1, 65)
        self.table_hist.setColumnWidth(2, 130)
        self.table_hist.setColumnWidth(3, 125)
        self.table_hist.setColumnWidth(4, 110)
        self.table_hist.setColumnWidth(5, 120)
        self.table_hist.setColumnWidth(6, 120)
        self.table_hist.setColumnWidth(8, 80)

        self.table_hist.verticalHeader().setVisible(False)
        self.table_hist.verticalHeader().setDefaultSectionSize(40)
        self.table_hist.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_hist.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_hist.setStyleSheet("""
            QTableWidget { border: 1px solid #E2E8F0; gridline-color: #F1F5F9; font-size: 13px; background: #FFFFFF; }
            QTableWidget::item { padding-left: 8px; padding-right: 8px; padding-top: 2px; padding-bottom: 2px; }
            QHeaderView::section { background: #F8FAFC; color: #334155; font-weight: 700; border: none; border-bottom: 2px solid #CBD5E1; border-right: 1px solid #E2E8F0; padding: 8px; font-size: 12px; }
        """)
        lay.addWidget(self.table_hist, 1)

        # Bottom Summary Strip (2-tier responsive layout - never clips!)
        self.hist_footer = QFrame()
        self.hist_footer.setStyleSheet("background: #F8FAFC; border: 1.5px solid #CBD5E1; border-radius: 8px; padding: 10px 14px;")
        hf_main = QVBoxLayout(self.hist_footer)
        hf_main.setContentsMargins(4, 4, 4, 4)
        hf_main.setSpacing(8)

        # Tier 1: Attendance breakdown badges
        row1 = QHBoxLayout()
        row1.setSpacing(8)

        def _make_badge(lbl_text, bg, fg, border):
            lbl = QLabel(lbl_text)
            lbl.setStyleSheet(f"background: {bg}; color: {fg}; border: 1px solid {border}; border-radius: 4px; padding: 3px 8px; font-size: 11px; font-weight: 700;")
            return lbl

        self.lbl_hf_units = _make_badge("Total Units: 0.0 D", "#EFF6FF", "#1E40AF", "#BFDBFE")
        self.lbl_hf_full = _make_badge("Full: 0", "#ECFDF5", "#059669", "#A7F3D0")
        self.lbl_hf_half = _make_badge("Half: 0", "#E0F2FE", "#0284C7", "#BAE6FD")
        self.lbl_hf_dedhi = _make_badge("1.5 Day: 0", "#F5F3FF", "#7C3AED", "#DDD6FE")
        self.lbl_hf_double = _make_badge("Double: 0", "#FEF3C7", "#D97706", "#FDE68A")
        self.lbl_hf_absent = _make_badge("Absent: 0", "#FEF2F2", "#DC2626", "#FECACA")

        row1.addWidget(self.lbl_hf_units)
        row1.addWidget(self.lbl_hf_full)
        row1.addWidget(self.lbl_hf_half)
        row1.addWidget(self.lbl_hf_dedhi)
        row1.addWidget(self.lbl_hf_double)
        row1.addWidget(self.lbl_hf_absent)
        row1.addStretch(1)
        hf_main.addLayout(row1)

        # Tier 2: Financial Calculation Chips & Final Net Hero
        row2 = QHBoxLayout()
        row2.setSpacing(10)

        def _fin_chip(title, val_text, color):
            f = QFrame()
            f.setStyleSheet("background: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 6px; padding: 4px 10px;")
            l = QHBoxLayout(f)
            l.setContentsMargins(0, 0, 0, 0)
            l.setSpacing(6)
            tl = QLabel(title)
            tl.setStyleSheet("font-size: 11px; color: #64748B; font-weight: 600;")
            vl = QLabel(val_text)
            vl.setStyleSheet(f"font-size: 12px; color: {color}; font-weight: 800;")
            l.addWidget(tl)
            l.addWidget(vl)
            return f, vl

        self.f_hf_earning, self.lbl_hf_earning = _fin_chip("Work Earnings:", "₹ 0.00", "#173560")
        self.f_hf_travel, self.lbl_hf_travel = _fin_chip("(+) Travel:", "+ ₹ 0.00", "#059669")
        self.f_hf_advances, self.lbl_hf_advances = _fin_chip("(-) Advances:", "- ₹ 0.00", "#DC2626")

        self.f_hf_net = QFrame()
        self.f_hf_net.setStyleSheet("background: #173560; border-radius: 6px; padding: 5px 14px;")
        l_net = QHBoxLayout(self.f_hf_net)
        l_net.setContentsMargins(0, 0, 0, 0)
        l_net.setSpacing(8)
        lbl_net_title = QLabel("FINAL NET PAYABLE:")
        lbl_net_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #F59E0B; letter-spacing: 0.5px;")
        self.lbl_hf_net = QLabel("₹ 0.00")
        self.lbl_hf_net.setStyleSheet("font-size: 14px; font-weight: 900; color: #FFFFFF;")
        l_net.addWidget(lbl_net_title)
        l_net.addWidget(self.lbl_hf_net)

        row2.addWidget(self.f_hf_earning)
        row2.addWidget(self.f_hf_travel)
        row2.addWidget(self.f_hf_advances)
        row2.addStretch(1)
        row2.addWidget(self.f_hf_net)
        hf_main.addLayout(row2)

        lay.addWidget(self.hist_footer)

        return w

    # -------------------------------------------------------------------------
    # Tab 4: Payments, Advances & Settlement
    # -------------------------------------------------------------------------
    def _build_settlement_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        # Toolbar
        tb = QHBoxLayout()
        tb.setSpacing(10)

        tb.addWidget(QLabel("Select Worker:"))
        self.cb_pay_worker = QComboBox()
        self.cb_pay_worker.setFixedWidth(240)
        self.cb_pay_worker.currentIndexChanged.connect(self._load_settlement_data)
        tb.addWidget(self.cb_pay_worker)

        tb.addWidget(QLabel("Month & Year:"))
        self.cb_pay_month = QComboBox()
        for m in range(1, 13):
            self.cb_pay_month.addItem(calendar.month_name[m], m)
        self.cb_pay_month.setCurrentIndex(date.today().month - 1)
        self.cb_pay_month.currentIndexChanged.connect(self._load_settlement_data)
        tb.addWidget(self.cb_pay_month)

        self.cb_pay_year = QComboBox()
        cur_year = date.today().year
        for y in range(cur_year - 2, cur_year + 3):
            self.cb_pay_year.addItem(str(y), y)
        self.cb_pay_year.setCurrentText(str(cur_year))
        self.cb_pay_year.currentIndexChanged.connect(self._load_settlement_data)
        tb.addWidget(self.cb_pay_year)

        tb.addStretch(1)

        btn_add_adv = QPushButton("💵 + Advance")
        btn_add_adv.setCursor(Qt.PointingHandCursor)
        btn_add_adv.setStyleSheet("background: #DC2626; color: white; font-weight: 700; border-radius: 4px; padding: 6px 12px; font-size: 11px;")
        btn_add_adv.clicked.connect(self._open_advance_dialog)
        tb.addWidget(btn_add_adv)

        btn_add_exp = QPushButton("🛵 + Travel")
        btn_add_exp.setCursor(Qt.PointingHandCursor)
        btn_add_exp.setStyleSheet("background: #059669; color: white; font-weight: 700; border-radius: 4px; padding: 6px 12px; font-size: 11px;")
        btn_add_exp.clicked.connect(self._open_travel_dialog)
        tb.addWidget(btn_add_exp)

        btn_add_adj = QPushButton("⚖ + Adjustment")
        btn_add_adj.setCursor(Qt.PointingHandCursor)
        btn_add_adj.setStyleSheet("background: #173560; color: white; font-weight: 700; border-radius: 4px; padding: 6px 12px; font-size: 11px;")
        btn_add_adj.clicked.connect(self._open_adjustment_dialog)
        tb.addWidget(btn_add_adj)

        lay.addLayout(tb)

        # Splitter: Left (Transactions Tables) vs Right (Settlement Card)
        split = QSplitter(Qt.Horizontal)
        split.setHandleWidth(8)

        # Left: Transactions Tabs
        left_box = QWidget()
        lb_lay = QVBoxLayout(left_box)
        lb_lay.setContentsMargins(0, 0, 0, 0)
        lb_lay.setSpacing(8)

        self.trans_subtabs = QTabWidget()
        self.trans_subtabs.setStyleSheet("QTabWidget::pane { border: 1px solid #CBD5E1; border-radius: 6px; }")

        self.table_advances = self._make_sub_table(["Date", "Amount", "Method", "Notes", "Action"])
        self.table_travel = self._make_sub_table(["Date", "Amount", "Category", "Notes", "Action"])
        self.table_adjustments = self._make_sub_table(["Date", "Type", "Category", "Amount", "Notes", "Action"])

        self.trans_subtabs.addTab(self.table_advances, "Advances Given (-)")
        self.trans_subtabs.addTab(self.table_travel, "Travel / Rickshaw (+)")
        self.trans_subtabs.addTab(self.table_adjustments, "Other Additions & Deductions")

        lb_lay.addWidget(self.trans_subtabs)
        split.addWidget(left_box)

        # Right: Settlement Card
        right_box = QWidget()
        rb_lay = QVBoxLayout(right_box)
        rb_lay.setContentsMargins(0, 0, 0, 0)

        self.settlement_card = QFrame()
        self.settlement_card.setStyleSheet("background: #F8FAFC; border: 2px solid #CBD5E1; border-radius: 8px; padding: 14px;")
        sc_lay = QGridLayout(self.settlement_card)
        sc_lay.setVerticalSpacing(8)

        def _sc_row(row_idx, label, val_str, color="#0F172A", bold=False):
            l = QLabel(label)
            l.setStyleSheet(f"font-size: 12px; color: #475569; {'font-weight:700;' if bold else ''}")
            vl = QLabel(val_str)
            vl.setAlignment(Qt.AlignRight)
            vl.setStyleSheet(f"font-size: 12px; color: {color}; {'font-weight:800;' if bold else 'font-weight:600;'}")
            sc_lay.addWidget(l, row_idx, 0)
            sc_lay.addWidget(vl, row_idx, 1)
            return vl

        self.lbl_sc_work = _sc_row(0, "Work Earnings:", "₹ 0.00")
        self.lbl_sc_travel = _sc_row(1, "(+) Travel Expenses:", "+ ₹ 0.00", color="#059669")
        self.lbl_sc_add = _sc_row(2, "(+) Other Additions:", "+ ₹ 0.00", color="#059669")
        self.lbl_sc_gross = _sc_row(3, "Gross Payable:", "₹ 0.00", bold=True)
        self.lbl_sc_adv = _sc_row(4, "(-) Advance Payments:", "- ₹ 0.00", color="#DC2626")
        self.lbl_sc_ded = _sc_row(5, "(-) Other Deductions:", "- ₹ 0.00", color="#DC2626")

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #CBD5E1;")
        sc_lay.addWidget(line, 6, 0, 1, 2)

        self.lbl_sc_net = _sc_row(7, "NET PAYABLE:", "₹ 0.00", color="#173560", bold=True)
        self.lbl_sc_paid = _sc_row(8, "Paid Amount:", "₹ 0.00", color="#059669")
        self.lbl_sc_rem = _sc_row(9, "REMAINING DUE:", "₹ 0.00", color="#DC2626", bold=True)

        self.btn_settle_action = QPushButton("💰 Settle Month / Record Payment")
        self.btn_settle_action.setCursor(Qt.PointingHandCursor)
        self.btn_settle_action.setStyleSheet(
            "QPushButton { background: #173560; color: #FFFFFF; font-weight: 700; "
            "border: none; border-radius: 6px; padding: 10px; font-size: 13px; } "
            "QPushButton:hover { background: #0F2342; }"
        )
        self.btn_settle_action.clicked.connect(self._open_settlement_dialog)
        sc_lay.addWidget(self.btn_settle_action, 10, 0, 1, 2)

        self.btn_view_slip_card = QPushButton("📸 View & Share Salary Slip (Photo Card)")
        self.btn_view_slip_card.setCursor(Qt.PointingHandCursor)
        self.btn_view_slip_card.setStyleSheet(
            "QPushButton { background: #059669; color: #FFFFFF; font-weight: 700; "
            "border: none; border-radius: 6px; padding: 10px; font-size: 12px; } "
            "QPushButton:hover { background: #047857; }"
        )
        self.btn_view_slip_card.clicked.connect(self._open_summary_slip)
        sc_lay.addWidget(self.btn_view_slip_card, 11, 0, 1, 2)

        rb_lay.addWidget(self.settlement_card)
        rb_lay.addStretch(1)
        split.addWidget(right_box)

        split.setSizes([600, 380])
        lay.addWidget(split, 1)

        return w

    def _make_sub_table(self, headers: list[str]) -> QTableWidget:
        t = QTableWidget(0, len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        t.horizontalHeader().setSectionResizeMode(len(headers) - 2, QHeaderView.Stretch)
        t.verticalHeader().setVisible(False)
        t.setSelectionBehavior(QAbstractItemView.SelectRows)
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.setStyleSheet("""
            QTableWidget { border: none; gridline-color: #F1F5F9; font-size: 11px; }
            QTableWidget::item { padding: 4px 6px; }
            QHeaderView::section { background: #F8FAFC; color: #475569; font-weight: 700; border: none; border-bottom: 2px solid #CBD5E1; padding: 6px; font-size: 11px; }
        """)
        return t

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------
    def on_first_show(self):
        self.refresh()

    def refresh(self):
        self._load_kpis()
        self._sync_worker_comboboxes()
        self._load_directory_data()
        self._load_daily_attendance_data()
        self._load_monthly_history_data()
        self._load_settlement_data()

    def _on_tab_changed(self, idx: int):
        self._load_kpis()
        if idx == 0:
            self._load_directory_data()
        elif idx == 1:
            self._load_daily_attendance_data()
        elif idx == 2:
            self._load_monthly_history_data()
        elif idx == 3:
            self._load_settlement_data()

    def _sync_worker_comboboxes(self):
        workers = worker_service.get_workers(is_active=None)
        self._cached_workers = workers

        for cb in (self.cb_hist_worker, self.cb_pay_worker):
            curr_id = cb.currentData()
            cb.blockSignals(True)
            cb.clear()
            for idx, w in enumerate(workers, 1):
                cb.addItem(f"{idx}. {w.name} ({w.work_type} - ₹{float(w.daily_rate or 0):,.0f}/day)", w.id)
            if curr_id:
                idx = cb.findData(curr_id)
                if idx >= 0:
                    cb.setCurrentIndex(idx)
            cb.blockSignals(False)

    # -------------------------------------------------------------------------
    # Data Loaders: KPIs
    # -------------------------------------------------------------------------
    def _load_kpis(self):
        today = date.today()
        metrics = worker_service.get_dashboard_worker_metrics(today.year, today.month)

        self.kpi_labels["total_workers"].setText(f"{metrics['total_workers']} Total")
        self.kpi_labels["active_workers"].setText(f"{metrics['active_workers']} Active")
        self.kpi_labels["month_work_cost"].setText(_money(metrics["month_work_cost"]))

        advs = worker_service.get_advances(today.year, today.month)
        tot_adv = sum(a["amount"] for a in advs)
        self.kpi_labels["advances_taken"].setText(f"- {_money(tot_adv)}")
        self.kpi_labels["pending_payments"].setText(_money(metrics["pending_payments"]))

    # -------------------------------------------------------------------------
    # Tab 1: Directory Data
    # -------------------------------------------------------------------------
    def _load_directory_data(self):
        query = self.f_dir_search.text().strip()
        w_type = self.cb_dir_type.currentText()
        if w_type == "All Types":
            w_type = None

        st_idx = self.cb_dir_status.currentIndex()
        is_active = True if st_idx == 1 else (False if st_idx == 2 else None)

        today = date.today()
        workers = worker_service.get_workers(search_query=query, work_type=w_type, is_active=is_active)

        self.table_dir.setRowCount(len(workers))
        for r, w in enumerate(workers):
            self.table_dir.setRowHeight(r, 42)

            sno_item = QTableWidgetItem(str(r + 1))
            sno_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
            sno_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            self.table_dir.setItem(r, 0, sno_item)

            name_item = QTableWidgetItem(w.name)
            name_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            name_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            self.table_dir.setItem(r, 1, name_item)

            type_item = QTableWidgetItem(w.work_type or "Mistri")
            type_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            type_item.setFont(QFont("Segoe UI", 10))
            self.table_dir.setItem(r, 2, type_item)

            mob_item = QTableWidgetItem(w.mobile or "—")
            mob_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
            mob_item.setFont(QFont("Segoe UI", 10))
            self.table_dir.setItem(r, 3, mob_item)

            rate_item = QTableWidgetItem(_money(w.daily_rate))
            rate_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
            rate_item.setFont(QFont("Segoe UI", 10))
            self.table_dir.setItem(r, 4, rate_item)

            # Current Month stats (Monthly Total Payment = work earning + travel - advance)
            summary = worker_service.get_worker_monthly_summary(w.id, today.year, today.month)
            if summary:
                # Monthly Total Payment = gross payable (earnings + travel + additions)
                monthly_total = summary.get('gross_payable', summary.get('total_work_earning', 0))
                e_item = QTableWidgetItem(_money(monthly_total))
                e_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                e_item.setFont(QFont("Segoe UI", 10))
                self.table_dir.setItem(r, 5, e_item)

                a_item = QTableWidgetItem(_money(summary['total_advance']))
                a_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                a_item.setFont(QFont("Segoe UI", 10))
                self.table_dir.setItem(r, 6, a_item)

                net_item = QTableWidgetItem(_money(summary['net_payable']))
                net_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                net_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
                net_item.setForeground(QColor("#173560"))
                self.table_dir.setItem(r, 7, net_item)
            else:
                for c in range(5, 8):
                    dash = QTableWidgetItem("₹ 0.00")
                    dash.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                    self.table_dir.setItem(r, c, dash)

            # Actions Box — compact styled text buttons
            act_box = QWidget()
            act_lay = QHBoxLayout(act_box)
            act_lay.setContentsMargins(4, 2, 4, 2)
            act_lay.setSpacing(4)

            def _act_btn(label, tip, fg, bg, hover_bg):
                b = QPushButton(label)
                b.setCursor(Qt.PointingHandCursor)
                b.setToolTip(tip)
                b.setStyleSheet(
                    f"QPushButton {{ background: {bg}; color: {fg}; font-weight: 700; font-size: 11px; "
                    f"border: 1px solid {fg}30; border-radius: 4px; padding: 3px 7px; }} "
                    f"QPushButton:hover {{ background: {hover_bg}; color: #FFFFFF; }}"
                )
                return b

            btn_view   = _act_btn("View",       "View monthly history",             "#2563EB", "#EFF6FF", "#2563EB")
            btn_card   = _act_btn("Slip",       "Share monthly salary card (photo)","#059669", "#ECFDF5", "#059669")
            btn_edit   = _act_btn("Edit",       "Edit worker profile",               "#475569", "#F8FAFC", "#475569")
            if w.is_active:
                btn_toggle = _act_btn("Off",   "Deactivate worker",                "#DC2626", "#FEF2F2", "#DC2626")
            else:
                btn_toggle = _act_btn("On",    "Activate worker",                  "#059669", "#ECFDF5", "#059669")

            btn_view.clicked.connect(lambda _=False, w_id=w.id: self._jump_to_worker_history(w_id))
            btn_card.clicked.connect(lambda _=False, w_id=w.id: self._open_card_for_worker(w_id))
            btn_edit.clicked.connect(lambda _=False, worker=w: self._edit_worker(worker))
            btn_toggle.clicked.connect(lambda _=False, w_id=w.id: self._toggle_worker(w_id))

            act_lay.addWidget(btn_view)
            act_lay.addWidget(btn_card)
            act_lay.addWidget(btn_edit)
            act_lay.addWidget(btn_toggle)
            act_lay.addStretch(1)

            self.table_dir.setCellWidget(r, 8, act_box)

    def _open_add_worker_dialog(self):
        dlg = WorkerDialog(self)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            w = worker_service.create_worker(
                name=data["name"],
                daily_rate=data["daily_rate"],
                mobile=data["mobile"],
                work_type=data["work_type"],
                joining_date=data["joining_date"],
                address=data["address"],
                notes=data["notes"],
                worker_code=data["worker_code"],
            )
            self.refresh()
            show_toast(self, f"Worker {w.name} added ({w.worker_code})", "success")

    def _edit_worker(self, worker):
        dlg = WorkerDialog(self, worker=worker)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            worker_service.update_worker(
                worker.id,
                name=data["name"],
                daily_rate=data["daily_rate"],
                mobile=data["mobile"],
                work_type=data["work_type"],
                joining_date=data["joining_date"],
                address=data["address"],
                notes=data["notes"],
            )
            self.refresh()
            show_toast(self, f"Worker {data['name']} updated", "success")

    def _toggle_worker(self, worker_id: int):
        worker_service.toggle_worker_status(worker_id)
        self.refresh()

    def _jump_to_worker_history(self, worker_id: int):
        idx = self.cb_hist_worker.findData(worker_id)
        if idx >= 0:
            self.cb_hist_worker.setCurrentIndex(idx)
        self.tabs.setCurrentIndex(2)  # Monthly History Tab

    def _open_card_for_worker(self, worker_id: int):
        year = self.cb_hist_year.currentData() or date.today().year
        month = self.cb_hist_month.currentData() or date.today().month
        summary = worker_service.get_worker_monthly_summary(worker_id, year, month)
        if not summary:
            show_toast(self, "No attendance or payment data found.", "info")
            return
        workers = worker_service.get_workers(is_active=None)
        s_no = next((i for i, w in enumerate(workers, 1) if w.id == worker_id), None)
        summary["serial_no"] = s_no

        profile = business_service.get_profile()
        b_name = profile.business_name if profile else ""
        dlg = MonthlySummarySlipDialog(self, summary=summary, business_name=b_name)
        dlg.exec()

    # -------------------------------------------------------------------------
    # Tab 2: Daily Attendance Entry Data
    # -------------------------------------------------------------------------
    def _load_daily_attendance_data(self):
        qd = self.att_date_edit.date()
        att_d = date(qd.year(), qd.month(), qd.day())

        workers = worker_service.get_workers(is_active=True)
        att_map = worker_service.get_daily_attendance(att_d)

        self.table_att.setRowCount(len(workers))

        cnt_full = 0
        cnt_half = 0
        cnt_dedhi = 0
        cnt_double = 0
        cnt_absent = 0

        for r, w in enumerate(workers):
            self.table_att.setRowHeight(r, 44)

            sno_item = QTableWidgetItem(str(r + 1))
            sno_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
            sno_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            self.table_att.setItem(r, 0, sno_item)

            name_item = QTableWidgetItem(w.name)
            name_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            name_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            self.table_att.setItem(r, 1, name_item)

            type_item = QTableWidgetItem(w.work_type or "Mistri")
            type_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            type_item.setFont(QFont("Segoe UI", 10))
            self.table_att.setItem(r, 2, type_item)

            rate_item = QTableWidgetItem(_money(w.daily_rate))
            rate_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
            rate_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            rate_item.setForeground(QColor("#173560"))
            self.table_att.setItem(r, 3, rate_item)

            rec = att_map.get(w.id, {})
            mult = rec.get("day_multiplier")

            if mult == 1.0:
                cnt_full += 1
            elif mult == 0.5:
                cnt_half += 1
            elif mult == 1.5:
                cnt_dedhi += 1
            elif mult == 2.0:
                cnt_double += 1
            elif mult == 0.0:
                cnt_absent += 1

            # Selector widget
            selector = self._make_attendance_selector(w.id, att_d, mult, w.daily_rate)
            self.table_att.setCellWidget(r, 4, selector)

            notes_item = QTableWidgetItem(rec.get("notes", ""))
            notes_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            notes_item.setFont(QFont("Segoe UI", 10))
            self.table_att.setItem(r, 5, notes_item)

        counts_text = f"Full (1.0): {cnt_full} | Half (0.5): {cnt_half} | 1.5 Day: {cnt_dedhi} | Double (2.0): {cnt_double} | Absent: {cnt_absent}"
        self.lbl_daily_att_counts.setText(counts_text)

    def _make_attendance_selector(self, worker_id: int, att_d: date, current_multiplier: float | None, daily_rate) -> QWidget:
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(4)

        options = [
            (0.0, "Absent (0)", "#DC2626"),
            (0.5, "Half (0.5)", "#0284C7"),
            (1.0, "Full (1.0)", "#059669"),
            (1.5, "1.5 Day", "#7C3AED"),
            (2.0, "Double (2.0)", "#D97706"),
        ]

        for val, label, color in options:
            btn = QPushButton(label)
            btn.setCursor(Qt.PointingHandCursor)
            is_sel = (current_multiplier is not None and abs(current_multiplier - val) < 0.01)
            if is_sel:
                btn.setStyleSheet(f"background: {color}; color: #FFFFFF; font-weight: 800; border-radius: 4px; padding: 4px 8px; font-size: 11px; border: none;")
            else:
                btn.setStyleSheet("background: #F1F5F9; color: #475569; font-weight: 600; border-radius: 4px; padding: 4px 8px; font-size: 11px; border: 1px solid #CBD5E1;")

            btn.clicked.connect(lambda _=False, w_id=worker_id, d=att_d, m=val, lbl=label: self._set_attendance(w_id, d, m, lbl))
            lay.addWidget(btn)

        # Delete button — only shown when a record exists
        if current_multiplier is not None:
            sep = QFrame()
            sep.setFrameShape(QFrame.VLine)
            sep.setStyleSheet("color: #CBD5E1;")
            lay.addWidget(sep)

            btn_del = QPushButton("✕ Delete")
            btn_del.setCursor(Qt.PointingHandCursor)
            btn_del.setToolTip("Delete this day's attendance record")
            btn_del.setStyleSheet(
                "QPushButton { background: #FEF2F2; color: #DC2626; font-weight: 700; border: 1px solid #FECACA; "
                "border-radius: 4px; padding: 4px 8px; font-size: 11px; } "
                "QPushButton:hover { background: #DC2626; color: #FFFFFF; }"
            )
            btn_del.clicked.connect(lambda _=False, w_id=worker_id, d=att_d: self._delete_attendance_record(w_id, d))
            lay.addWidget(btn_del)

        return box

    def _set_attendance(self, worker_id: int, att_d: date, multiplier: float, status_label: str):
        worker_service.record_daily_attendance(
            worker_id=worker_id,
            att_date=att_d,
            multiplier=multiplier,
            status_label=status_label,
        )
        self._load_daily_attendance_data()
        self._load_kpis()
        show_toast(self, f"Attendance updated ({status_label})", "success")

    def _att_go_next_day(self):
        """Advance to next day, but never beyond today."""
        next_d = self.att_date_edit.date().addDays(1)
        today_q = QDate.currentDate()
        if next_d <= today_q:
            self.att_date_edit.setDate(next_d)
        else:
            show_toast(self, "Future dates cannot be marked. Please wait for the date to arrive.", "warning")

    def _mark_all_full_day(self):
        qd = self.att_date_edit.date()
        att_d = date(qd.year(), qd.month(), qd.day())
        if att_d > date.today():
            show_toast(self, "Cannot mark attendance for a future date.", "warning")
            return
        worker_service.mark_all_full_day(att_d)
        self._load_daily_attendance_data()
        self._load_kpis()
        show_toast(self, "All active workers marked Full Day", "success")

    def _delete_attendance_record(self, worker_id: int, att_date: date):
        """Delete a single attendance record after confirmation."""
        worker = worker_service.get_worker_by_id(worker_id)
        w_name = worker.name if worker else f"Worker #{worker_id}"
        date_str = att_date.strftime("%d %b %Y")

        confirm = QMessageBox.question(
            self,
            "Delete Attendance Record",
            f"Are you sure you want to delete this attendance record?\n\n"
            f"Worker: {w_name}\n"
            f"Date:   {date_str}\n\n"
            f"⚠️  This record will be permanently removed.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return

        deleted = worker_service.delete_attendance(worker_id, att_date)
        if deleted:
            self._load_daily_attendance_data()
            self._load_monthly_history_data()
            self._load_directory_data()
            self._load_kpis()
            show_toast(self, f"✓ Attendance deleted: {w_name} — {date_str}", "success")
        else:
            show_toast(self, "No attendance record found to delete.", "warning")

    def _open_daily_edit_dialog(self, worker_id: int, att_date: date, existing: dict):
        """Open DailyRecordEditDialog to edit attendance, travel, advance for a specific date."""
        worker = worker_service.get_worker_by_id(worker_id)
        w_name = worker.name if worker else f"Worker #{worker_id}"

        dlg = DailyRecordEditDialog(
            self, worker_id=worker_id, worker_name=w_name,
            att_date=att_date, existing=existing
        )
        if dlg.exec() != QDialog.Accepted:
            return

        result = dlg.get_result()

        # 1. Update attendance if changed
        mult = result.get("att_multiplier")
        if mult is not None:
            label_map = {1.0: "Full Day", 0.5: "Half Day", 1.5: "1.5 Day", 2.0: "Double Day", 0.0: "Absent"}
            worker_service.record_daily_attendance(
                worker_id=worker_id,
                att_date=att_date,
                multiplier=mult,
                status_label=label_map.get(mult, f"{mult} Day"),
                notes=result.get("att_notes", ""),
            )

        # 2. Add travel if amount > 0
        if result.get("travel_amount", 0) > 0:
            worker_service.record_travel_expense(
                worker_id=worker_id,
                expense_date=att_date,
                amount=result["travel_amount"],
                category=result.get("travel_category", "Rickshaw"),
                notes=result.get("travel_notes", ""),
            )

        # 3. Add advance if amount > 0
        if result.get("advance_amount", 0) > 0:
            worker_service.record_advance(
                worker_id=worker_id,
                advance_date=att_date,
                amount=result["advance_amount"],
                payment_method=result.get("advance_method", "Cash"),
                notes=result.get("advance_notes", ""),
            )

        # Refresh all views
        self._load_monthly_history_data()
        self._load_daily_attendance_data()
        self._load_directory_data()
        self._load_kpis()
        show_toast(self, f"Record updated: {w_name} — {att_date.strftime('%d %b %Y')}", "success")

    def _open_add_attendance_dialog(self, preselected_worker_id=None):
        workers = worker_service.get_workers(is_active=True)
        if not workers:
            show_toast(self, "No active workers available.", "warning")
            return

        qd = self.att_date_edit.date()
        current_d = date(qd.year(), qd.month(), qd.day())

        if not preselected_worker_id:
            if self.tabs.currentIndex() == 2:
                preselected_worker_id = self.cb_hist_worker.currentData()
            elif self.tabs.currentIndex() == 3:
                preselected_worker_id = self.cb_pay_worker.currentData()

        dlg = AttendanceEntryDialog(self, workers=workers, preselected_worker_id=preselected_worker_id, default_date=current_d)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            # 1. Record Attendance
            worker_service.record_daily_attendance(
                worker_id=data["worker_id"],
                att_date=data["date"],
                multiplier=data["multiplier"],
                status_label=data["status_label"],
                notes=data["att_notes"],
            )

            # 2. Record Advance if provided
            if data["advance_amount"] > 0:
                worker_service.record_advance(
                    worker_id=data["worker_id"],
                    advance_date=data["date"],
                    amount=data["advance_amount"],
                    payment_method=data["advance_method"],
                    notes=data["advance_notes"],
                )

            # 3. Record Travel if provided
            if data["travel_amount"] > 0:
                worker_service.record_travel_expense(
                    worker_id=data["worker_id"],
                    expense_date=data["date"],
                    amount=data["travel_amount"],
                    category=data["travel_category"],
                    notes=data["travel_notes"],
                )

            # Update date in tab 2
            self.att_date_edit.setDate(QDate(data["date"].year, data["date"].month, data["date"].day))

            # Refresh all views
            self._load_daily_attendance_data()
            self._load_monthly_history_data()
            self._load_settlement_data()
            self._load_directory_data()
            self._load_kpis()

            show_toast(self, "Attendance saved successfully!", "success")

    # -------------------------------------------------------------------------
    # Tab 3: Monthly Attendance Table & History
    # -------------------------------------------------------------------------
    def _load_monthly_history_data(self):
        worker_id = self.cb_hist_worker.currentData()
        year = self.cb_hist_year.currentData() or date.today().year
        month = self.cb_hist_month.currentData() or date.today().month

        if not worker_id:
            self.table_hist.setRowCount(0)
            self._update_hist_footer(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
            return

        summary = worker_service.get_worker_monthly_summary(worker_id, year, month)
        if not summary:
            self.table_hist.setRowCount(0)
            self._update_hist_footer(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
            return

        # Map travel expenses by date
        expenses_by_date = {}
        for exp in summary.get("travel_expenses", []):
            d = exp["date"]
            if d not in expenses_by_date:
                expenses_by_date[d] = {"total": 0.0, "details": []}
            expenses_by_date[d]["total"] += exp["amount"]
            note_str = f"{exp['category']}: {_money(exp['amount'])}"
            if exp["notes"]:
                note_str += f" ({exp['notes']})"
            expenses_by_date[d]["details"].append(note_str)

        # Map advances by date
        advances_by_date = {}
        for adv in summary.get("advances", []):
            d = adv["date"]
            if d not in advances_by_date:
                advances_by_date[d] = {"total": 0.0, "details": []}
            advances_by_date[d]["total"] += adv["amount"]
            note_str = f"Adv ({adv['payment_method']}): {_money(adv['amount'])}"
            if adv["notes"]:
                note_str += f" ({adv['notes']})"
            advances_by_date[d]["details"].append(note_str)

        # Map adjustments by date
        adj_by_date = {}
        for adj in summary.get("adjustments", []):
            d = adj["date"]
            if d not in adj_by_date:
                adj_by_date[d] = {"additions": 0.0, "deductions": 0.0, "details": []}
            if adj["type"] == "ADDITION":
                adj_by_date[d]["additions"] += adj["amount"]
                adj_by_date[d]["details"].append(f"+Bonus: {_money(adj['amount'])} ({adj['notes'] or adj['category']})")
            else:
                adj_by_date[d]["deductions"] += adj["amount"]
                adj_by_date[d]["details"].append(f"-Ded: {_money(adj['amount'])} ({adj['notes'] or adj['category']})")

        # Collect and order all dates
        date_keys = set()
        att_map = {}
        for a in summary.get("attendances", []):
            d = a["date"]
            date_keys.add(d)
            att_map[d] = a
        for d in expenses_by_date:
            date_keys.add(d)
        for d in advances_by_date:
            date_keys.add(d)
        for d in adj_by_date:
            date_keys.add(d)

        sorted_dates = sorted(date_keys)
        self.table_hist.setRowCount(len(sorted_dates))

        for r, d in enumerate(sorted_dates):
            self.table_hist.setRowHeight(r, 42)
            a = att_map.get(d)
            exp_info = expenses_by_date.get(d, {"total": 0.0, "details": []})
            adv_info = advances_by_date.get(d, {"total": 0.0, "details": []})
            adj_info = adj_by_date.get(d, {"additions": 0.0, "deductions": 0.0, "details": []})

            date_str = d.strftime("%d %b %Y")
            day_name = d.strftime("%a")

            date_item = QTableWidgetItem(date_str)
            date_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            date_item.setFont(QFont("Segoe UI", 10))
            self.table_hist.setItem(r, 0, date_item)

            day_item = QTableWidgetItem(day_name)
            day_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
            day_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            if day_name == "Sun":
                day_item.setForeground(QColor("#DC2626"))
            self.table_hist.setItem(r, 1, day_item)

            if a:
                mult = a["day_multiplier"]
                st_badge = QLabel(a["status_label"])
                st_badge.setAlignment(Qt.AlignCenter)
                if mult == 1.0:
                    bg, fg, bdr = "#ECFDF5", "#059669", "#A7F3D0"
                elif mult == 0.5:
                    bg, fg, bdr = "#E0F2FE", "#0284C7", "#BAE6FD"
                elif mult == 1.5:
                    bg, fg, bdr = "#F5F3FF", "#7C3AED", "#DDD6FE"
                elif mult == 2.0:
                    bg, fg, bdr = "#FEF3C7", "#D97706", "#FDE68A"
                else:
                    bg, fg, bdr = "#FEF2F2", "#DC2626", "#FECACA"
                st_badge.setStyleSheet(f"background: {bg}; color: {fg}; border: 1px solid {bdr}; border-radius: 4px; font-size: 11px; font-weight: 700; padding: 2px 6px;")
                self.table_hist.setCellWidget(r, 2, st_badge)

                rate_item = QTableWidgetItem(_money(a["daily_rate"]))
                rate_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                rate_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
                rate_item.setForeground(QColor("#173560"))
                self.table_hist.setItem(r, 3, rate_item)

                earning_val = a["daily_earning"]
            else:
                earning_val = 0.0
                dash2 = QTableWidgetItem("—"); dash2.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
                dash3 = QTableWidgetItem("—"); dash3.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
                self.table_hist.setItem(r, 2, dash2)
                self.table_hist.setItem(r, 3, dash3)

            # Travel Expense (+) (Col 4)
            if exp_info["total"] > 0:
                t_item = QTableWidgetItem(f"+ {_money(exp_info['total'])}")
                t_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                t_item.setForeground(QColor("#059669"))
                t_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
                t_item.setToolTip("\n".join(exp_info["details"]))
                self.table_hist.setItem(r, 4, t_item)
            else:
                dash4 = QTableWidgetItem("—"); dash4.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
                self.table_hist.setItem(r, 4, dash4)

            # Advance Taken (-) (Col 5)
            if adv_info["total"] > 0:
                adv_item = QTableWidgetItem(f"- {_money(adv_info['total'])}")
                adv_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                adv_item.setForeground(QColor("#DC2626"))
                adv_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
                adv_item.setToolTip("\n".join(adv_info["details"]))
                self.table_hist.setItem(r, 5, adv_item)
            else:
                dash5 = QTableWidgetItem("—"); dash5.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
                self.table_hist.setItem(r, 5, dash5)

            # Daily Net = Earning + Travel + Additions - Advance - Deductions (Col 6)
            daily_net = float(earning_val) + exp_info["total"] + adj_info["additions"] - adv_info["total"] - adj_info["deductions"]
            net_item = QTableWidgetItem(_money(daily_net))
            net_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
            net_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
            if daily_net > 0:
                net_item.setForeground(QColor("#173560"))
            elif daily_net < 0:
                net_item.setForeground(QColor("#DC2626"))
            self.table_hist.setItem(r, 6, net_item)

            # Combined Notes & Details (Col 7)
            notes_parts = []
            if a and a["notes"]:
                notes_parts.append(a["notes"])
            if exp_info["details"]:
                notes_parts.append("; ".join(exp_info["details"]))
            if adv_info["details"]:
                notes_parts.append("; ".join(adv_info["details"]))
            if adj_info["details"]:
                notes_parts.append("; ".join(adj_info["details"]))
            note_item = QTableWidgetItem(" | ".join(notes_parts))
            note_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            note_item.setFont(QFont("Segoe UI", 10))
            self.table_hist.setItem(r, 7, note_item)

            # Action column (Col 8) — Edit + Delete buttons per row
            act_cell = QWidget()
            act_layout = QHBoxLayout(act_cell)
            act_layout.setContentsMargins(3, 2, 3, 2)
            act_layout.setSpacing(4)

            if a:  # Has attendance — show Edit + Delete
                btn_edit_row = QPushButton("Edit")
                btn_edit_row.setCursor(Qt.PointingHandCursor)
                btn_edit_row.setToolTip("Edit attendance, travel or advance for this date")
                btn_edit_row.setStyleSheet(
                    "QPushButton { background: #EFF6FF; color: #2563EB; font-weight: 700; border: 1px solid #BFDBFE; "
                    "border-radius: 4px; padding: 3px 10px; font-size: 11px; } "
                    "QPushButton:hover { background: #2563EB; color: #FFFFFF; }"
                )
                worker_id_hist = self.cb_hist_worker.currentData()
                btn_edit_row.clicked.connect(
                    lambda _=False, w_id=worker_id_hist, dt=d,
                    cur_mult=a["day_multiplier"], cur_notes=a.get("notes",""):
                    self._open_daily_edit_dialog(w_id, dt, {"att_multiplier": cur_mult, "att_notes": cur_notes})
                )
                act_layout.addWidget(btn_edit_row)

                btn_del_hist = QPushButton("Del")
                btn_del_hist.setCursor(Qt.PointingHandCursor)
                btn_del_hist.setToolTip("Delete this day's attendance record")
                btn_del_hist.setStyleSheet(
                    "QPushButton { background: #FEF2F2; color: #DC2626; font-weight: 700; border: 1px solid #FECACA; "
                    "border-radius: 4px; padding: 3px 8px; font-size: 11px; } "
                    "QPushButton:hover { background: #DC2626; color: #FFFFFF; }"
                )
                btn_del_hist.clicked.connect(lambda _=False, w_id=worker_id_hist, att_date=d: self._delete_attendance_record(w_id, att_date))
                act_layout.addWidget(btn_del_hist)

            else:  # No attendance — show Add button
                btn_add_row = QPushButton("+ Add")
                btn_add_row.setCursor(Qt.PointingHandCursor)
                btn_add_row.setToolTip("Add attendance / travel / advance for this date")
                btn_add_row.setStyleSheet(
                    "QPushButton { background: #ECFDF5; color: #059669; font-weight: 700; border: 1px solid #A7F3D0; "
                    "border-radius: 4px; padding: 3px 10px; font-size: 11px; } "
                    "QPushButton:hover { background: #059669; color: #FFFFFF; }"
                )
                worker_id_hist2 = self.cb_hist_worker.currentData()
                btn_add_row.clicked.connect(lambda _=False, w_id=worker_id_hist2, dt=d: self._open_add_attendance_dialog(preselected_worker_id=w_id))
                act_layout.addWidget(btn_add_row)

            act_layout.addStretch(1)
            self.table_hist.setCellWidget(r, 8, act_cell)

        self._update_hist_footer(
            summary["total_units"],
            summary["full_days"],
            summary["half_days"],
            summary["one_and_half_days"],
            summary["double_days"],
            summary["absent_days"],
            summary["total_work_earning"],
            summary["total_travel"],
            summary["total_advance"],
            summary["net_payable"],
        )

    def _update_hist_footer(self, units, full, half, dedhi, double, absent, earning, travel=0.0, advance=0.0, net_payable=0.0):
        self.lbl_hf_units.setText(f"Total Units: <b>{units:.1f} D</b>")
        self.lbl_hf_full.setText(f"Full: <b>{full}</b>")
        self.lbl_hf_half.setText(f"Half: <b>{half}</b>")
        self.lbl_hf_dedhi.setText(f"1.5 Day: <b>{dedhi}</b>")
        self.lbl_hf_double.setText(f"Double: <b>{double}</b>")
        self.lbl_hf_absent.setText(f"Absent: <b>{absent}</b>")
        self.lbl_hf_earning.setText(_money(earning))
        self.lbl_hf_travel.setText(f"+ {_money(travel)}")
        self.lbl_hf_advances.setText(f"- {_money(advance)}")
        self.lbl_hf_net.setText(_money(net_payable))

    def _copy_whatsapp_summary(self):
        worker_id = self.cb_hist_worker.currentData() if self.tabs.currentIndex() == 2 else self.cb_pay_worker.currentData()
        year = self.cb_hist_year.currentData() or date.today().year
        month = self.cb_hist_month.currentData() or date.today().month
        if not worker_id:
            show_toast(self, "Select a worker first", "warning")
            return
        profile = business_service.get_profile()
        b_name = profile.business_name if profile else ""
        text = worker_service.generate_whatsapp_summary_text(worker_id, year, month, business_name=b_name)
        if text:
            from PySide6.QtGui import QGuiApplication
            QGuiApplication.clipboard().setText(text)
            show_toast(self, "WhatsApp summary copied! You can paste in WhatsApp.", "success")

    def _open_summary_slip(self):
        worker_id = self.cb_hist_worker.currentData() if self.tabs.currentIndex() == 2 else self.cb_pay_worker.currentData()
        year = self.cb_hist_year.currentData() or date.today().year
        month = self.cb_hist_month.currentData() or date.today().month
        if not worker_id:
            show_toast(self, "Select a worker first", "warning")
            return
        summary = worker_service.get_worker_monthly_summary(worker_id, year, month)
        if not summary:
            return
        workers = worker_service.get_workers(is_active=None)
        s_no = next((i for i, w in enumerate(workers, 1) if w.id == worker_id), None)
        summary["serial_no"] = s_no

        profile = business_service.get_profile()
        b_name = profile.business_name if profile else ""
        dlg = MonthlySummarySlipDialog(self, summary=summary, business_name=b_name)
        dlg.exec()

    # -------------------------------------------------------------------------
    # Tab 4: Payments & Settlement Data
    # -------------------------------------------------------------------------
    def _load_settlement_data(self):
        worker_id = self.cb_pay_worker.currentData()
        year = self.cb_pay_year.currentData() or date.today().year
        month = self.cb_pay_month.currentData() or date.today().month

        if not worker_id:
            return

        summary = worker_service.get_worker_monthly_summary(worker_id, year, month)
        if not summary:
            return

        # Advances
        advs = summary.get("advances", [])
        self.table_advances.setRowCount(len(advs))
        for r, a in enumerate(advs):
            self.table_advances.setRowHeight(r, 34)
            self.table_advances.setItem(r, 0, QTableWidgetItem(a["date_str"]))
            self.table_advances.setItem(r, 1, QTableWidgetItem(_money(a["amount"])))
            self.table_advances.setItem(r, 2, QTableWidgetItem(a["payment_method"]))
            self.table_advances.setItem(r, 3, QTableWidgetItem(a["notes"]))

            del_btn = QPushButton("🗑")
            del_btn.setStyleSheet("color: #DC2626; background: transparent; border: none; font-weight: 700;")
            del_btn.clicked.connect(lambda _=False, a_id=a["id"]: self._delete_advance(a_id))
            self.table_advances.setCellWidget(r, 4, del_btn)

        # Travel Expenses
        exps = summary.get("travel_expenses", [])
        self.table_travel.setRowCount(len(exps))
        for r, e in enumerate(exps):
            self.table_travel.setRowHeight(r, 34)
            self.table_travel.setItem(r, 0, QTableWidgetItem(e["date_str"]))
            self.table_travel.setItem(r, 1, QTableWidgetItem(_money(e["amount"])))
            self.table_travel.setItem(r, 2, QTableWidgetItem(e["category"]))
            self.table_travel.setItem(r, 3, QTableWidgetItem(e["notes"]))

            del_btn = QPushButton("🗑")
            del_btn.setStyleSheet("color: #DC2626; background: transparent; border: none; font-weight: 700;")
            del_btn.clicked.connect(lambda _=False, e_id=e["id"]: self._delete_travel(e_id))
            self.table_travel.setCellWidget(r, 4, del_btn)

        # Adjustments
        adjs = summary.get("adjustments", [])
        self.table_adjustments.setRowCount(len(adjs))
        for r, adj in enumerate(adjs):
            self.table_adjustments.setRowHeight(r, 34)
            self.table_adjustments.setItem(r, 0, QTableWidgetItem(adj["date_str"]))
            self.table_adjustments.setItem(r, 1, QTableWidgetItem(adj["type"]))
            self.table_adjustments.setItem(r, 2, QTableWidgetItem(adj["category"]))
            self.table_adjustments.setItem(r, 3, QTableWidgetItem(_money(adj["amount"])))
            self.table_adjustments.setItem(r, 4, QTableWidgetItem(adj["notes"]))

            del_btn = QPushButton("🗑")
            del_btn.setStyleSheet("color: #DC2626; background: transparent; border: none; font-weight: 700;")
            del_btn.clicked.connect(lambda _=False, adj_id=adj["id"]: self._delete_adjustment(adj_id))
            self.table_adjustments.setCellWidget(r, 5, del_btn)

        # Settlement Card numbers
        self.lbl_sc_work.setText(_money(summary["total_work_earning"]))
        self.lbl_sc_travel.setText(f"+ {_money(summary['total_travel'])}")
        self.lbl_sc_add.setText(f"+ {_money(summary['total_additions'])}")
        self.lbl_sc_gross.setText(_money(summary["gross_payable"]))
        self.lbl_sc_adv.setText(f"- {_money(summary['total_advance'])}")
        self.lbl_sc_ded.setText(f"- {_money(summary['total_deductions'])}")
        self.lbl_sc_net.setText(_money(summary["net_payable"]))
        self.lbl_sc_paid.setText(_money(summary["paid_amount"]))
        self.lbl_sc_rem.setText(_money(summary["remaining_balance"]))

        if summary["is_settled"]:
            self.btn_settle_action.setText("✓ Month Settled (Update Payment)")
            self.btn_settle_action.setStyleSheet("background: #059669; color: white; font-weight: 700; border-radius: 6px; padding: 10px; font-size: 13px;")
        else:
            self.btn_settle_action.setText("💰 Settle Month / Record Payment")
            self.btn_settle_action.setStyleSheet("background: #173560; color: white; font-weight: 700; border-radius: 6px; padding: 10px; font-size: 13px;")

    def _open_advance_dialog(self):
        workers = worker_service.get_workers(is_active=True)
        if not workers:
            show_toast(self, "No active workers available.", "warning")
            return
        curr_id = self.cb_hist_worker.currentData() if self.tabs.currentIndex() == 2 else self.cb_pay_worker.currentData()
        dlg = AdvanceDialog(self, workers=workers, preselected_worker_id=curr_id)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            worker_service.record_advance(
                worker_id=data["worker_id"],
                advance_date=data["date"],
                amount=data["amount"],
                payment_method=data["method"],
                notes=data["notes"],
            )
            self._load_monthly_history_data()
            self._load_settlement_data()
            self._load_kpis()
            show_toast(self, "Advance recorded successfully", "success")

    def _open_travel_dialog(self):
        workers = worker_service.get_workers(is_active=True)
        if not workers:
            show_toast(self, "No active workers available.", "warning")
            return
        curr_id = self.cb_hist_worker.currentData() if self.tabs.currentIndex() == 2 else self.cb_pay_worker.currentData()
        dlg = TravelExpenseDialog(self, workers=workers, preselected_worker_id=curr_id)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            worker_service.record_travel_expense(
                worker_id=data["worker_id"],
                expense_date=data["date"],
                amount=data["amount"],
                category=data["category"],
                notes=data["notes"],
            )
            self._load_monthly_history_data()
            self._load_settlement_data()
            self._load_kpis()
            show_toast(self, "Travel expense recorded", "success")

    def _open_adjustment_dialog(self):
        workers = worker_service.get_workers(is_active=True)
        if not workers:
            show_toast(self, "No active workers available.", "warning")
            return
        curr_id = self.cb_hist_worker.currentData() if self.tabs.currentIndex() == 2 else self.cb_pay_worker.currentData()
        dlg = AdjustmentDialog(self, workers=workers, preselected_worker_id=curr_id)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            worker_service.record_adjustment(
                worker_id=data["worker_id"],
                adjustment_date=data["date"],
                amount=data["amount"],
                adjustment_type=data["type"],
                category=data["category"],
                notes=data["notes"],
            )
            self._load_monthly_history_data()
            self._load_settlement_data()
            self._load_kpis()
            show_toast(self, f"Adjustment ({data['type']}) recorded", "success")

    def _open_settlement_dialog(self):
        worker_id = self.cb_pay_worker.currentData()
        year = self.cb_pay_year.currentData() or date.today().year
        month = self.cb_pay_month.currentData() or date.today().month
        if not worker_id:
            show_toast(self, "Select a worker first.", "warning")
            return

        summary = worker_service.get_worker_monthly_summary(worker_id, year, month)
        if not summary:
            return

        dlg = SettlementDialog(self, summary=summary)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            worker_service.record_settlement(
                worker_id=worker_id,
                year=year,
                month=month,
                paid_amount=data["paid_amount"],
                payment_method=data["method"],
                notes=data["notes"],
            )
            self._load_settlement_data()
            self._load_kpis()
            show_toast(self, f"Settlement recorded for {summary['name']}", "success")

    def _delete_advance(self, advance_id: int):
        ret = QMessageBox.question(self, "Confirm Delete", "Delete this advance record?", QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            worker_service.delete_advance(advance_id)
            self._load_settlement_data()
            self._load_kpis()
            show_toast(self, "Advance deleted", "info")

    def _delete_travel(self, expense_id: int):
        ret = QMessageBox.question(self, "Confirm Delete", "Delete this travel expense record?", QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            worker_service.delete_travel_expense(expense_id)
            self._load_settlement_data()
            self._load_kpis()
            show_toast(self, "Travel expense deleted", "info")

    def _delete_adjustment(self, adj_id: int):
        ret = QMessageBox.question(self, "Confirm Delete", "Delete this adjustment record?", QMessageBox.Yes | QMessageBox.No)
        if ret == QMessageBox.Yes:
            worker_service.delete_adjustment(adj_id)
            self._load_settlement_data()
            self._load_kpis()
            show_toast(self, "Adjustment deleted", "info")
