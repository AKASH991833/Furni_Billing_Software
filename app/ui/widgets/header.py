"""Top header bar with settings dropdown menu."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QVBoxLayout,
)

from app.services.business_service import get_profile


class Header(QFrame):
    def __init__(self, on_logout=None, on_navigate=None, parent=None):
        super().__init__(parent)
        self.setObjectName("header")
        self.setFixedHeight(64)
        self._on_logout = on_logout
        self._on_navigate = on_navigate
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

        # Settings dropdown button
        if self._on_logout:
            lay.addSpacing(12)
            self._menu = self._build_menu()
            self._btn_settings = QPushButton("\u2699\uFE0F")
            self._btn_settings.setObjectName("iconButton")
            self._btn_settings.setFixedSize(38, 38)
            self._btn_settings.setCursor(Qt.PointingHandCursor)
            self._btn_settings.setStyleSheet(
                "QPushButton { font-size: 18px; padding: 4px; "
                "border: 1px solid #D1D5DB; border-radius: 8px; "
                "background: transparent; }"
                "QPushButton:hover { background: rgba(37,99,235,0.06); border-color: #2563EB; }"
            )
            self._btn_settings.clicked.connect(
                lambda: self._menu.exec(self._btn_settings.mapToGlobal(
                    self._btn_settings.rect().bottomLeft()
                ))
            )
            lay.addWidget(self._btn_settings)

    def _build_menu(self) -> QMenu:
        menu = QMenu(self)
        menu.setStyleSheet(
            "QMenu { background: rgba(255,255,255,0.97); border: 1px solid #E5E7EB; "
            "border-radius: 10px; padding: 6px; }"
            "QMenu::item { padding: 9px 20px 9px 14px; border-radius: 6px; "
            "font-size: 13px; color: #1F2937; }"
            "QMenu::item:selected { background: rgba(37,99,235,0.08); color: #2563EB; }"
            "QMenu::separator { height: 1px; background: #E5E7EB; margin: 4px 8px; }"
        )

        act_settings = menu.addAction("\u2699\uFE0F  Settings")
        act_settings.triggered.connect(lambda: self._navigate("settings"))

        act_pin = menu.addAction("\U0001F512  Change PIN")
        act_pin.triggered.connect(lambda: self._navigate("settings", "security"))

        menu.addSeparator()

        act_logout = menu.addAction("\U0001F6AA  Logout")
        act_logout.triggered.connect(self._do_logout)

        return menu

    def _navigate(self, page: str, tab: str | None = None):
        if self._on_navigate:
            self._on_navigate(page, tab)

    def _do_logout(self):
        if self._on_logout:
            self._on_logout()

    def set_title(self, title: str, sub: str = ""):
        self.title.setText(title)
        self.sub.setText(sub)

    def refresh_business_name(self):
        """Re-read the business name from DB (called after settings save)."""
        profile = get_profile()
        biz = profile.business_name if profile else "My Business"
        self.biz_label.setText(biz)
