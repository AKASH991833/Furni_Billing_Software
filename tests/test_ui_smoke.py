"""Basic UI smoke tests.

Verifies that key UI components can be imported and instantiated
without crashing. These are lightweight tests that don't require
a running QApplication event loop.
"""
import pytest


class TestUIImports:
    """Verify all UI modules can be imported without errors."""

    def test_import_main_window(self):
        from app.ui.main_window import MainWindow
        assert MainWindow is not None

    def test_import_style(self):
        from app.ui.style import STYLESHEET
        assert isinstance(STYLESHEET, str)
        assert len(STYLESHEET) > 0

    def test_import_common_widgets(self):
        from app.ui.widgets.common import (
            GlassCard, AnimatedStatCard, GlassSection,
            Toast, show_toast, primary_button, card, empty_state,
        )
        assert GlassCard is not None
        assert AnimatedStatCard is not None
        assert GlassSection is not None

    def test_import_header(self):
        from app.ui.widgets.header import Header
        assert Header is not None

    def test_import_sidebar(self):
        from app.ui.widgets.sidebar import Sidebar, NAV_FORWARD
        assert Sidebar is not None
        assert isinstance(NAV_FORWARD, dict)

    def test_import_pages(self):
        from app.ui.pages.dashboard_page import DashboardPage
        from app.ui.pages.customers_page import CustomersPage, CustomerDialog
        from app.ui.pages.invoices_page import InvoicesPage
        from app.ui.pages.workers_page import WorkersPage
        from app.ui.pages.reports_page import ReportsPage
        from app.ui.pages.settings_page import SettingsPage
        from app.ui.pages.base_page import BasePage
        assert all([DashboardPage, CustomersPage, InvoicesPage, WorkersPage,
                    ReportsPage, SettingsPage, BasePage])

    def test_import_invoice_editor(self):
        from app.ui.pages.invoice_editor import InvoiceEditor
        assert InvoiceEditor is not None

    def test_dashboard_page_render_and_refresh(self):
        from PySide6.QtWidgets import QApplication
        from app.ui.pages.dashboard_page import DashboardPage
        _app = QApplication.instance() or QApplication([])
        page = DashboardPage()
        page.refresh()
        assert page.pending_collections_table is not None


class TestDarkModeRemoval:
    """Verify dark mode files are completely removed."""

    def test_no_dark_mode_module(self):
        import importlib
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("app.ui.dark_mode")

    def test_no_dark_mode_manager(self):
        import importlib
        with pytest.raises(ModuleNotFoundError):
            importlib.import_module("app.ui.dark_mode_manager")


class TestValidatorsImportable:
    """Verify validator module works."""

    def test_import_validators(self):
        from app.utils.validators import (
            validate_mobile, validate_email, validate_gstin,
            validate_pincode, validate_name,
            validate_customer, validate_business_profile,
        )
        assert all([validate_mobile, validate_email, validate_gstin,
                    validate_pincode, validate_name,
                    validate_customer, validate_business_profile])

    def test_valid_customer_passes(self):
        from app.utils.validators import validate_customer
        data = {"name": "Test Customer", "mobile": "9876543210"}
        errors = validate_customer(data)
        assert len(errors) == 0


class TestMigrationsImportable:
    """Verify migration framework works."""

    def test_import_migrations(self):
        from app.database.migrations import (
            run_migrations, get_current_version, get_applied_migrations,
        )
        assert all([run_migrations, get_current_version, get_applied_migrations])

    def test_migrations_registry(self):
        from app.database.migrations import _MIGRATIONS
        assert len(_MIGRATIONS) >= 5  # at least 5 migrations registered


class TestBackupService:
    """Verify backup service functions exist."""

    def test_import_backup_service(self):
        from app.services.backup_service import create_backup, list_backups, restore_backup
        assert all([create_backup, list_backups, restore_backup])


class TestCalculationEngine:
    """Verify calculation engine correctness."""

    def test_amount_in_words_singular(self):
        from app.utils.calculations import amount_in_words
        assert amount_in_words(1) == "One Rupee Only"

    def test_amount_in_words_plural(self):
        from app.utils.calculations import amount_in_words
        assert amount_in_words(2) == "Two Rupees Only"

    def test_amount_in_words_paisa(self):
        from app.utils.calculations import amount_in_words
        result = amount_in_words(0.01)
        assert "One Paisa" in result

    def test_discount_clamping(self):
        from app.utils.calculations import apply_gst
        result = apply_gst(1000, -500, 18)
        assert result["discount"] == 0  # negative clamped to 0

    def test_ls_amount(self):
        from app.utils.calculations import row_amount
        assert row_amount("LS", "LS", 5000) == 5000

    def test_numeric_amount(self):
        from app.utils.calculations import row_amount
        assert row_amount(10, 500) == 5000.0

    def test_decimal_amount(self):
        from app.utils.calculations import row_amount
        assert row_amount(1.5, 12000) == 18000.0
