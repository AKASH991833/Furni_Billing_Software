"""Measurement & Square-Footage (Sq. Ft.) Calculator Dialog.

Calculates length and width in feet & inches, computes total Area in Sq. Ft.
and Running Feet (Rft), and provides 1-click insertion into the Size and
Quantity (QTY) columns of the invoice editor.
"""
from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)


class MeasurementHelper:
    """Feet/inches helper that computes Area (Sq. Ft.) & Rft for furniture billing."""

    def __init__(self, parent=None, current=""):
        self._dlg = QDialog(parent)
        self._dlg.setWindowTitle("Furniture Measurement & Area Calculator")
        self._dlg.setMinimumWidth(440)
        self._size = ""
        self._sqft: float | None = None

        v = QVBoxLayout(self._dlg)
        v.setSpacing(12)
        v.setContentsMargins(18, 16, 18, 16)

        title = QLabel("📏 Furniture Measurement & Area (Sq. Ft.)")
        title.setStyleSheet("font-size: 15px; font-weight: 800; color: #173560;")
        v.addWidget(title)

        hint = QLabel("Enter dimensions in feet & inches (e.g. Wardrobe 7'0\" × 6'0\" = 42.0 Sq. Ft.)")
        hint.setStyleSheet("color: #64748B; font-size: 11px;")
        v.addWidget(hint)

        def spin(maxv=500):
            s = QSpinBox()
            s.setRange(0, maxv)
            s.setValue(0)
            s.setAlignment(Qt.AlignCenter)
            s.setMinimumHeight(28)
            s.setStyleSheet("font-size: 13px; font-weight: 600;")
            s.valueChanged.connect(self._recalc_area)
            return s

        self.f1 = spin(); self.i1 = spin(11)
        self.f2 = spin(); self.i2 = spin(11)

        form = QFormLayout()
        form.setVerticalSpacing(10)

        def ft_in_row(f, i, label):
            row = QHBoxLayout()
            row.setSpacing(6)
            row.addWidget(f, 1)
            lbl_ft = QLabel("ft")
            lbl_ft.setStyleSheet("font-weight: 700; color: #475569;")
            row.addWidget(lbl_ft)
            row.addWidget(i, 1)
            lbl_in = QLabel("in")
            lbl_in.setStyleSheet("font-weight: 700; color: #475569;")
            row.addWidget(lbl_in)
            return label, row

        form.addRow(*ft_in_row(self.f1, self.i1, "Length / Height:"))
        form.addRow(*ft_in_row(self.f2, self.i2, "Width / Depth:"))
        v.addLayout(form)

        # Live Calculation Card
        self.card = QFrame()
        self.card.setStyleSheet(
            "QFrame { background: #F0FDF4; border: 1.5px solid #86EFAC; border-radius: 8px; padding: 10px; }"
        )
        card_lay = QVBoxLayout(self.card)
        card_lay.setSpacing(4)
        card_lay.setContentsMargins(10, 8, 10, 8)

        self.lbl_area_val = QLabel("Total Area: 0.00 Sq. Ft.")
        self.lbl_area_val.setStyleSheet("font-size: 16px; font-weight: 800; color: #166534;")
        self.lbl_sub_val = QLabel("Running Length: 0.00 Rft  |  0.00 Sq. Meters")
        self.lbl_sub_val.setStyleSheet("font-size: 11px; color: #15803D; font-weight: 600;")

        card_lay.addWidget(self.lbl_area_val)
        card_lay.addWidget(self.lbl_sub_val)
        v.addWidget(self.card)

        self._parse_current(current)
        self._recalc_area()

        # Action Buttons
        btns = QHBoxLayout()
        btns.setSpacing(8)

        cancel = QPushButton("Cancel")
        cancel.setCursor(Qt.PointingHandCursor)
        cancel.clicked.connect(self._dlg.reject)

        btn_size_only = QPushButton("Insert Size Only")
        btn_size_only.setCursor(Qt.PointingHandCursor)
        btn_size_only.setStyleSheet("padding: 6px 12px; font-weight: 600;")
        btn_size_only.clicked.connect(self._on_insert_size_only)

        btn_set_qty = QPushButton("✓ Insert Size & Set Qty (Sq. Ft.)")
        btn_set_qty.setCursor(Qt.PointingHandCursor)
        btn_set_qty.setStyleSheet(
            "QPushButton { background: #059669; color: white; font-weight: 800; padding: 6px 14px; border-radius: 6px; }"
            "QPushButton:hover { background: #047857; }"
        )
        btn_set_qty.clicked.connect(self._on_insert_with_qty)

        btns.addWidget(cancel)
        btns.addStretch(1)
        btns.addWidget(btn_size_only)
        btns.addWidget(btn_set_qty)
        v.addLayout(btns)

    def _calc_metrics(self) -> tuple[float, float, float]:
        l_feet = float(self.f1.value()) + (float(self.i1.value()) / 12.0)
        w_feet = float(self.f2.value()) + (float(self.i2.value()) / 12.0)
        sqft = l_feet * w_feet
        sqm = sqft * 0.092903
        return sqft, sqm, l_feet

    def _recalc_area(self):
        sqft, sqm, rft = self._calc_metrics()
        self.lbl_area_val.setText(f"Total Area: {sqft:.2f} Sq. Ft.")
        self.lbl_sub_val.setText(f"Running Length: {rft:.2f} Rft  |  {sqm:.2f} Sq. Meters")

    def _parse_current(self, current):
        if not current or not isinstance(current, str):
            return
        parts = [p.strip() for p in current.replace("×", "x").split("x") if p.strip()]
        if len(parts) != 2:
            return

        def to_vals(s):
            ft = re.search(r"(\d+)'", s)
            inch = re.search(r'(\d+)"', s)
            return (int(ft.group(1)) if ft else 0, int(inch.group(1)) if inch else 0)

        f1, i1 = to_vals(parts[0]); f2, i2 = to_vals(parts[1])
        self.f1.setValue(f1); self.i1.setValue(i1)
        self.f2.setValue(f2); self.i2.setValue(i2)

    def _build_size_text(self) -> str:
        def part(ft, inch):
            if inch == 0:
                return f"{ft}'"
            return f"{ft}'{inch}\""
        return f"{part(self.f1.value(), self.i1.value())} × {part(self.f2.value(), self.i2.value())}"

    def _on_insert_size_only(self):
        self._size = self._build_size_text()
        self._sqft = None
        self._dlg.accept()

    def _on_insert_with_qty(self):
        self._size = self._build_size_text()
        sqft, _, _ = self._calc_metrics()
        self._sqft = round(sqft, 2) if sqft > 0 else None
        self._dlg.accept()

    def result(self) -> str:
        return getattr(self, "_size", "")

    def sqft(self) -> float | None:
        """Returns computed square feet if user clicked 'Set Qty', else None."""
        return getattr(self, "_sqft", None)

    def exec(self) -> bool:
        """Show the dialog and return True if user accepted."""
        return bool(self._dlg.exec())
