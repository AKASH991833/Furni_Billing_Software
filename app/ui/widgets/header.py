"""Top header bar."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout

from app.services.business_service import get_profile


class Header(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("header")
        self.setFixedHeight(64)
        self._build()

    def _build(self):
        lay = QHBoxLayout(self)
        lay.setContentsMargins(24, 8, 24, 8)

        left = QVBoxLayout()
        left.setSpacing(0)
        self.title = QLabel("Home")
        self.title.setObjectName("pageTitle")
        self.sub = QLabel("")
        self.sub.setObjectName("pageSub")
        left.addWidget(self.title)
        left.addWidget(self.sub)
        lay.addLayout(left, 1)

        profile = get_profile()
        biz = profile.business_name if profile else "My Business"
        self.biz_label = QLabel(biz)
        self.biz_label.setObjectName("pageSub")
        self.biz_label.setStyleSheet("font-size:13px; font-weight:600; color:#2563EB;")
        lay.addWidget(self.biz_label)

    def set_title(self, title: str, sub: str = ""):
        self.title.setText(title)
        self.sub.setText(sub)

    def refresh_business_name(self):
        """Re-read the business name from DB (called after settings save)."""
        profile = get_profile()
        biz = profile.business_name if profile else "My Business"
        self.biz_label.setText(biz)
