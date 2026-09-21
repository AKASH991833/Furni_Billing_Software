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
    """Dialog to confirm and record settlement / full payment done up to cutoff date."""

    def __init__(self, parent=None, summary=None, worker_id: int | None = None):
        super().__init__(parent)
        self.summary = summary or {}
        self.worker_id = worker_id or self.summary.get("worker_id")
        worker_name = self.summary.get("name", "Worker")

        self.setWindowTitle(f"Confirm Payment Done — {worker_name}")
        self.setMinimumWidth(480)
        self.resize(510, 530)

        v = QVBoxLayout(self)
        v.setContentsMargins(20, 18, 20, 18)
        v.setSpacing(12)

        # Title & Description
        title = QLabel(f"💰 Confirm Payment Done — {worker_name}")
        title.setStyleSheet("font-size: 16px; font-weight: 800; color: #173560;")
        v.addWidget(title)

        sub_lbl = QLabel("All attendance and advances up to the cutoff date will be marked as settled.")
        sub_lbl.setStyleSheet("font-size: 11px; color: #64748B;")
        v.addWidget(sub_lbl)

        # Cutoff Date Row
        top_form = QFormLayout()
        top_form.setVerticalSpacing(8)

        def _lab(t):
            l = QLabel(t)
            l.setStyleSheet("font-size: 11px; font-weight: 700; color: #334155;")
            return l

        self.f_end_date = QDateEdit()
        self.f_end_date.setCalendarPopup(True)
        self.f_end_date.setDisplayFormat("dd MMM yyyy")

        today = date.today()
        s_year = self.summary.get("year", today.year)
        s_month = self.summary.get("month", today.month)
        if s_year == today.year and s_month == today.month:
            init_d = today
        else:
            _, last_day = calendar.monthrange(s_year, s_month)
            init_d = date(s_year, s_month, last_day)

        self.f_end_date.setDate(QDate(init_d.year, init_d.month, init_d.day))
        self.f_end_date.setStyleSheet("""
            QDateEdit {
                font-size: 12px; font-weight: 700; padding: 6px 10px;
                border: 1.5px solid #CBD5E1; border-radius: 6px; background: #FFFFFF; color: #0F172A;
            }
        """)
        self.f_end_date.dateChanged.connect(self._on_cutoff_date_changed)
        top_form.addRow(_lab("Payment Cutoff Date *"), self.f_end_date)
        v.addLayout(top_form)

        # Dynamic Overview Box
        self.box = QFrame()
        self.box.setObjectName("settleOverviewBox")
        self.box.setStyleSheet("""
            QFrame#settleOverviewBox {
                background: #F8FAFC; border: 1.5px solid #CBD5E1; border-radius: 8px; padding: 12px;
            }
            QFrame#settleOverviewBox QLabel {
                border: none; background: transparent;
            }
        """)
        self.b_lay = QGridLayout(self.box)
        self.b_lay.setVerticalSpacing(5)

        self.lbl_row_period = QLabel("—")
        self.lbl_row_units = QLabel("—")
        self.lbl_row_earn = QLabel("—")
        self.lbl_row_travel = QLabel("—")
        self.lbl_row_add = QLabel("—")
        self.lbl_row_gross = QLabel("—")
        self.lbl_row_adv = QLabel("—")
        self.lbl_row_ded = QLabel("—")
        self.lbl_row_net = QLabel("—")

        def _row_w(row_idx, label, val_widget, color="#0F172A", bold=False):
            l = QLabel(label)
            l.setStyleSheet(f"font-size: 11.5px; color: #475569; {'font-weight:700;' if bold else ''}")
            val_widget.setAlignment(Qt.AlignRight)
            val_widget.setStyleSheet(f"font-size: 12px; color: {color}; {'font-weight:800;' if bold else 'font-weight:600;'}")
            self.b_lay.addWidget(l, row_idx, 0)
            self.b_lay.addWidget(val_widget, row_idx, 1)

        _row_w(0, "Settlement Period:", self.lbl_row_period, color="#1E40AF", bold=True)
        _row_w(1, "Days Worked:", self.lbl_row_units, bold=True)
        _row_w(2, "Base Work Earnings:", self.lbl_row_earn)
        _row_w(3, "(+) Travel / Rickshaw:", self.lbl_row_travel, color="#059669")
        _row_w(4, "(+) Other Additions:", self.lbl_row_add, color="#059669")
        _row_w(5, "Gross Payable:", self.lbl_row_gross, bold=True)
        _row_w(6, "(-) Advance Payments:", self.lbl_row_adv, color="#DC2626")
        _row_w(7, "(-) Other Deductions:", self.lbl_row_ded, color="#DC2626")

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setStyleSheet("color: #CBD5E1;")
        self.b_lay.addWidget(line, 8, 0, 1, 2)

        _row_w(9, "CYCLE NET PAYABLE:", self.lbl_row_net, color="#173560", bold=True)
        v.addWidget(self.box)

        # Bottom Payment Inputs
        form = QFormLayout()
        form.setVerticalSpacing(8)

        self.f_amount = QDoubleSpinBox()
        self.f_amount.setRange(0, 1000000)
        self.f_amount.setPrefix("₹ ")
        self.f_amount.setStyleSheet("font-size: 13px; font-weight: 800; padding: 6px; color: #059669;")

        self.f_method = QComboBox()
        self.f_method.addItems(["Cash", "UPI", "Bank", "Other"])
        self.f_method.setStyleSheet("font-size: 12px; padding: 5px;")

        self.f_notes = QLineEdit()
        self.f_notes.setStyleSheet("font-size: 12px; padding: 5px;")

        form.addRow(_lab("Confirm Paid Amount *"), self.f_amount)
        form.addRow(_lab("Payment Method"), self.f_method)
        form.addRow(_lab("Notes / Remarks"), self.f_notes)
        v.addLayout(form)

        # Dialog Buttons
        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setStyleSheet(
            "QPushButton { background: #F1F5F9; color: #475569; font-weight: 600; "
            "border: 1px solid #CBD5E1; border-radius: 6px; padding: 7px 16px; font-size: 12px; }"
        )
        cancel.clicked.connect(self.reject)

        save = QPushButton("✓ Confirm Payment Done")
        save.setStyleSheet(
            "QPushButton { background: #059669; color: #FFFFFF; font-weight: 800; "
            "border: none; border-radius: 6px; padding: 8px 22px; font-size: 12px; } "
            "QPushButton:hover { background: #047857; }"
        )
        save.clicked.connect(self._save)

        btns.addWidget(cancel)
        btns.addWidget(save)
        v.addLayout(btns)

        # Initial calculation
        self._current_cycle = {}
        self._recalculate_cycle()

    def _on_cutoff_date_changed(self):
        self._recalculate_cycle()

    def _recalculate_cycle(self):
        qd = self.f_end_date.date()
        cutoff_d = date(qd.year(), qd.month(), qd.day())
        if self.worker_id:
            cycle = worker_service.get_worker_active_cycle(self.worker_id, up_to_date=cutoff_d)
            self._current_cycle = cycle
            self.lbl_row_period.setText(cycle.get("period_label", "—"))
            self.lbl_row_units.setText(f"{cycle.get('total_units', 0.0):.1f} Days")
            self.lbl_row_earn.setText(_money(cycle.get("total_work_earning", 0.0)))
            self.lbl_row_travel.setText(f"+ {_money(cycle.get('total_travel', 0.0))}")
            self.lbl_row_add.setText(f"+ {_money(cycle.get('total_additions', 0.0))}")
            self.lbl_row_gross.setText(_money(cycle.get("gross_payable", 0.0)))
            self.lbl_row_adv.setText(f"- {_money(cycle.get('total_advances', 0.0))}")
            self.lbl_row_ded.setText(f"- {_money(cycle.get('total_deductions', 0.0))}")
            net = cycle.get("net_payable", 0.0)
            self.lbl_row_net.setText(_money(net))
            self.f_amount.setValue(max(0.0, float(net)))
            self.f_notes.setText(f"Payment Done up to {cutoff_d.strftime('%d %b %Y')}")
        else:
            self.lbl_row_period.setText(f"{self.summary.get('month_name', '')} {self.summary.get('year', '')}")
            self.lbl_row_units.setText(f"{self.summary.get('total_units', 0.0):.1f} Days")
            self.lbl_row_earn.setText(_money(self.summary.get("total_work_earning", 0.0)))
            self.lbl_row_travel.setText(f"+ {_money(self.summary.get('total_travel', 0.0))}")
            self.lbl_row_add.setText(f"+ {_money(self.summary.get('total_additions', 0.0))}")
            self.lbl_row_gross.setText(_money(self.summary.get("gross_payable", 0.0)))
            self.lbl_row_adv.setText(f"- {_money(self.summary.get('total_advance', 0.0))}")
            self.lbl_row_ded.setText(f"- {_money(self.summary.get('total_deductions', 0.0))}")
            net = self.summary.get("net_payable", 0.0)
            self.lbl_row_net.setText(_money(net))
            self.f_amount.setValue(max(0.0, float(net)))
            self.f_notes.setText(f"Final settlement for {self.summary.get('month_name', '')} {self.summary.get('year', '')}")

    def _save(self):
        qd = self.f_end_date.date()
        cutoff_d = date(qd.year(), qd.month(), qd.day())
        st_d = self._current_cycle.get("start_date")
        self._data = {
            "start_date": st_d,
            "end_date": cutoff_d,
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
        tc.setContentsMargins(0, 0, 0, 0)
        tc.setSpacing(6)
        lbl_trv = QLabel("Travel / Rickshaw Expense (optional)")
        lbl_trv.setStyleSheet("font-size:11px; font-weight:800; color:#059669;")
        tc.addWidget(lbl_trv)

        trv_row = QHBoxLayout()
        trv_row.setSpacing(8)
        self.f_trv = QDoubleSpinBox()
        self.f_trv.setRange(0, 100000)
        self.f_trv.setPrefix("Rs. ")
        self.f_trv.setValue(self.existing.get("travel_amount", 0.0))
        trv_row.addWidget(self.f_trv, 2)
        self.f_trv_cat = QComboBox()
        self.f_trv_cat.setEditable(True)
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
        ac.setContentsMargins(0, 0, 0, 0)
        ac.setSpacing(6)
        lbl_adv = QLabel("Advance Payment (optional)")
        lbl_adv.setStyleSheet("font-size:11px; font-weight:800; color:#DC2626;")
        ac.addWidget(lbl_adv)

        adv_row = QHBoxLayout()
        adv_row.setSpacing(8)
        self.f_adv = QDoubleSpinBox()
        self.f_adv.setRange(0, 1000000)
        self.f_adv.setPrefix("Rs. ")
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

    @staticmethod
    def _clear_table_widgets(tbl: QTableWidget):
        """Safely remove and delete all child cell widgets to avoid orphan widgets on the viewport."""
        tbl.clearSpans()
        for r in range(tbl.rowCount()):
            for c in range(tbl.columnCount()):
                cw = tbl.cellWidget(r, c)
                if cw:
                    tbl.removeCellWidget(r, c)
                    cw.setParent(None)
                    cw.deleteLater()
        tbl.clearContents()

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
        self.tab_pdone = self._build_payment_done_tab()

        self.tabs.addTab(self.tab_directory, "👥 Worker List")
        self.tabs.addTab(self.tab_attendance, "⚡ Daily Attendance")
        self.tabs.addTab(self.tab_history, "📋 Monthly History")
        self.tabs.addTab(self.tab_settlement, "💵 Payments && Settlement")
        self.tabs.addTab(self.tab_pdone, "✅ Payment Done")

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
        self.att_date_edit.setDisplayFormat("dd MMM yyyy")
        self.att_date_edit.setDate(QDate.currentDate())
        self.att_date_edit.setMaximumDate(QDate.currentDate())  # Cannot go to future
        self.att_date_edit.dateChanged.connect(self._load_daily_attendance_data)
        self.att_date_edit.setStyleSheet("font-size: 12px; font-weight: 700; padding: 4px 8px; min-width: 110px;")
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
        self.table_att.setColumnWidth(4, 490)

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

        self.lbl_hist_settle_badge = QLabel("")
        self.lbl_hist_settle_badge.setVisible(False)
        tb.addWidget(self.lbl_hist_settle_badge)

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
        self.table_hist.setColumnWidth(8, 115)

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
        self.lbl_hist_net_title = QLabel("FINAL NET PAYABLE:")
        self.lbl_hist_net_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #F59E0B; letter-spacing: 0.5px;")
        self.lbl_hf_net = QLabel("₹ 0.00")
        self.lbl_hf_net.setStyleSheet("font-size: 14px; font-weight: 900; color: #FFFFFF;")
        l_net.addWidget(self.lbl_hist_net_title)
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

        # ── Toolbar ──────────────────────────────────────────────────────────
        tb = QHBoxLayout()
        tb.setSpacing(12)

        lbl_w = QLabel("Select Worker:")
        lbl_w.setStyleSheet("font-size: 12px; font-weight: 700; color: #334155;")
        tb.addWidget(lbl_w)
        self.cb_pay_worker = QComboBox()
        self.cb_pay_worker.setFixedWidth(260)
        self.cb_pay_worker.setStyleSheet("""
            QComboBox {
                font-size: 12px; font-weight: 600; padding: 6px 12px;
                border: 1px solid #CBD5E1; border-radius: 6px; background: #FFFFFF; color: #0F172A;
            }
            QComboBox:hover { border: 1px solid #94A3B8; }
            QComboBox::drop-down { border: none; padding-right: 8px; }
        """)
        self.cb_pay_worker.currentIndexChanged.connect(self._load_settlement_data)
        tb.addWidget(self.cb_pay_worker)

        lbl_m = QLabel("Month & Year:")
        lbl_m.setStyleSheet("font-size: 12px; font-weight: 700; color: #334155;")
        tb.addWidget(lbl_m)
        self.cb_pay_month = QComboBox()
        self.cb_pay_month.setStyleSheet("""
            QComboBox {
                font-size: 12px; font-weight: 600; padding: 6px 12px;
                border: 1px solid #CBD5E1; border-radius: 6px; background: #FFFFFF; color: #0F172A;
            }
        """)
        for m in range(1, 13):
            self.cb_pay_month.addItem(calendar.month_name[m], m)
        self.cb_pay_month.setCurrentIndex(date.today().month - 1)
        self.cb_pay_month.currentIndexChanged.connect(self._load_settlement_data)
        tb.addWidget(self.cb_pay_month)

        self.cb_pay_year = QComboBox()
        self.cb_pay_year.setStyleSheet("""
            QComboBox {
                font-size: 12px; font-weight: 600; padding: 6px 12px;
                border: 1px solid #CBD5E1; border-radius: 6px; background: #FFFFFF; color: #0F172A;
            }
        """)
        cur_year = date.today().year
        for y in range(cur_year - 2, cur_year + 3):
            self.cb_pay_year.addItem(str(y), y)
        self.cb_pay_year.setCurrentText(str(cur_year))
        self.cb_pay_year.currentIndexChanged.connect(self._load_settlement_data)
        tb.addWidget(self.cb_pay_year)

        tb.addStretch(1)

        def _tb_btn(text: str, bg: str, hover: str):
            b = QPushButton(text)
            b.setCursor(Qt.PointingHandCursor)
            b.setStyleSheet(f"""
                QPushButton {{
                    background: {bg}; color: #FFFFFF; font-weight: 700;
                    border-radius: 6px; padding: 7px 15px; font-size: 11px; border: none;
                }}
                QPushButton:hover {{ background: {hover}; }}
            """)
            return b

        btn_add_adv = _tb_btn("+ Advance", "#DC2626", "#B91C1C")
        btn_add_adv.setToolTip("Record a cash or UPI advance payment given to worker")
        btn_add_adv.clicked.connect(self._open_advance_dialog)
        tb.addWidget(btn_add_adv)

        btn_add_exp = _tb_btn("+ Travel", "#059669", "#047857")
        btn_add_exp.setToolTip("Record rickshaw, bus, or travel expenses for site work")
        btn_add_exp.clicked.connect(self._open_travel_dialog)
        tb.addWidget(btn_add_exp)

        btn_add_adj = _tb_btn("+ Adjustment", "#173560", "#0F2342")
        btn_add_adj.setToolTip("Record special bonus addition or penalty deduction")
        btn_add_adj.clicked.connect(self._open_adjustment_dialog)
        tb.addWidget(btn_add_adj)

        lay.addLayout(tb)

        # ── Splitter: Left (Transactions Tables) | Right (Settlement Card) ───
        split = QSplitter(Qt.Horizontal)
        split.setHandleWidth(8)
        split.setStyleSheet("""
            QSplitter::handle {
                background: #E2E8F0;
                border-radius: 4px;
                margin: 2px;
            }
            QSplitter::handle:hover {
                background: #94A3B8;
            }
        """)

        # ── LEFT PANE: Transaction Sub-Tabs ──────────────────────────────────
        left_box = QWidget()
        lb_lay = QVBoxLayout(left_box)
        lb_lay.setContentsMargins(0, 0, 6, 0)
        lb_lay.setSpacing(0)

        self.trans_subtabs = QTabWidget()
        self.trans_subtabs.setStyleSheet("""
            QTabWidget::pane {
                border: 1.5px solid #CBD5E1;
                border-radius: 0 8px 8px 8px;
                background: #FFFFFF;
            }
            QTabBar::tab {
                background: #F8FAFC;
                color: #475569;
                font-weight: 700;
                font-size: 11px;
                padding: 8px 12px;
                border: 1px solid #CBD5E1;
                border-bottom: none;
                border-radius: 6px 6px 0 0;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background: #FFFFFF;
                color: #173560;
                font-weight: 800;
                border-top: 2px solid #173560;
            }
            QTabBar::tab:hover:!selected {
                background: #EDF2F7;
                color: #173560;
            }
        """)

        # Tab 1: Advances Given
        tab_adv_widget = QWidget()
        t1_lay = QVBoxLayout(tab_adv_widget)
        t1_lay.setContentsMargins(10, 10, 10, 10)
        t1_lay.setSpacing(8)

        t1_hdr = QHBoxLayout()
        self.lbl_subtab_adv_total = QLabel("Total Advances: ₹ 0.00")
        self.lbl_subtab_adv_total.setStyleSheet("""
            background: #FEF2F2; color: #DC2626; font-size: 11px; font-weight: 800;
            padding: 4px 10px; border-radius: 4px; border: 1px solid #FECACA;
        """)
        t1_hdr.addWidget(self.lbl_subtab_adv_total)
        t1_hdr.addStretch(1)
        btn_adv_fast = QPushButton("+ Record Advance")
        btn_adv_fast.setCursor(Qt.PointingHandCursor)
        btn_adv_fast.setStyleSheet("""
            QPushButton {
                background: #DC2626; color: white; font-weight: 700; font-size: 10px;
                border-radius: 4px; padding: 4px 10px; border: none;
            }
            QPushButton:hover { background: #B91C1C; }
        """)
        btn_adv_fast.clicked.connect(self._open_advance_dialog)
        t1_hdr.addWidget(btn_adv_fast)
        t1_lay.addLayout(t1_hdr)

        self.table_advances = self._make_sub_table(["Date", "Amount", "Method", "Notes / Purpose", "Action"], is_adj=False)
        t1_lay.addWidget(self.table_advances, 1)
        self.trans_subtabs.addTab(tab_adv_widget, "💵 Advances Given (-)")

        # Tab 2: Travel Expenses
        tab_trv_widget = QWidget()
        t2_lay = QVBoxLayout(tab_trv_widget)
        t2_lay.setContentsMargins(10, 10, 10, 10)
        t2_lay.setSpacing(8)

        t2_hdr = QHBoxLayout()
        self.lbl_subtab_trv_total = QLabel("Total Travel: ₹ 0.00")
        self.lbl_subtab_trv_total.setStyleSheet("""
            background: #ECFDF5; color: #059669; font-size: 11px; font-weight: 800;
            padding: 4px 10px; border-radius: 4px; border: 1px solid #A7F3D0;
        """)
        t2_hdr.addWidget(self.lbl_subtab_trv_total)
        t2_hdr.addStretch(1)
        btn_trv_fast = QPushButton("+ Record Travel")
        btn_trv_fast.setCursor(Qt.PointingHandCursor)
        btn_trv_fast.setStyleSheet("""
            QPushButton {
                background: #059669; color: white; font-weight: 700; font-size: 10px;
                border-radius: 4px; padding: 4px 10px; border: none;
            }
            QPushButton:hover { background: #047857; }
        """)
        btn_trv_fast.clicked.connect(self._open_travel_dialog)
        t2_hdr.addWidget(btn_trv_fast)
        t2_lay.addLayout(t2_hdr)

        self.table_travel = self._make_sub_table(["Date", "Amount", "Category", "Route / Notes", "Action"], is_adj=False)
        t2_lay.addWidget(self.table_travel, 1)
        self.trans_subtabs.addTab(tab_trv_widget, "🛵 Travel / Rickshaw (+)")

        # Tab 3: Adjustments
        tab_adj_widget = QWidget()
        t3_lay = QVBoxLayout(tab_adj_widget)
        t3_lay.setContentsMargins(10, 10, 10, 10)
        t3_lay.setSpacing(8)

        t3_hdr = QHBoxLayout()
        self.lbl_subtab_adj_total = QLabel("Net Adjustments: ₹ 0.00")
        self.lbl_subtab_adj_total.setStyleSheet("""
            background: #EFF6FF; color: #1E40AF; font-size: 11px; font-weight: 800;
            padding: 4px 10px; border-radius: 4px; border: 1px solid #BFDBFE;
        """)
        t3_hdr.addWidget(self.lbl_subtab_adj_total)
        t3_hdr.addStretch(1)
        btn_adj_fast = QPushButton("+ Add Adjustment")
        btn_adj_fast.setCursor(Qt.PointingHandCursor)
        btn_adj_fast.setStyleSheet("""
            QPushButton {
                background: #173560; color: white; font-weight: 700; font-size: 10px;
                border-radius: 4px; padding: 4px 10px; border: none;
            }
            QPushButton:hover { background: #0F2342; }
        """)
        btn_adj_fast.clicked.connect(self._open_adjustment_dialog)
        t3_hdr.addWidget(btn_adj_fast)
        t3_lay.addLayout(t3_hdr)

        self.table_adjustments = self._make_sub_table(["Date", "Type", "Category", "Amount", "Reason / Notes", "Action"], is_adj=True)
        t3_lay.addWidget(self.table_adjustments, 1)
        self.trans_subtabs.addTab(tab_adj_widget, "⚖ Other Additions && Deductions")

        # Tab 4: Past Settlement History
        tab_shist_widget = QWidget()
        t4_lay = QVBoxLayout(tab_shist_widget)
        t4_lay.setContentsMargins(10, 10, 10, 10)
        t4_lay.setSpacing(8)

        t4_hdr = QHBoxLayout()
        self.lbl_subtab_shist_total = QLabel("All Recorded Settlements for Selected Worker")
        self.lbl_subtab_shist_total.setStyleSheet("""
            background: #F0FDF4; color: #166534; font-size: 11px; font-weight: 800;
            padding: 4px 10px; border-radius: 4px; border: 1px solid #BBF7D0;
        """)
        t4_hdr.addWidget(self.lbl_subtab_shist_total)
        t4_hdr.addStretch(1)
        t4_lay.addLayout(t4_hdr)

        self.table_settle_hist = self._make_sub_table(
            ["Month", "Days", "Earnings", "Advances", "Paid Amount", "Paid Date", "Mode", "Status"],
            is_adj=False
        )
        t4_lay.addWidget(self.table_settle_hist, 1)
        self.trans_subtabs.addTab(tab_shist_widget, "📜 Settlement History")

        lb_lay.addWidget(self.trans_subtabs)
        split.addWidget(left_box)

        # ── RIGHT PANE: Executive Settlement Statement Card ──────────────────
        right_scroll = QScrollArea()
        right_scroll.setWidgetResizable(True)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        right_scroll.setFrameShape(QFrame.NoFrame)
        right_scroll.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical {
                width: 6px; background: transparent; border-radius: 3px;
            }
            QScrollBar::handle:vertical {
                background: #CBD5E1; border-radius: 3px; min-height: 24px;
            }
            QScrollBar::handle:vertical:hover {
                background: #94A3B8;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)

        right_card = QFrame()
        right_card.setObjectName("settlementCardFrame")
        right_card.setStyleSheet("""
            QFrame#settlementCardFrame {
                background: #FFFFFF;
                border: 1.5px solid #CBD5E1;
                border-radius: 10px;
            }
        """)
        rc_lay = QVBoxLayout(right_card)
        rc_lay.setContentsMargins(10, 8, 10, 8)
        rc_lay.setSpacing(5)

        # 1. Card Header Banner
        card_hdr = QFrame()
        card_hdr.setObjectName("scHeader")
        card_hdr.setStyleSheet("""
            QFrame#scHeader {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0F2342, stop:1 #1E3A8A);
                border-radius: 7px;
            }
            QFrame#scHeader QLabel {
                background: transparent;
                border: none;
            }
        """)
        hdr_lay = QVBoxLayout(card_hdr)
        hdr_lay.setContentsMargins(12, 7, 12, 7)
        hdr_lay.setSpacing(1)

        hdr_top = QHBoxLayout()
        hdr_top.setSpacing(8)
        self.lbl_sc_header_name = QLabel("Monthly Salary Statement")
        self.lbl_sc_header_name.setFont(QFont("Segoe UI", 12, QFont.Bold))
        self.lbl_sc_header_name.setStyleSheet("color: #FFFFFF; font-weight: 800; font-size: 13px;")
        hdr_top.addWidget(self.lbl_sc_header_name, 1)

        self.lbl_sc_status = QLabel("PENDING")
        self.lbl_sc_status.setAlignment(Qt.AlignCenter)
        self.lbl_sc_status.setStyleSheet("""
            background: #FEF3C7; color: #92400E; font-size: 9.5px; font-weight: 800;
            border-radius: 3px; padding: 2px 7px; border: 1px solid #FCD34D;
        """)
        hdr_top.addWidget(self.lbl_sc_status)
        hdr_lay.addLayout(hdr_top)

        self.lbl_sc_header_month = QLabel("Select worker and month above")
        self.lbl_sc_header_month.setFont(QFont("Segoe UI", 9))
        self.lbl_sc_header_month.setStyleSheet("color: #93C5FD; font-size: 10.5px;")
        hdr_lay.addWidget(self.lbl_sc_header_month)
        rc_lay.addWidget(card_hdr)

        # Helper: section header label
        def _section_title(icon: str, title: str, subtitle: str, fg: str) -> QWidget:
            w_sec = QWidget()
            w_sec.setStyleSheet("background: transparent; border: none;")
            h_sec = QHBoxLayout(w_sec)
            h_sec.setContentsMargins(2, 1, 2, 0)
            h_sec.setSpacing(5)
            t_lbl = QLabel(f"{icon}  <b>{title}</b>")
            t_lbl.setStyleSheet(f"font-size: 10px; font-weight: 800; color: {fg}; letter-spacing: 0.5px; border: none; background: transparent;")
            s_lbl = QLabel(subtitle)
            s_lbl.setStyleSheet("font-size: 9.5px; color: #64748B; border: none; background: transparent;")
            s_lbl.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            h_sec.addWidget(t_lbl)
            h_sec.addStretch(1)
            h_sec.addWidget(s_lbl)
            return w_sec

        # Helper: card row — returns (frame, value_QLabel, sub_QLabel_or_None)
        def _card_row(label: str, value: str, val_color: str = "#0F172A",
                      bold_val: bool = False, bg: str = "transparent", sub: str = None) -> tuple:
            rf = QFrame()
            rf.setObjectName("cardRow")
            rf.setStyleSheet(f"QFrame#cardRow {{ background: {bg}; border: none; }}")
            rh = QHBoxLayout(rf)
            rh.setContentsMargins(10, 4, 10, 4)
            rh.setSpacing(6)

            lbl_sub = None
            if sub:
                lh = QVBoxLayout()
                lh.setSpacing(0)
                lbl_t = QLabel(label)
                lbl_t.setStyleSheet("font-size: 11px; color: #1E293B; font-weight: 600; border: none; background: transparent;")
                lbl_sub = QLabel(sub)
                lbl_sub.setStyleSheet("font-size: 9px; color: #64748B; font-weight: 500; border: none; background: transparent;")
                lh.addWidget(lbl_t)
                lh.addWidget(lbl_sub)
                rh.addLayout(lh, 1)
            else:
                lbl_t = QLabel(label)
                lbl_t.setStyleSheet("font-size: 11.5px; color: #1E293B; font-weight: 600; border: none; background: transparent;")
                rh.addWidget(lbl_t, 1)

            lbl_v = QLabel(value)
            lbl_v.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            weight = "900" if bold_val else "700"
            size = "12px" if bold_val else "11.5px"
            lbl_v.setStyleSheet(f"font-size: {size}; color: {val_color}; font-weight: {weight}; border: none; background: transparent;")
            rh.addWidget(lbl_v)
            return rf, lbl_v, lbl_sub

        def _divider() -> QFrame:
            d = QFrame()
            d.setFrameShape(QFrame.HLine)
            d.setStyleSheet("background: #E2E8F0; border: none; max-height: 1px; margin: 0px;")
            d.setFixedHeight(1)
            return d

        # 2. Earnings Section
        rc_lay.addWidget(_section_title("📈", "EARNINGS", "Work & Conveyance", "#1E40AF"))
        earn_card = QFrame()
        earn_card.setObjectName("scEarnCard")
        earn_card.setStyleSheet("""
            QFrame#scEarnCard {
                background: #FFFFFF;
                border: 1px solid #BFDBFE;
                border-radius: 7px;
            }
            QFrame#scEarnCard QLabel {
                background: transparent;
                border: none;
            }
        """)
        earn_vl = QVBoxLayout(earn_card)
        earn_vl.setContentsMargins(0, 0, 0, 0)
        earn_vl.setSpacing(0)

        f0, self.lbl_sc_work,   self.lbl_sc_work_sub   = _card_row("Base Attendance:",       "₹ 0.00",    "#1E293B", bg="#F8FAFC", sub="Days worked × rate")
        f1, self.lbl_sc_travel, self.lbl_sc_travel_sub = _card_row("(+) Travel / Rickshaw:", "+ ₹ 0.00",  "#047857", bg="#FFFFFF", sub="Site conveyance reimbursements")
        f2, self.lbl_sc_add,    self.lbl_sc_add_sub    = _card_row("(+) Other Additions:",   "+ ₹ 0.00",  "#047857", bg="#FFFFFF", sub="Bonuses & allowances")
        f3, self.lbl_sc_gross,  _                      = _card_row("Gross Payable:",         "₹ 0.00",    "#1E40AF", bold_val=True, bg="#EFF6FF", sub="Total earned before deductions")

        for f in [f0, f1, f2, f3]:
            earn_vl.addWidget(f)
            if f is not f3:
                earn_vl.addWidget(_divider())
        rc_lay.addWidget(earn_card)

        # 3. Deductions Section
        rc_lay.addWidget(_section_title("📉", "DEDUCTIONS", "Advances & Deductions", "#991B1B"))
        ded_card = QFrame()
        ded_card.setObjectName("scDedCard")
        ded_card.setStyleSheet("""
            QFrame#scDedCard {
                background: #FFFFFF;
                border: 1px solid #FECACA;
                border-radius: 7px;
            }
            QFrame#scDedCard QLabel {
                background: transparent;
                border: none;
            }
        """)
        ded_vl = QVBoxLayout(ded_card)
        ded_vl.setContentsMargins(0, 0, 0, 0)
        ded_vl.setSpacing(0)

        f4, self.lbl_sc_adv,     self.lbl_sc_adv_sub = _card_row("(-) Advance Payments:", "- ₹ 0.00", "#DC2626", bg="#FFF5F5", sub="Cash / UPI advances given")
        f5, self.lbl_sc_ded,     self.lbl_sc_ded_sub = _card_row("(-) Other Deductions:", "- ₹ 0.00", "#DC2626", bg="#FFFFFF", sub="Damage / penalty / adjustments")
        f5_tot, self.lbl_sc_tot_ded, _               = _card_row("Total Deductions:",     "- ₹ 0.00", "#991B1B", bold_val=True, bg="#FEF2F2")

        for f in [f4, f5, f5_tot]:
            ded_vl.addWidget(f)
            if f is not f5_tot:
                ded_vl.addWidget(_divider())
        rc_lay.addWidget(ded_card)

        # 4. Final Net Hero Card
        net_hero = QFrame()
        net_hero.setObjectName("scNetHero")
        net_hero.setStyleSheet("""
            QFrame#scNetHero {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #064E3B, stop:1 #059669);
                border-radius: 8px;
            }
            QFrame#scNetHero QLabel {
                background: transparent;
                border: none;
            }
        """)
        nh_lay = QVBoxLayout(net_hero)
        nh_lay.setContentsMargins(12, 7, 12, 7)
        nh_lay.setSpacing(1)

        nh_top = QHBoxLayout()
        lbl_net_t = QLabel("FINAL NET PAYABLE:")
        lbl_net_t.setStyleSheet("font-size: 10px; font-weight: 800; color: #A7F3D0; letter-spacing: 0.8px;")
        self.lbl_sc_net = QLabel("₹ 0.00")
        self.lbl_sc_net.setStyleSheet("font-size: 18px; font-weight: 900; color: #FFFFFF;")
        self.lbl_sc_net.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        nh_top.addWidget(lbl_net_t)
        nh_top.addStretch(1)
        nh_top.addWidget(self.lbl_sc_net)
        nh_lay.addLayout(nh_top)

        self.lbl_sc_net_sub = QLabel("Net payout after all advance & expense adjustments")
        self.lbl_sc_net_sub.setStyleSheet("font-size: 9.5px; color: #D1FAE5;")
        nh_lay.addWidget(self.lbl_sc_net_sub)
        rc_lay.addWidget(net_hero)

        # 5. Settlement & Payment Reconciliation
        rc_lay.addWidget(_section_title("💳", "SETTLEMENT STATUS", "Paid vs Remaining", "#166534"))
        pay_card = QFrame()
        pay_card.setObjectName("scPayCard")
        pay_card.setStyleSheet("""
            QFrame#scPayCard {
                background: #FFFFFF;
                border: 1px solid #CBD5E1;
                border-radius: 7px;
            }
            QFrame#scPayCard QLabel {
                background: transparent;
                border: none;
            }
        """)
        pay_vl = QVBoxLayout(pay_card)
        pay_vl.setContentsMargins(0, 0, 0, 0)
        pay_vl.setSpacing(0)

        f6, self.lbl_sc_paid, _ = _card_row("Already Paid:",   "₹ 0.00", "#047857", bg="#F0FDF4", sub="Recorded settlement payments")
        f7, self.lbl_sc_rem,  _ = _card_row("Remaining Due:", "₹ 0.00", "#DC2626", bold_val=True, bg="#FEF2F2", sub="Pending worker payout")

        pay_vl.addWidget(f6)
        pay_vl.addWidget(_divider())
        pay_vl.addWidget(f7)
        rc_lay.addWidget(pay_card)

        # 6. Action Buttons
        self.btn_settle_action = QPushButton("💰   Settle Month / Record Payment")
        self.btn_settle_action.setCursor(Qt.PointingHandCursor)
        self.btn_settle_action.setMinimumHeight(38)
        self.btn_settle_action.setStyleSheet("""
            QPushButton {
                background: #173560; color: #FFFFFF; font-weight: 800;
                border: none; border-radius: 7px; font-size: 12px;
            }
            QPushButton:hover { background: #0F2342; }
        """)
        self.btn_settle_action.clicked.connect(self._open_settlement_dialog)
        rc_lay.addWidget(self.btn_settle_action)

        self.btn_view_slip_card = QPushButton("📸   View & Share Salary Slip (Photo Card)")
        self.btn_view_slip_card.setCursor(Qt.PointingHandCursor)
        self.btn_view_slip_card.setMinimumHeight(36)
        self.btn_view_slip_card.setStyleSheet("""
            QPushButton {
                background: #059669; color: #FFFFFF; font-weight: 700;
                border: none; border-radius: 7px; font-size: 11.5px;
            }
            QPushButton:hover { background: #047857; }
        """)
        self.btn_view_slip_card.clicked.connect(self._open_summary_slip)
        rc_lay.addWidget(self.btn_view_slip_card)

        rc_lay.addStretch(1)
        right_scroll.setWidget(right_card)
        split.addWidget(right_scroll)

        split.setSizes([640, 380])
        lay.addWidget(split, 1)

        return w

    # -------------------------------------------------------------------------
    # Tab 5: Payment Done Ledger & Confirmed Vouchers
    # -------------------------------------------------------------------------
    def _build_payment_done_tab(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        # ── 1. Top KPI Summary Strip for Confirmed Payouts ───────────────────
        kpi_row = QHBoxLayout()
        kpi_row.setSpacing(12)

        def _pdone_kpi_card(title: str, val_attr: str, subtext: str, accent: str):
            c = QFrame()
            c.setObjectName("pdoneKpiCard")
            c.setStyleSheet(f"""
                QFrame#pdoneKpiCard {{
                    background: #FFFFFF; border: 1.5px solid #E2E8F0;
                    border-top: 3.5px solid {accent}; border-radius: 8px; padding: 10px 14px;
                }}
                QFrame#pdoneKpiCard QLabel {{
                    border: none; background: transparent;
                }}
            """)
            cl = QVBoxLayout(c)
            cl.setContentsMargins(0, 0, 0, 0)
            cl.setSpacing(2)
            lt = QLabel(title)
            lt.setStyleSheet("font-size: 9.5px; font-weight: 800; color: #64748B; letter-spacing: 0.5px;")
            lv = QLabel("—")
            lv.setStyleSheet(f"font-size: 17px; font-weight: 900; color: {accent};")
            ls = QLabel(subtext)
            ls.setStyleSheet("font-size: 9px; color: #94A3B8;")
            cl.addWidget(lt)
            cl.addWidget(lv)
            cl.addWidget(ls)
            setattr(self, val_attr, lv)
            return c

        kpi_row.addWidget(_pdone_kpi_card("TOTAL PAID OUT", "lbl_pdone_kpi_total", "Confirmed Paid Dues", "#059669"), 1)
        kpi_row.addWidget(_pdone_kpi_card("TOTAL VOUCHERS", "lbl_pdone_kpi_vouchers", "Confirmed Settlements", "#2563EB"), 1)
        kpi_row.addWidget(_pdone_kpi_card("SETTLED WORKERS", "lbl_pdone_kpi_workers", "Workers with Confirmed Pay", "#7C3AED"), 1)
        lay.addLayout(kpi_row)

        # ── 2. Filters & Actions Toolbar ─────────────────────────────────────
        tb = QHBoxLayout()
        tb.setSpacing(10)

        self.f_pdone_search = QLineEdit()
        self.f_pdone_search.setPlaceholderText("🔍 Search by Voucher #, Worker Name, Mode...")
        self.f_pdone_search.setClearButtonEnabled(True)
        self.f_pdone_search.setStyleSheet("""
            QLineEdit {
                font-size: 12px; padding: 6px 12px; border: 1px solid #CBD5E1;
                border-radius: 6px; background: #FFFFFF; min-width: 240px;
            }
            QLineEdit:focus { border: 1.5px solid #173560; }
        """)
        self.f_pdone_search.textChanged.connect(self._load_payment_done_data)
        tb.addWidget(self.f_pdone_search)

        lbl_w = QLabel("Worker:")
        lbl_w.setStyleSheet("font-size: 11px; font-weight: 700; color: #475569;")
        tb.addWidget(lbl_w)

        self.cb_pdone_worker = QComboBox()
        self.cb_pdone_worker.setFixedWidth(200)
        self.cb_pdone_worker.setStyleSheet("""
            QComboBox {
                font-size: 12px; font-weight: 600; padding: 6px 10px;
                border: 1px solid #CBD5E1; border-radius: 6px; background: #FFFFFF;
            }
        """)
        self.cb_pdone_worker.addItem("All Workers", None)
        self.cb_pdone_worker.currentIndexChanged.connect(self._load_payment_done_data)
        tb.addWidget(self.cb_pdone_worker)

        lbl_m = QLabel("Month:")
        lbl_m.setStyleSheet("font-size: 11px; font-weight: 700; color: #475569;")
        tb.addWidget(lbl_m)

        self.cb_pdone_month = QComboBox()
        self.cb_pdone_month.addItem("All Months", None)
        for m in range(1, 13):
            self.cb_pdone_month.addItem(calendar.month_name[m], m)
        self.cb_pdone_month.currentIndexChanged.connect(self._load_payment_done_data)
        tb.addWidget(self.cb_pdone_month)

        lbl_y = QLabel("Year:")
        lbl_y.setStyleSheet("font-size: 11px; font-weight: 700; color: #475569;")
        tb.addWidget(lbl_y)

        self.cb_pdone_year = QComboBox()
        self.cb_pdone_year.addItem("All Years", None)
        cur_year = date.today().year
        for y in range(cur_year - 2, cur_year + 3):
            self.cb_pdone_year.addItem(str(y), y)
        self.cb_pdone_year.setCurrentIndex(0)
        self.cb_pdone_year.currentIndexChanged.connect(self._load_payment_done_data)
        tb.addWidget(self.cb_pdone_year)

        tb.addStretch(1)

        btn_refresh = QPushButton("↻ Refresh")
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.setStyleSheet("""
            QPushButton {
                background: #F1F5F9; color: #334155; font-weight: 700; font-size: 11px;
                border: 1px solid #CBD5E1; border-radius: 6px; padding: 6px 14px;
            }
            QPushButton:hover { background: #E2E8F0; }
        """)
        btn_refresh.clicked.connect(self._load_payment_done_data)
        tb.addWidget(btn_refresh)

        btn_new_settle = QPushButton("💰 Settle Worker Payment")
        btn_new_settle.setCursor(Qt.PointingHandCursor)
        btn_new_settle.setStyleSheet("""
            QPushButton {
                background: #173560; color: #FFFFFF; font-weight: 800; font-size: 11px;
                border: none; border-radius: 6px; padding: 7px 16px;
            }
            QPushButton:hover { background: #0F2342; }
        """)
        btn_new_settle.clicked.connect(self._open_new_settlement_from_pdone)
        tb.addWidget(btn_new_settle)

        lay.addLayout(tb)

        # ── 3. Main Payments Done Table ──────────────────────────────────────
        self.table_pdone = QTableWidget()
        self.table_pdone.setColumnCount(12)
        self.table_pdone.setHorizontalHeaderLabels([
            "VOUCHER #", "WORKER NAME", "WORK TYPE", "SETTLED PERIOD",
            "DAYS PAID", "WORK EARNINGS", "ADVANCES (-)", "NET PAID",
            "PAYMENT DATE", "MODE", "STATUS", "ACTIONS"
        ])
        hh = self.table_pdone.horizontalHeader()
        hh.setMinimumSectionSize(60)
        for i in range(12):
            hh.setSectionResizeMode(i, QHeaderView.Interactive)

        self.table_pdone.setColumnWidth(0, 125)
        self.table_pdone.setColumnWidth(1, 130)
        self.table_pdone.setColumnWidth(2, 75)
        self.table_pdone.setColumnWidth(3, 180)
        self.table_pdone.setColumnWidth(4, 85)
        self.table_pdone.setColumnWidth(5, 110)
        self.table_pdone.setColumnWidth(6, 95)
        self.table_pdone.setColumnWidth(7, 100)
        self.table_pdone.setColumnWidth(8, 95)
        self.table_pdone.setColumnWidth(9, 65)
        self.table_pdone.setColumnWidth(10, 105)
        self.table_pdone.setColumnWidth(11, 108)

        self.table_pdone.verticalHeader().setVisible(False)
        self.table_pdone.verticalHeader().setDefaultSectionSize(42)
        self.table_pdone.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table_pdone.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table_pdone.setStyleSheet("""
            QTableWidget {
                border: 1px solid #E2E8F0; gridline-color: #F1F5F9;
                font-size: 12px; background: #FFFFFF;
            }
            QTableWidget::item { padding: 4px 8px; }
            QHeaderView::section {
                background: #F8FAFC; color: #334155; font-weight: 700;
                border: none; border-bottom: 2px solid #CBD5E1; border-right: 1px solid #E2E8F0;
                padding: 8px; font-size: 11px;
            }
        """)
        lay.addWidget(self.table_pdone, 1)

        return w

    def _load_payment_done_data(self):
        query = getattr(self, "f_pdone_search", None)
        search_txt = query.text().strip() if query else ""

        w_cb = getattr(self, "cb_pdone_worker", None)
        worker_id = w_cb.currentData() if w_cb else None

        m_cb = getattr(self, "cb_pdone_month", None)
        month = m_cb.currentData() if m_cb else None

        y_cb = getattr(self, "cb_pdone_year", None)
        year = y_cb.currentData() if y_cb else None

        records = worker_service.get_all_payment_done_records(
            worker_id=worker_id,
            year=year,
            month=month,
            search_query=search_txt,
        )

        total_paid = sum(r["paid_amount"] for r in records)
        unique_workers = len(set(r["worker_id"] for r in records))
        if hasattr(self, "lbl_pdone_kpi_total"):
            self.lbl_pdone_kpi_total.setText(_money(total_paid))
        if hasattr(self, "lbl_pdone_kpi_vouchers"):
            self.lbl_pdone_kpi_vouchers.setText(f"{len(records)} Vouchers")
        if hasattr(self, "lbl_pdone_kpi_workers"):
            self.lbl_pdone_kpi_workers.setText(f"{unique_workers} Workers")

        if not hasattr(self, "table_pdone"):
            return

        self._clear_table_widgets(self.table_pdone)

        if not records:
            self.table_pdone.setRowCount(1)
            self.table_pdone.setRowHeight(0, 48)
            self.table_pdone.setSpan(0, 0, 1, self.table_pdone.columnCount())
            empty_it = QTableWidgetItem("ℹ  No confirmed payment records found matching the filters.")
            empty_it.setTextAlignment(Qt.AlignCenter)
            empty_it.setForeground(QColor("#94A3B8"))
            empty_it.setFont(QFont("Segoe UI", 11))
            self.table_pdone.setItem(0, 0, empty_it)
            return

        self.table_pdone.setRowCount(len(records))

        for r, rec in enumerate(records):
            self.table_pdone.setRowHeight(r, 42)

            # Col 0: Voucher #
            v_it = QTableWidgetItem(rec["voucher_no"])
            v_it.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
            v_it.setFont(QFont("Segoe UI", 10, QFont.Bold))
            v_it.setForeground(QColor("#1E40AF"))
            self.table_pdone.setItem(r, 0, v_it)

            # Col 1: Worker Name
            w_it = QTableWidgetItem(rec["worker_name"])
            w_it.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            w_it.setFont(QFont("Segoe UI", 10, QFont.Bold))
            w_it.setForeground(QColor("#0F172A"))
            self.table_pdone.setItem(r, 1, w_it)

            # Col 2: Work Type
            wt_it = QTableWidgetItem(rec["work_type"])
            wt_it.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            wt_it.setFont(QFont("Segoe UI", 10))
            self.table_pdone.setItem(r, 2, wt_it)

            # Col 3: Settled Period
            per_it = QTableWidgetItem(rec["period_label"])
            per_it.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            per_it.setFont(QFont("Segoe UI", 10, QFont.Bold))
            per_it.setForeground(QColor("#334155"))
            self.table_pdone.setItem(r, 3, per_it)

            # Col 4: Days Paid
            d_it = QTableWidgetItem(f"{rec['total_units']:.1f} Days")
            d_it.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
            d_it.setFont(QFont("Segoe UI", 10))
            self.table_pdone.setItem(r, 4, d_it)

            # Col 5: Work Earnings
            e_it = QTableWidgetItem(_money(rec["work_earnings"]))
            e_it.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
            e_it.setFont(QFont("Segoe UI", 10))
            self.table_pdone.setItem(r, 5, e_it)

            # Col 6: Advances (-)
            adv_it = QTableWidgetItem(f"- {_money(rec['total_advances'])}")
            adv_it.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
            adv_it.setFont(QFont("Segoe UI", 10))
            adv_it.setForeground(QColor("#DC2626"))
            self.table_pdone.setItem(r, 6, adv_it)

            # Col 7: Net Paid
            paid_it = QTableWidgetItem(_money(rec["paid_amount"]))
            paid_it.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
            paid_it.setFont(QFont("Segoe UI", 10, QFont.Bold))
            paid_it.setForeground(QColor("#059669"))
            self.table_pdone.setItem(r, 7, paid_it)

            # Col 8: Payment Date
            dt_it = QTableWidgetItem(rec["payment_date_str"])
            dt_it.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
            dt_it.setFont(QFont("Segoe UI", 10))
            self.table_pdone.setItem(r, 8, dt_it)

            # Col 9: Mode
            m_it = QTableWidgetItem(rec["payment_method"])
            m_it.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
            m_it.setFont(QFont("Segoe UI", 10))
            self.table_pdone.setItem(r, 9, m_it)

            # Col 10: Status
            st_w = QWidget()
            st_l = QHBoxLayout(st_w)
            st_l.setContentsMargins(0, 0, 0, 0)
            st_l.setAlignment(Qt.AlignCenter)
            st_lbl = QLabel("✓ CONFIRMED")
            st_lbl.setStyleSheet("""
                background: #DCFCE7; color: #15803D; font-size: 10px; font-weight: 800;
                border-radius: 4px; padding: 3px 8px; border: 1px solid #86EFAC;
            """)
            st_l.addWidget(st_lbl)
            self.table_pdone.setCellWidget(r, 10, st_w)

            # Col 11: Actions (Slip 📸, WhatsApp 💬, Rollback ↩️)
            act_w = QWidget()
            act_l = QHBoxLayout(act_w)
            act_l.setContentsMargins(4, 2, 4, 2)
            act_l.setSpacing(4)
            act_l.setAlignment(Qt.AlignCenter)

            _emoji_f = QFont("Segoe UI Emoji", 13)

            def _act_btn(symbol, tip, fg, bg, hover):
                b = QPushButton(symbol)
                b.setCursor(Qt.PointingHandCursor)
                b.setToolTip(tip)
                b.setFixedSize(30, 26)
                b.setFont(_emoji_f)
                b.setStyleSheet(
                    f"QPushButton {{ background: {bg}; color: {fg}; "
                    f"border: 1px solid {fg}40; border-radius: 5px; font-size: 13px; }} "
                    f"QPushButton:hover {{ background: {hover}; }}"
                )
                return b

            b_slip = _act_btn("\U0001F4F8", "View and export salary slip card", "#047857", "#ECFDF5", "#A7F3D0")
            b_slip.clicked.connect(lambda _=False, rc=rec: self._open_pdone_slip(rc))
            act_l.addWidget(b_slip)

            b_wa = _act_btn("\U0001F4AC", "Copy WhatsApp payment receipt", "#2563EB", "#EFF6FF", "#BFDBFE")
            b_wa.clicked.connect(lambda _=False, sid=rec["id"]: self._copy_pdone_whatsapp(sid))
            act_l.addWidget(b_wa)

            b_undo = _act_btn("\u21A9", "Rollback settlement (Reopen dates as active)", "#DC2626", "#FEF2F2", "#FECACA")
            b_undo.clicked.connect(lambda _=False, sid=rec["id"], vn=rec["voucher_no"], wn=rec["worker_name"], pl=rec["period_label"]: self._rollback_pdone(sid, vn, wn, pl))
            act_l.addWidget(b_undo)

            self.table_pdone.setCellWidget(r, 11, act_w)

    def _open_pdone_slip(self, rec: dict):
        worker_id = rec["worker_id"]
        biz_name = ""
        try:
            biz = business_service.get_business_profile()
            biz_name = biz.get("name", "")
        except Exception:
            pass

        st_d = rec.get("start_date")
        end_d = rec.get("end_date") or rec.get("payment_date")

        summary = {
            "worker_id": worker_id,
            "name": rec["worker_name"],
            "worker_code": rec.get("worker_code", ""),
            "mobile": rec.get("mobile", ""),
            "work_type": rec.get("work_type", "Staff"),
            "current_daily_rate": rec.get("daily_rate", 0.0),
            "daily_rate": rec.get("daily_rate", 0.0),
            "year": rec["payment_date"].year if rec.get("payment_date") else date.today().year,
            "month": rec["payment_date"].month if rec.get("payment_date") else date.today().month,
            "month_name": rec.get("period_label", "Settled Period"),
            "voucher_no": rec.get("voucher_no", ""),
            "period_label": rec.get("period_label", ""),
            "total_units": rec.get("total_units", 0.0),
            "total_work_earning": rec.get("work_earnings", 0.0),
            "total_travel": max(0.0, rec.get("gross_payable", 0.0) - rec.get("work_earnings", 0.0) - rec.get("total_additions", 0.0)),
            "total_additions": rec.get("total_additions", 0.0),
            "gross_payable": rec.get("gross_payable", 0.0),
            "total_advance": rec.get("total_advances", 0.0),
            "total_deductions": rec.get("total_deductions", 0.0),
            "net_payable": rec.get("paid_amount", 0.0),
            "paid_amount": rec.get("paid_amount", 0.0),
            "remaining_balance": 0.0,
            "payment_date_str": rec.get("payment_date_str", ""),
            "payment_method": rec.get("payment_method", "Cash"),
            "is_settled": True,
            "full_days": int(rec.get("total_units", 0)),
            "half_days": 0,
            "one_and_half_days": 0,
            "double_days": 0,
            "absent_days": 0,
            "custom_days": 0,
            "attendances": [],
            "advances": [],
            "travel_expenses": [],
            "adjustments": [],
        }

        if st_d and end_d:
            session = worker_service.get_session()
            try:
                from app.models.models import WorkerAttendance, WorkerAdvance
                atts = (
                    session.query(WorkerAttendance)
                    .filter(
                        WorkerAttendance.worker_id == worker_id,
                        WorkerAttendance.attendance_date >= st_d,
                        WorkerAttendance.attendance_date <= end_d,
                    )
                    .order_by(WorkerAttendance.attendance_date)
                    .all()
                )
                advs = (
                    session.query(WorkerAdvance)
                    .filter(
                        WorkerAdvance.worker_id == worker_id,
                        WorkerAdvance.advance_date >= st_d,
                        WorkerAdvance.advance_date <= end_d,
                    )
                    .order_by(WorkerAdvance.advance_date)
                    .all()
                )
                summary["attendances"] = [
                    {
                        "date": a.attendance_date,
                        "date_str": a.attendance_date.strftime("%d %b %Y"),
                        "day_multiplier": float(a.day_multiplier or 0),
                        "daily_rate": float(a.daily_rate or 0),
                        "daily_earning": float(a.daily_earning or 0),
                        "status_label": a.status_label or "Present",
                        "notes": a.notes or "",
                    }
                    for a in atts
                ]
                summary["advances"] = [
                    {
                        "id": adv.id,
                        "date": adv.advance_date,
                        "date_str": adv.advance_date.strftime("%d %b %Y"),
                        "amount": float(adv.amount or 0),
                        "payment_method": adv.payment_method or "Cash",
                        "notes": adv.notes or "",
                    }
                    for adv in advs
                ]
            finally:
                session.close()

        dlg = MonthlySummarySlipDialog(self, summary=summary, business_name=biz_name)
        dlg.exec()

    def _copy_pdone_whatsapp(self, settlement_id: int):
        biz_name = ""
        try:
            biz = business_service.get_business_profile()
            biz_name = biz.get("name", "")
        except Exception:
            pass
        txt = worker_service.generate_payment_done_whatsapp_text(settlement_id, business_name=biz_name)
        if txt:
            QGuiApplication.clipboard().setText(txt)
            show_toast(self, "WhatsApp payment voucher receipt copied to clipboard!", "success")
        else:
            show_toast(self, "Could not generate WhatsApp receipt.", "warning")

    def _rollback_pdone(self, settlement_id: int, voucher_no: str, worker_name: str, period_label: str):
        ret = QMessageBox.question(
            self,
            "Confirm Payment Rollback",
            f"Are you sure you want to rollback Payment Voucher {voucher_no}?\n\n"
            f"Worker: {worker_name}\n"
            f"Period: {period_label}\n\n"
            "This will delete the settlement record and reopen all attendance & advance\n"
            "records in this period back into the active pending cycle.",
            QMessageBox.Yes | QMessageBox.No,
        )
        if ret == QMessageBox.Yes:
            success = worker_service.rollback_payment_done(settlement_id)
            if success:
                show_toast(self, f"Voucher {voucher_no} rolled back. Period reopened.", "info")
                self._load_payment_done_data()
                self._load_settlement_data()
                self._load_directory_data()
                self._load_monthly_history_data()
                self._load_daily_attendance_data()
                self._load_kpis()
            else:
                show_toast(self, "Could not rollback settlement.", "danger")

    def _open_new_settlement_from_pdone(self):
        worker_id = getattr(self, "cb_pdone_worker", None) and self.cb_pdone_worker.currentData()
        if not worker_id:
            self.tabs.setCurrentIndex(3)
            return
        idx = self.cb_pay_worker.findData(worker_id)
        if idx >= 0:
            self.cb_pay_worker.setCurrentIndex(idx)
        self._open_settlement_dialog()

    def _make_sub_table(self, headers: list[str], is_adj: bool = False) -> QTableWidget:
        t = QTableWidget(0, len(headers))
        t.setHorizontalHeaderLabels(headers)
        t.verticalHeader().setVisible(False)
        t.verticalHeader().setDefaultSectionSize(38)
        t.setSelectionBehavior(QAbstractItemView.SelectRows)
        t.setEditTriggers(QAbstractItemView.NoEditTriggers)
        t.setAlternatingRowColors(True)
        t.setShowGrid(False)
        t.setStyleSheet("""
            QTableWidget {
                border: 1px solid #E2E8F0;
                background: #FFFFFF;
                alternate-background-color: #F8FAFC;
                gridline-color: transparent;
                border-radius: 6px;
                font-size: 12px;
            }
            QTableWidget::item {
                padding: 4px 10px;
                border-bottom: 1px solid #F1F5F9;
                color: #1E293B;
            }
            QTableWidget::item:selected {
                background: #EFF6FF;
                color: #173560;
            }
            QHeaderView::section {
                background: #F8FAFC;
                color: #334155;
                font-weight: 800;
                border: none;
                border-bottom: 2px solid #CBD5E1;
                border-right: 1px solid #E2E8F0;
                padding: 8px 10px;
                font-size: 11px;
            }
        """)
        if len(headers) == 8:
            # Settlement History: ["Month", "Days", "Earnings", "Advances", "Paid Amount", "Paid Date", "Mode", "Status"]
            for c in range(8):
                t.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeToContents)
        elif not is_adj:
            # ["Date", "Amount", "Method / Category", "Notes / Purpose", "Action"]
            t.setColumnWidth(0, 115)
            t.setColumnWidth(1, 130)
            t.setColumnWidth(2, 120)
            t.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
            t.setColumnWidth(4, 70)
        else:
            # ["Date", "Type", "Category", "Amount", "Reason / Notes", "Action"]
            t.setColumnWidth(0, 115)
            t.setColumnWidth(1, 105)
            t.setColumnWidth(2, 115)
            t.setColumnWidth(3, 130)
            t.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
            t.setColumnWidth(5, 70)
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
        self._load_payment_done_data()

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
        elif idx == 4:
            self._load_payment_done_data()

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

        if hasattr(self, "cb_pdone_worker"):
            curr_id = self.cb_pdone_worker.currentData()
            self.cb_pdone_worker.blockSignals(True)
            self.cb_pdone_worker.clear()
            self.cb_pdone_worker.addItem("All Workers", None)
            for idx, w in enumerate(workers, 1):
                self.cb_pdone_worker.addItem(f"{idx}. {w.name} ({w.work_type})", w.id)
            if curr_id:
                idx = self.cb_pdone_worker.findData(curr_id)
                if idx >= 0:
                    self.cb_pdone_worker.setCurrentIndex(idx)
            self.cb_pdone_worker.blockSignals(False)

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

        self._clear_table_widgets(self.table_dir)
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

            # Check worker's active cycle (cutoff-aware)
            active_cycle = worker_service.get_worker_active_cycle(w.id)
            last_st = active_cycle.get("last_settled_date")
            summary = worker_service.get_worker_monthly_summary(w.id, today.year, today.month)

            if last_st:
                cycle_units = active_cycle.get("total_units", 0.0)
                cycle_gross = active_cycle.get("gross_payable", 0.0)
                cycle_adv = active_cycle.get("total_advances", 0.0)
                cycle_net = active_cycle.get("net_payable", 0.0)
                last_st_str = last_st.strftime("%d %b %Y")

                e_item = QTableWidgetItem(_money(cycle_gross))
                e_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                e_item.setFont(QFont("Segoe UI", 10))
                e_item.setToolTip(f"Active cycle earnings (from {active_cycle.get('period_label', '')})")
                self.table_dir.setItem(r, 5, e_item)

                a_item = QTableWidgetItem(_money(cycle_adv))
                a_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                a_item.setFont(QFont("Segoe UI", 10))
                self.table_dir.setItem(r, 6, a_item)

                if cycle_units > 0 or cycle_net > 0:
                    net_item = QTableWidgetItem(f"{_money(cycle_net)} (New)")
                    net_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                    net_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
                    net_item.setForeground(QColor("#1E40AF"))
                    net_item.setToolTip(
                        f"Paid up to {last_st_str}.\n"
                        f"Active Cycle ({active_cycle.get('period_label', '')}): {cycle_units:.1f} days worked, Net Due: {_money(cycle_net)}"
                    )
                else:
                    net_item = QTableWidgetItem("✓ Paid (₹ 0.00)")
                    net_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                    net_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
                    net_item.setForeground(QColor("#059669"))
                    net_item.setToolTip(f"Fully settled up to {last_st_str}. No active cycle dues.")
                self.table_dir.setItem(r, 7, net_item)
            elif summary:
                monthly_total = summary.get('gross_payable', summary.get('total_work_earning', 0))
                e_item = QTableWidgetItem(_money(monthly_total))
                e_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                e_item.setFont(QFont("Segoe UI", 10))
                self.table_dir.setItem(r, 5, e_item)

                a_item = QTableWidgetItem(_money(summary['total_advance']))
                a_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                a_item.setFont(QFont("Segoe UI", 10))
                self.table_dir.setItem(r, 6, a_item)

                is_settled = summary.get("is_settled", False)
                paid_val = summary.get("paid_amount", 0.0)
                rem_val = summary.get("remaining_balance", 0.0)
                p_date = summary.get("payment_date_str", "")
                p_mode = summary.get("payment_method", "")

                if is_settled or (rem_val <= 0 and paid_val > 0):
                    net_item = QTableWidgetItem("✓ Paid (₹ 0.00)")
                    net_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                    net_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
                    net_item.setForeground(QColor("#059669"))
                    tip = f"Fully Settled: {_money(paid_val)}"
                    if p_date:
                        tip += f" on {p_date}"
                    if p_mode:
                        tip += f" via {p_mode}"
                    net_item.setToolTip(tip)
                elif paid_val > 0 and rem_val > 0:
                    net_item = QTableWidgetItem(f"{_money(rem_val)} (Part)")
                    net_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                    net_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
                    net_item.setForeground(QColor("#D97706"))
                    net_item.setToolTip(f"Paid: {_money(paid_val)}, Remaining Due: {_money(rem_val)}")
                else:
                    net_item = QTableWidgetItem(_money(summary['net_payable']))
                    net_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                    net_item.setFont(QFont("Segoe UI", 10, QFont.Bold))
                    net_item.setForeground(QColor("#173560"))
                    net_item.setToolTip(f"Pending Payout: {_money(summary['net_payable'])}")
                self.table_dir.setItem(r, 7, net_item)
            else:
                for c in range(5, 8):
                    dash = QTableWidgetItem("₹ 0.00")
                    dash.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                    self.table_dir.setItem(r, c, dash)

            # Actions Box — emoji icon buttons (Segoe UI Emoji ensures rendering on Windows)
            act_box = QWidget()
            act_lay = QHBoxLayout(act_box)
            act_lay.setContentsMargins(4, 2, 4, 2)
            act_lay.setSpacing(4)

            _emoji_font = QFont("Segoe UI Emoji", 14)

            def _icon_btn(symbol, tip, fg, bg, hover):
                b = QPushButton(symbol)
                b.setCursor(Qt.PointingHandCursor)
                b.setToolTip(tip)
                b.setFixedSize(30, 26)
                b.setFont(_emoji_font)
                b.setStyleSheet(
                    f"QPushButton {{ background: {bg}; color: {fg}; "
                    f"border: 1px solid {fg}40; border-radius: 5px; font-size: 14px; }} "
                    f"QPushButton:hover {{ background: {hover}; }}"
                )
                return b

            btn_view   = _icon_btn("\U0001F441", "View monthly history",              "#1D4ED8", "#EFF6FF", "#BFDBFE")
            btn_card   = _icon_btn("\U0001F4F8", "Share monthly salary card",         "#047857", "#ECFDF5", "#6EE7B7")
            btn_edit   = _icon_btn("\u270F",     "Edit worker profile",               "#374151", "#F9FAFB", "#D1D5DB")
            if w.is_active:
                btn_toggle = _icon_btn("\U0001F534", "Deactivate worker",             "#B91C1C", "#FEF2F2", "#FECACA")
            else:
                btn_toggle = _icon_btn("\U0001F7E2", "Activate worker",               "#047857", "#ECFDF5", "#6EE7B7")

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

        self._clear_table_widgets(self.table_att)
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

            last_st = worker_service.get_worker_last_settled_date(w.id)
            # Selector widget
            selector = self._make_attendance_selector(w.id, att_d, mult, w.daily_rate, last_st)
            self.table_att.setCellWidget(r, 4, selector)

            notes_item = QTableWidgetItem(rec.get("notes", ""))
            notes_item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
            notes_item.setFont(QFont("Segoe UI", 10))
            self.table_att.setItem(r, 5, notes_item)

        counts_text = f"Full (1.0): {cnt_full} | Half (0.5): {cnt_half} | 1.5 Day: {cnt_dedhi} | Double (2.0): {cnt_double} | Absent: {cnt_absent}"
        self.lbl_daily_att_counts.setText(counts_text)

    def _make_attendance_selector(self, worker_id: int, att_d: date, current_multiplier: float | None, daily_rate, last_settled_date: date | None = None) -> QWidget:
        box = QWidget()
        lay = QHBoxLayout(box)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.setSpacing(4)

        if last_settled_date and att_d <= last_settled_date:
            st_val = f"{current_multiplier:.1f} Day" if current_multiplier is not None else "0 Day"
            badge = QLabel(f"✓ Settled ({st_val} • Paid)")
            badge.setStyleSheet("""
                background: #ECFDF5; color: #059669; font-weight: 800;
                border: 1px solid #A7F3D0; border-radius: 5px; padding: 5px 12px; font-size: 11px;
            """)
            badge.setToolTip(
                f"Paid up to {last_settled_date.strftime('%d %b %Y')}.\n"
                "To edit this date, please rollback the settlement voucher in the 'Payment Done' tab."
            )
            lay.addWidget(badge)
            lay.addStretch(1)
            return box

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
        last_st = worker_service.get_worker_last_settled_date(worker_id)
        if last_st and att_d <= last_st:
            show_toast(self, f"Date {att_d.strftime('%d %b')} is settled in a payment voucher. Rollback in 'Payment Done' tab to edit.", "warning")
            return

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
        last_st = worker_service.get_worker_last_settled_date(worker_id)
        if last_st and att_date <= last_st:
            show_toast(self, f"Date {att_date.strftime('%d %b')} is settled in a payment voucher. Rollback in 'Payment Done' tab to edit.", "warning")
            return

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
            self._clear_table_widgets(self.table_hist)
            self.table_hist.setRowCount(0)
            self._update_hist_footer(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
            self.lbl_hist_settle_badge.setVisible(False)
            return

        summary = worker_service.get_worker_monthly_summary(worker_id, year, month)
        if not summary:
            self._clear_table_widgets(self.table_hist)
            self.table_hist.setRowCount(0)
            self._update_hist_footer(0, 0, 0, 0, 0, 0, 0, 0, 0, 0)
            self.lbl_hist_settle_badge.setVisible(False)
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
        self._clear_table_widgets(self.table_hist)
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

            is_row_settled = bool(a and a.get("is_settled")) or bool(summary.get("last_settled_date") and d <= summary.get("last_settled_date"))

            if a:  # Has attendance
                if is_row_settled:
                    btn_settled = QPushButton("✓ Settled")
                    btn_settled.setCursor(Qt.PointingHandCursor)
                    btn_settled.setToolTip("This date is settled and paid. Rollback in 'Payment Done' tab to edit.")
                    btn_settled.setStyleSheet(
                        "QPushButton { background: #ECFDF5; color: #059669; font-weight: 700; border: 1px solid #A7F3D0; "
                        "border-radius: 4px; padding: 3px 10px; font-size: 11px; } "
                        "QPushButton:hover { background: #D1FAE5; }"
                    )
                    btn_settled.clicked.connect(
                        lambda _=False, dt_s=date_str: QMessageBox.information(
                            self, "Date Settled",
                            f"Attendance for {dt_s} is locked in a confirmed payment voucher.\n\n"
                            "To edit or delete this date, please rollback the settlement voucher in the 'Payment Done' tab."
                        )
                    )
                    act_layout.addWidget(btn_settled)
                else:
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

        is_st = summary.get("is_settled", False)
        paid_val = summary.get("paid_amount", 0.0)
        p_date = summary.get("payment_date_str", "")
        p_mode = summary.get("payment_method", "Cash")
        rem_bal = summary.get("remaining_balance", 0.0)
        net_val = summary.get("net_payable", 0.0)

        if is_st or (rem_bal <= 0 and paid_val > 0):
            lbl_text = "✓ FULLY SETTLED"
            if p_date:
                lbl_text += f" • {p_date}"
            self.lbl_hist_settle_badge.setText(lbl_text)
            self.lbl_hist_settle_badge.setStyleSheet("""
                background: #ECFDF5; color: #059669; border: 1px solid #A7F3D0;
                font-size: 11px; font-weight: 800; padding: 4px 10px; border-radius: 6px;
            """)
            self.lbl_hist_settle_badge.setToolTip(f"Paid in full: {_money(paid_val)} on {p_date} via {p_mode}")
            self.lbl_hist_settle_badge.setVisible(True)
        elif paid_val > 0:
            self.lbl_hist_settle_badge.setText(f"⚡ PARTIAL (₹ {rem_bal:,.0f} DUE)")
            self.lbl_hist_settle_badge.setStyleSheet("""
                background: #FEF3C7; color: #D97706; border: 1px solid #FDE68A;
                font-size: 11px; font-weight: 800; padding: 4px 10px; border-radius: 6px;
            """)
            self.lbl_hist_settle_badge.setToolTip(f"Paid {_money(paid_val)}, Remaining Due: {_money(rem_bal)}")
            self.lbl_hist_settle_badge.setVisible(True)
        else:
            self.lbl_hist_settle_badge.setText("⏳ PAYMENT PENDING")
            self.lbl_hist_settle_badge.setStyleSheet("""
                background: #FEE2E2; color: #DC2626; border: 1px solid #FECACA;
                font-size: 11px; font-weight: 800; padding: 4px 10px; border-radius: 6px;
            """)
            self.lbl_hist_settle_badge.setToolTip(f"Pending payout: {_money(net_val)}")
            self.lbl_hist_settle_badge.setVisible(True)

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
            is_settled=is_st,
            paid_amount=paid_val,
            payment_date_str=p_date,
        )

    def _update_hist_footer(
        self, units, full, half, dedhi, double, absent, earning, travel=0.0, advance=0.0, net_payable=0.0,
        is_settled=False, paid_amount=0.0, payment_date_str=""
    ):
        self.lbl_hf_units.setText(f"Total Units: <b>{units:.1f} D</b>")
        self.lbl_hf_full.setText(f"Full: <b>{full}</b>")
        self.lbl_hf_half.setText(f"Half: <b>{half}</b>")
        self.lbl_hf_dedhi.setText(f"1.5 Day: <b>{dedhi}</b>")
        self.lbl_hf_double.setText(f"Double: <b>{double}</b>")
        self.lbl_hf_absent.setText(f"Absent: <b>{absent}</b>")
        self.lbl_hf_earning.setText(_money(earning))
        self.lbl_hf_travel.setText(f"+ {_money(travel)}")
        self.lbl_hf_advances.setText(f"- {_money(advance)}")
        if is_settled or (paid_amount >= net_payable and net_payable > 0):
            date_txt = f" ({payment_date_str})" if payment_date_str else ""
            self.lbl_hist_net_title.setText(f"✓ PAID{date_txt}:")
            self.lbl_hist_net_title.setStyleSheet("font-size: 11px; font-weight: 800; color: #A7F3D0; letter-spacing: 0.5px;")
            self.lbl_hf_net.setText(_money(paid_amount or net_payable))
            self.f_hf_net.setStyleSheet("background: #065F46; border-radius: 6px; padding: 5px 14px;")
        else:
            self.lbl_hist_net_title.setText("FINAL NET PAYABLE:")
            self.lbl_hist_net_title.setStyleSheet("font-size: 11px; font-weight: 700; color: #F59E0B; letter-spacing: 0.5px;")
            self.lbl_hf_net.setText(_money(net_payable))
            self.f_hf_net.setStyleSheet("background: #173560; border-radius: 6px; padding: 5px 14px;")

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
            self.lbl_sc_header_name.setText("Monthly Salary Statement")
            self.lbl_sc_header_month.setText("Select a worker and month from toolbar")
            self.lbl_sc_status.setText("NO SELECTION")
            self.lbl_sc_status.setStyleSheet("""
                background: #F1F5F9; color: #64748B; font-size: 10px; font-weight: 800;
                border-radius: 4px; padding: 4px 8px; border: 1px solid #CBD5E1;
            """)
            self.table_advances.setRowCount(0)
            self.table_travel.setRowCount(0)
            self.table_adjustments.setRowCount(0)
            self.table_settle_hist.setRowCount(0)
            self.lbl_subtab_adv_total.setText("Total Advances: ₹ 0.00")
            self.lbl_subtab_trv_total.setText("Total Travel: ₹ 0.00")
            self.lbl_subtab_adj_total.setText("Net Adjustments: ₹ 0.00")
            return

        summary = worker_service.get_worker_monthly_summary(worker_id, year, month)
        if not summary:
            return

        # ── 1. Card Header & Status ──────────────────────────────────────────
        self.lbl_sc_header_name.setText(f"{summary['name']}  •  {summary['work_type']}")
        self.lbl_sc_header_month.setText(
            f"{summary['month_name']} {summary['year']} Statement  |  Daily Rate: ₹ {summary['current_daily_rate']:,.0f}"
        )

        net_val = summary["net_payable"]
        paid_val = summary["paid_amount"]
        rem_val = summary["remaining_balance"]
        is_settled = summary["is_settled"]

        if is_settled or (paid_val >= net_val and net_val > 0):
            self.lbl_sc_status.setText("✓ FULLY SETTLED")
            self.lbl_sc_status.setStyleSheet("""
                background: #DCFCE7; color: #15803D; font-size: 10px; font-weight: 800;
                border-radius: 4px; padding: 4px 10px; border: 1px solid #86EFAC;
            """)
        elif paid_val > 0:
            self.lbl_sc_status.setText(f"⚡ PARTIAL (₹ {rem_val:,.0f} DUE)")
            self.lbl_sc_status.setStyleSheet("""
                background: #FEF3C7; color: #B45309; font-size: 10px; font-weight: 800;
                border-radius: 4px; padding: 4px 10px; border: 1px solid #FCD34D;
            """)
        else:
            self.lbl_sc_status.setText("⏳ PENDING PAYMENT")
            self.lbl_sc_status.setStyleSheet("""
                background: #FEE2E2; color: #B91C1C; font-size: 10px; font-weight: 800;
                border-radius: 4px; padding: 4px 10px; border: 1px solid #FCA5A5;
            """)

        # ── Clean up existing cell widgets to prevent orphans ───────────────
        for tbl in (self.table_advances, self.table_travel, self.table_adjustments, self.table_settle_hist):
            tbl.clearSpans()
            for r in range(tbl.rowCount()):
                for c in range(tbl.columnCount()):
                    cw = tbl.cellWidget(r, c)
                    if cw:
                        tbl.removeCellWidget(r, c)
                        cw.setParent(None)
                        cw.deleteLater()
            tbl.clearContents()
            tbl.setRowCount(0)

        # Helper: Create styled action cell
        def _make_action_widget(on_delete_fn, tip="Delete record"):
            act_w = QWidget()
            act_l = QHBoxLayout(act_w)
            act_l.setContentsMargins(0, 0, 0, 0)
            act_l.setAlignment(Qt.AlignCenter)
            b = QPushButton("🗑")
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip(tip)
            b.setFixedSize(28, 26)
            b.setFont(QFont("Segoe UI Emoji", 11))
            b.setStyleSheet("""
                QPushButton {
                    background: #FEF2F2; color: #DC2626; border: 1px solid #FECACA;
                    border-radius: 4px; font-size: 11px;
                }
                QPushButton:hover {
                    background: #DC2626; color: #FFFFFF; border: 1px solid #DC2626;
                }
            """)
            b.clicked.connect(on_delete_fn)
            act_l.addWidget(b)
            return act_w

        # ── 2. Advances Table ────────────────────────────────────────────────
        advs = summary.get("advances", [])
        self.lbl_subtab_adv_total.setText(f"Total Advances: {_money(summary['total_advance'])}  ({len(advs)} records)")
        if not advs:
            self.table_advances.setRowCount(1)
            self.table_advances.setRowHeight(0, 48)
            self.table_advances.setSpan(0, 0, 1, self.table_advances.columnCount())
            empty_it = QTableWidgetItem("ℹ  No advance payments recorded for this worker in this month.")
            empty_it.setTextAlignment(Qt.AlignCenter)
            empty_it.setForeground(QColor("#94A3B8"))
            empty_it.setFont(QFont("Segoe UI", 10))
            self.table_advances.setItem(0, 0, empty_it)
        else:
            self.table_advances.setRowCount(len(advs))
            for r, a in enumerate(advs):
                self.table_advances.setRowHeight(r, 38)
                # Date
                d_it = QTableWidgetItem(a["date_str"])
                d_it.setTextAlignment(Qt.AlignCenter)
                d_it.setFont(QFont("Segoe UI", 10))
                self.table_advances.setItem(r, 0, d_it)
                # Amount
                amt_it = QTableWidgetItem(f"- {_money(a['amount'])}")
                amt_it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                amt_it.setForeground(QColor("#DC2626"))
                amt_it.setFont(QFont("Segoe UI", 10, QFont.Bold))
                self.table_advances.setItem(r, 1, amt_it)
                # Method
                m_it = QTableWidgetItem(a.get("payment_method") or "Cash")
                m_it.setTextAlignment(Qt.AlignCenter)
                m_it.setFont(QFont("Segoe UI", 10))
                self.table_advances.setItem(r, 2, m_it)
                # Notes
                n_it = QTableWidgetItem(a.get("notes") or "—")
                n_it.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                n_it.setFont(QFont("Segoe UI", 10))
                n_it.setToolTip(a.get("notes") or "")
                self.table_advances.setItem(r, 3, n_it)
                # Action
                act_w = _make_action_widget(lambda _=False, a_id=a["id"]: self._delete_advance(a_id), "Delete this advance")
                self.table_advances.setCellWidget(r, 4, act_w)

        # ── 3. Travel Expenses Table ─────────────────────────────────────────
        exps = summary.get("travel_expenses", [])
        self.lbl_subtab_trv_total.setText(f"Total Travel: {_money(summary['total_travel'])}  ({len(exps)} records)")
        if not exps:
            self.table_travel.setRowCount(1)
            self.table_travel.setRowHeight(0, 48)
            self.table_travel.setSpan(0, 0, 1, self.table_travel.columnCount())
            empty_it = QTableWidgetItem("ℹ  No travel or conveyance expenses recorded for this month.")
            empty_it.setTextAlignment(Qt.AlignCenter)
            empty_it.setForeground(QColor("#94A3B8"))
            empty_it.setFont(QFont("Segoe UI", 10))
            self.table_travel.setItem(0, 0, empty_it)
        else:
            self.table_travel.setRowCount(len(exps))
            for r, e in enumerate(exps):
                self.table_travel.setRowHeight(r, 38)
                # Date
                d_it = QTableWidgetItem(e["date_str"])
                d_it.setTextAlignment(Qt.AlignCenter)
                d_it.setFont(QFont("Segoe UI", 10))
                self.table_travel.setItem(r, 0, d_it)
                # Amount
                amt_it = QTableWidgetItem(f"+ {_money(e['amount'])}")
                amt_it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                amt_it.setForeground(QColor("#059669"))
                amt_it.setFont(QFont("Segoe UI", 10, QFont.Bold))
                self.table_travel.setItem(r, 1, amt_it)
                # Category
                c_it = QTableWidgetItem(e.get("category") or "Travel")
                c_it.setTextAlignment(Qt.AlignCenter)
                c_it.setFont(QFont("Segoe UI", 10))
                self.table_travel.setItem(r, 2, c_it)
                # Notes
                n_it = QTableWidgetItem(e.get("notes") or "—")
                n_it.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                n_it.setFont(QFont("Segoe UI", 10))
                n_it.setToolTip(e.get("notes") or "")
                self.table_travel.setItem(r, 3, n_it)
                # Action
                act_w = _make_action_widget(lambda _=False, e_id=e["id"]: self._delete_travel(e_id), "Delete this travel expense")
                self.table_travel.setCellWidget(r, 4, act_w)

        # ── 4. Adjustments Table ─────────────────────────────────────────────
        adjs = summary.get("adjustments", [])
        net_adj = summary['total_additions'] - summary['total_deductions']
        sign_str = "+" if net_adj >= 0 else "-"
        self.lbl_subtab_adj_total.setText(
            f"Additions: +{_money(summary['total_additions'])} | Deductions: -{_money(summary['total_deductions'])}  (Net: {sign_str}{_money(abs(net_adj))})"
        )
        if not adjs:
            self.table_adjustments.setRowCount(1)
            self.table_adjustments.setRowHeight(0, 48)
            self.table_adjustments.setSpan(0, 0, 1, self.table_adjustments.columnCount())
            empty_it = QTableWidgetItem("ℹ  No special bonuses, penalties, or adjustments recorded for this month.")
            empty_it.setTextAlignment(Qt.AlignCenter)
            empty_it.setForeground(QColor("#94A3B8"))
            empty_it.setFont(QFont("Segoe UI", 10))
            self.table_adjustments.setItem(0, 0, empty_it)
        else:
            self.table_adjustments.setRowCount(len(adjs))
            for r, adj in enumerate(adjs):
                self.table_adjustments.setRowHeight(r, 38)
                # Date
                d_it = QTableWidgetItem(adj["date_str"])
                d_it.setTextAlignment(Qt.AlignCenter)
                d_it.setFont(QFont("Segoe UI", 10))
                self.table_adjustments.setItem(r, 0, d_it)
                # Type badge
                is_add = (adj["type"] == "ADDITION")
                t_it = QTableWidgetItem("+ Add" if is_add else "- Ded")
                t_it.setTextAlignment(Qt.AlignCenter)
                t_it.setFont(QFont("Segoe UI", 10, QFont.Bold))
                t_it.setForeground(QColor("#059669" if is_add else "#DC2626"))
                self.table_adjustments.setItem(r, 1, t_it)
                # Category
                c_it = QTableWidgetItem(adj.get("category") or "General")
                c_it.setTextAlignment(Qt.AlignCenter)
                c_it.setFont(QFont("Segoe UI", 10))
                self.table_adjustments.setItem(r, 2, c_it)
                # Amount
                amt_it = QTableWidgetItem((f"+ {_money(adj['amount'])}" if is_add else f"- {_money(adj['amount'])}"))
                amt_it.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                amt_it.setForeground(QColor("#059669" if is_add else "#DC2626"))
                amt_it.setFont(QFont("Segoe UI", 10, QFont.Bold))
                self.table_adjustments.setItem(r, 3, amt_it)
                # Notes
                n_it = QTableWidgetItem(adj.get("notes") or "—")
                n_it.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
                n_it.setFont(QFont("Segoe UI", 10))
                n_it.setToolTip(adj.get("notes") or "")
                self.table_adjustments.setItem(r, 4, n_it)
                # Action
                act_w = _make_action_widget(lambda _=False, adj_id=adj["id"]: self._delete_adjustment(adj_id), "Delete this adjustment")
                self.table_adjustments.setCellWidget(r, 5, act_w)

        # ── 4. Settlement History Table (All Recorded Months) ────────────────
        hist_list = worker_service.get_worker_settlement_history(worker_id)
        if not hist_list:
            self.table_settle_hist.setRowCount(1)
            self.table_settle_hist.setRowHeight(0, 48)
            self.table_settle_hist.setSpan(0, 0, 1, self.table_settle_hist.columnCount())
            empty_it = QTableWidgetItem("ℹ  No settlement payments recorded yet for this worker.")
            empty_it.setTextAlignment(Qt.AlignCenter)
            empty_it.setForeground(QColor("#94A3B8"))
            empty_it.setFont(QFont("Segoe UI", 10))
            self.table_settle_hist.setItem(0, 0, empty_it)
            self.lbl_subtab_shist_total.setText("Settlement History: 0 records")
        else:
            self.lbl_subtab_shist_total.setText(f"Settlement History: {len(hist_list)} recorded months")
            self.table_settle_hist.setRowCount(len(hist_list))
            for r, h in enumerate(hist_list):
                self.table_settle_hist.setRowHeight(r, 38)
                # Col 0: Month
                it0 = QTableWidgetItem(h["month_label"])
                it0.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                it0.setFont(QFont("Segoe UI", 10, QFont.Bold))
                self.table_settle_hist.setItem(r, 0, it0)

                # Col 1: Days Worked
                it1 = QTableWidgetItem(f"{h['total_units']:.1f} Days")
                it1.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
                self.table_settle_hist.setItem(r, 1, it1)

                # Col 2: Work Earning
                it2 = QTableWidgetItem(_money(h['total_work_earning']))
                it2.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                self.table_settle_hist.setItem(r, 2, it2)

                # Col 3: Advances (-)
                it3 = QTableWidgetItem(f"- {_money(h['total_advances'])}")
                it3.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                it3.setForeground(QColor("#DC2626"))
                self.table_settle_hist.setItem(r, 3, it3)

                # Col 4: Paid Amount
                it4 = QTableWidgetItem(_money(h['paid_amount']))
                it4.setTextAlignment(Qt.AlignVCenter | Qt.AlignRight)
                it4.setFont(QFont("Segoe UI", 10, QFont.Bold))
                it4.setForeground(QColor("#047857"))
                self.table_settle_hist.setItem(r, 4, it4)

                # Col 5: Payment Date
                it5 = QTableWidgetItem(h['payment_date_str'])
                it5.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
                self.table_settle_hist.setItem(r, 5, it5)

                # Col 6: Mode
                it6 = QTableWidgetItem(h['payment_method'])
                it6.setTextAlignment(Qt.AlignVCenter | Qt.AlignCenter)
                self.table_settle_hist.setItem(r, 6, it6)

                # Col 7: Status Badge
                st_w = QWidget()
                st_l = QHBoxLayout(st_w)
                st_l.setContentsMargins(0, 0, 0, 0)
                st_l.setAlignment(Qt.AlignCenter)
                st_lbl = QLabel("✓ PAID" if h['is_settled'] else "⏳ PARTIAL")
                st_lbl.setStyleSheet("""
                    background: #DCFCE7; color: #15803D; font-size: 10px; font-weight: 800;
                    border-radius: 4px; padding: 2px 6px; border: 1px solid #86EFAC;
                """)
                st_l.addWidget(st_lbl)
                self.table_settle_hist.setCellWidget(r, 7, st_w)

        # ── 5. Settlement Statement Card Values & Subtexts ───────────────────
        # Earnings
        self.lbl_sc_work.setText(_money(summary["total_work_earning"]))
        self.lbl_sc_work_sub.setText(f"{summary['total_units']:.1f} days worked × ₹ {summary['current_daily_rate']:,.0f}")

        self.lbl_sc_travel.setText(f"+ {_money(summary['total_travel'])}")
        self.lbl_sc_travel_sub.setText(f"{len(exps)} travel reimbursement items")

        self.lbl_sc_add.setText(f"+ {_money(summary['total_additions'])}")
        num_adds = len([x for x in adjs if x.get("type") == "ADDITION"])
        self.lbl_sc_add_sub.setText(f"{num_adds} bonus / allowance items")

        self.lbl_sc_gross.setText(_money(summary["gross_payable"]))

        # Deductions
        self.lbl_sc_adv.setText(f"- {_money(summary['total_advance'])}")
        self.lbl_sc_adv_sub.setText(f"{len(advs)} advance payments given")

        self.lbl_sc_ded.setText(f"- {_money(summary['total_deductions'])}")
        num_deds = len([x for x in adjs if x.get("type") == "DEDUCTION"])
        self.lbl_sc_ded_sub.setText(f"{num_deds} penalty / adjustment items")

        tot_ded = summary["total_advance"] + summary["total_deductions"]
        self.lbl_sc_tot_ded.setText(f"- {_money(tot_ded)}")

        # Net Hero
        self.lbl_sc_net.setText(_money(summary["net_payable"]))
        self.lbl_sc_net_sub.setText(
            f"Net payable after subtracting {_money(tot_ded)} total deductions"
        )

        # Payment & Due
        self.lbl_sc_paid.setText(_money(summary["paid_amount"]))
        self.lbl_sc_rem.setText(_money(summary["remaining_balance"]))
        if summary["remaining_balance"] <= 0:
            self.lbl_sc_rem.setStyleSheet("font-size: 13px; color: #059669; font-weight: 900; border: none; background: transparent;")
        else:
            self.lbl_sc_rem.setStyleSheet("font-size: 13px; color: #DC2626; font-weight: 900; border: none; background: transparent;")

        # Action button style
        if is_settled:
            self.btn_settle_action.setText("✓   Month Settled (Update Payment)")
            self.btn_settle_action.setStyleSheet("""
                QPushButton {
                    background: #059669; color: #FFFFFF; font-weight: 800;
                    border: none; border-radius: 8px; font-size: 13px;
                }
                QPushButton:hover { background: #047857; }
            """)
        else:
            self.btn_settle_action.setText("💰   Settle Month / Record Payment")
            self.btn_settle_action.setStyleSheet("""
                QPushButton {
                    background: #173560; color: #FFFFFF; font-weight: 800;
                    border: none; border-radius: 8px; font-size: 13px;
                }
                QPushButton:hover { background: #0F2342; }
            """)

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

        dlg = SettlementDialog(self, summary=summary, worker_id=worker_id)
        if dlg.exec() == QDialog.Accepted:
            data = dlg.get_data()
            st = worker_service.record_full_payment_done(
                worker_id=worker_id,
                end_date=data.get("end_date"),
                paid_amount=data["paid_amount"],
                payment_method=data["method"],
                notes=data["notes"],
                start_date=data.get("start_date"),
            )
            self._load_settlement_data()
            self._load_directory_data()
            self._load_monthly_history_data()
            self._load_daily_attendance_data()
            self._load_payment_done_data()
            self._load_kpis()
            show_toast(self, f"Payment confirmed: Voucher #{st.voucher_no} for {summary['name']}", "success")

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
