"""Measurement Helper dialog.

Standalone feet/inches helper that builds a Size text like 6'6" x 6'.
Extracted from invoice_editor.py for code organization.
"""
from __future__ import annotations

import re

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)


class MeasurementHelper:
    """Feet/inches helper that builds a Size text like 6'6\" x 6'."""

    def __init__(self, parent=None, current=""):
        from PySide6.QtWidgets import QDialog
        self._dlg = QDialog(parent)
        self._dlg.setWindowTitle("Measurement Helper")
        self._dlg.setMinimumWidth(400)
        v = QVBoxLayout(self._dlg)
        v.setSpacing(14)

        title = QLabel("Enter length and width in feet / inches")
        title.setObjectName("dialogTitle")
        v.addWidget(title)

        hint = QLabel("Example: 9' 6\" length   x   6' width   →   9'6\" × 6'")
        hint.setStyleSheet("color:#6B7280;")
        v.addWidget(hint)

        def spin(maxv=300):
            s = QSpinBox()
            s.setRange(0, maxv)
            s.setValue(0)
            s.setAlignment(Qt.AlignCenter)
            return s

        self.f1 = spin(); self.i1 = spin(12)
        self.f2 = spin(); self.i2 = spin(12)

        form = QFormLayout()
        form.setVerticalSpacing(12)

        def ft_in_row(f, i, label):
            row = QHBoxLayout()
            row.setSpacing(8)
            row.addWidget(f); row.addWidget(QLabel("ft"))
            row.addWidget(i); row.addWidget(QLabel("in"))
            row.addStretch(1)
            return label, row

        form.addRow(*ft_in_row(self.f1, self.i1, "Length:"))
        form.addRow(*ft_in_row(self.f2, self.i2, "Width:"))
        v.addLayout(form)

        self._parse_current(current)

        btns = QHBoxLayout()
        btns.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self._dlg.reject)
        ok = QPushButton("Insert")
        ok.setObjectName("primaryButton")
        ok.clicked.connect(self._ok)
        btns.addWidget(cancel); btns.addWidget(ok)
        v.addLayout(btns)

    def _parse_current(self, current):
        if not current or not isinstance(current, str):
            return
        parts = [p.strip() for p in current.split("x") if p.strip()]
        if len(parts) != 2:
            return

        def to_vals(s):
            ft = re.search(r"(\d+)'", s)
            inch = re.search(r'(\d+)"', s)
            return (int(ft.group(1)) if ft else 0, int(inch.group(1)) if inch else 0)

        f1, i1 = to_vals(parts[0]); f2, i2 = to_vals(parts[1])
        self.f1.setValue(f1); self.i1.setValue(i1)
        self.f2.setValue(f2); self.i2.setValue(i2)

    def _ok(self):
        def part(ft, inch):
            if inch == 0:
                return f"{ft}'"
            return f"{ft}'{inch}\""
        self._size = f"{part(self.f1.value(), self.i1.value())} × {part(self.f2.value(), self.i2.value())}"
        self._dlg.accept()

    def result(self) -> str:
        return getattr(self, "_size", "")

    def exec(self) -> bool:
        """Show the dialog and return True if user clicked Insert."""
        return self._dlg.exec()
