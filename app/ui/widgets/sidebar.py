"""Sidebar navigation component."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

NAV_ITEMS = [
    ("dashboard", "Home", "\u2302"),
    ("customers", "Customers", "\U0001F465"),
    ("invoices", "Invoices", "\U0001F4C4"),
    ("reports", "Reports", "\U0001F4CA"),
    ("settings", "Settings", "\u2699\uFE0F"),
]

NAV_FORWARD = {"dashboard": "Home", "customers": "Customers",
              "invoices": "Invoices", "reports": "Reports", "settings": "Settings"}
NAV_BACKWARD = {"Home": "dashboard", "Customers": "customers",
                "Invoices": "invoices", "Reports": "reports", "Settings": "settings"}


class Sidebar(QFrame):
    def __init__(self, on_navigate=None, parent=None):
        super().__init__(parent)
        self.setObjectName("sidebar")
        self.setFixedWidth(220)
        self.on_navigate = on_navigate
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._build()

    def _build(self):
        lay = QVBoxLayout(self)
        lay.setContentsMargins(16, 24, 16, 16)
        lay.setSpacing(4)

        brand = QLabel("Furniture Bill")
        brand.setObjectName("brandTitle")
        lay.addWidget(brand)
        sub = QLabel("Interior & Accounts")
        sub.setObjectName("brandSub")
        lay.addWidget(sub)
        lay.addSpacing(24)

        self._buttons = {}
        for key, label, icon in NAV_ITEMS:
            btn = QPushButton(f"{icon}   {label}")
            btn.setObjectName("navButton")
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda _=False, k=key: self._navigate(k))
            self._group.addButton(btn)
            lay.addWidget(btn)
            self._buttons[key] = btn

        lay.addStretch(1)

        version = QLabel("v1.0.0")
        version.setObjectName("brandSub")
        version.setAlignment(Qt.AlignCenter)
        lay.addWidget(version)

    def _navigate(self, key):
        if self.on_navigate:
            self.on_navigate(key)

    def set_active(self, key: str):
        btn = self._buttons.get(key)
        if btn:
            btn.setChecked(True)
