"""Main application window with sidebar navigation and page stack."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.services.business_service import on_profile_changed
from app.ui.pages.customers_page import CustomersPage
from app.ui.pages.dashboard_page import DashboardPage
from app.ui.pages.invoices_page import InvoicesPage
from app.ui.pages.reports_page import ReportsPage
from app.ui.pages.settings_page import SettingsPage
from app.ui.pages.workers_page import WorkersPage
from app.ui.style import STYLESHEET
from app.ui.widgets.common import Toast
from app.ui.widgets.header import Header
from app.ui.widgets.sidebar import NAV_FORWARD, Sidebar


class MainWindow(QMainWindow):
    def __init__(self, on_logout=None):
        super().__init__()
        self.setWindowTitle("Furniture Bill - Billing & Accounts")
        self.resize(1280, 800)
        self.setMinimumSize(1024, 700)
        self._on_logout = on_logout

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
        self.header = Header(on_logout=self._on_logout, on_navigate=self._header_navigate)
        right.addWidget(self.header)

        self.stack = QStackedWidget()
        right.addWidget(self.stack, 1)
        root_layout.addLayout(right, 1)

        # Build pages
        self.pages = {
            "dashboard": DashboardPage(self),
            "customers": CustomersPage(self),
            "invoices": InvoicesPage(self),
            "workers": WorkersPage(self),
            "reports": ReportsPage(self),
            "settings": SettingsPage(self),
        }
        for page in self.pages.values():
            self.stack.addWidget(page)

        self.sidebar.set_active("dashboard")
        self.header.set_title("Home", "Welcome back")
        self._current = "dashboard"

        # Trigger the first show so dashboard data loads immediately on startup
        self.pages["dashboard"].on_show()

        # React to profile/settings changes in real time so nothing stays stale
        # until restart — mirrors web auto-reload after a settings save.
        on_profile_changed(self._on_profile_changed)



    def _on_profile_changed(self):
        """Called after every settings save: refresh header + current page."""
        try:
            self.header.refresh_business_name()
        except Exception:  # noqa: BLE001, S110
            pass
        try:
            page = self.pages.get(self._current)
            if page is not None:
                page.refresh()
        except Exception:  # noqa: BLE001, S110
            pass

    def _navigate(self, key: str):
        page = self.pages.get(key)
        if page is None:
            return
        self.stack.setCurrentWidget(page)
        page.on_show()
        self._current = key
        title = NAV_FORWARD.get(key, "Home")
        self.header.set_title(title, self._subtitle_for(key))

    def _header_navigate(self, page: str, tab: str | None = None):
        """Navigate from header dropdown — supports optional tab jump."""
        self._navigate(page)
        if tab and page == "settings":
            settings_page = self.pages.get("settings")
            if settings_page and hasattr(settings_page, "switch_to_tab"):
                settings_page.switch_to_tab(tab)

    def _subtitle_for(self, key: str) -> str:
        subs = {
            "dashboard": "Your business at a glance",
            "customers": "Manage your customers",
            "invoices": "Create and manage invoices",
            "workers": "Daily attendance, advances, travel & salary calculation",
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
