"""Main application window with sidebar navigation and page stack."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.services.business_service import get_profile
from app.ui.widgets.common import Toast
from app.ui.widgets.header import Header
from app.ui.widgets.sidebar import NAV_FORWARD, Sidebar
from app.ui.pages.customers_page import CustomersPage
from app.ui.pages.dashboard_page import DashboardPage
from app.ui.pages.invoices_page import InvoicesPage
from app.ui.pages.reports_page import ReportsPage
from app.ui.pages.settings_page import SettingsPage
from app.ui.style import STYLESHEET


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Furniture Bill - Billing & Accounts")
        self.resize(1280, 800)
        self.setMinimumSize(1024, 700)
        self.setStyleSheet(STYLESHEET)

        root = QWidget()
        root.setObjectName("rootWidget")
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        self.sidebar = Sidebar(on_navigate=self._navigate)
        root_layout.addWidget(self.sidebar)

        right = QVBoxLayout()
        right.setContentsMargins(0, 0, 0, 0)
        right.setSpacing(0)
        self.header = Header()
        right.addWidget(self.header)

        self.stack = QStackedWidget()
        right.addWidget(self.stack, 1)
        root_layout.addLayout(right, 1)

        # Build pages
        self.pages = {
            "dashboard": DashboardPage(self),
            "customers": CustomersPage(self),
            "invoices": InvoicesPage(self),
            "reports": ReportsPage(self),
            "settings": SettingsPage(self),
        }
        for page in self.pages.values():
            self.stack.addWidget(page)

        self.sidebar.set_active("dashboard")
        self.header.set_title("Home", "Welcome back")
        self._current = "dashboard"

    def _navigate(self, key: str):
        page = self.pages.get(key)
        if page is None:
            return
        self.stack.setCurrentWidget(page)
        page.on_show()
        self._current = key
        title = NAV_FORWARD.get(key, "Home")
        self.header.set_title(title, self._subtitle_for(key))

    def _subtitle_for(self, key: str) -> str:
        subs = {
            "dashboard": "Your business at a glance",
            "customers": "Manage your customers",
            "invoices": "Create and manage invoices",
            "reports": "Income and outstanding reports",
            "settings": "Business profile and preferences",
        }
        return subs.get(key, "")

    def show_toast(self, message: str, kind: str = "info"):
        Toast(self, message, kind)

    def show_page(self, key: str):
        if key in self.pages:
            self._navigate(key)

    def refresh_current(self):
        page = self.pages.get(self._current)
        if page is not None:
            page.refresh()
