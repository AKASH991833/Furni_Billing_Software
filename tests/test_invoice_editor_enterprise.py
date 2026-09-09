"""Automated tests for Enterprise Invoice Editor upgrades:
- MeasurementHelper Sq. Ft. and Rft calculations
- FurniturePresetsDialog search & preset insertion
- Inline advance payment entry and database recording
- Bottom dock totals and balance due synchronization
"""
from datetime import date
import pytest
from PySide6.QtWidgets import QApplication

from app.models.models import Customer, Invoice, Payment
from app.services import invoice_service, payment_service
from app.ui.pages.editor_measurement import MeasurementHelper
from app.ui.pages.editor_presets_dialog import FURNITURE_PRESETS, FurniturePresetsDialog
from app.ui.pages.invoice_editor import InvoiceEditor

# Ensure single QApplication exists for GUI tests
_app = QApplication.instance() or QApplication([])


class TestMeasurementHelper:
    def test_sqft_calculation(self):
        """Verify Area (Sq. Ft.) calculation for standard wardrobe dimensions."""
        helper = MeasurementHelper(current="7' x 6'")
        # 7ft x 6ft = 42 sq ft
        sqft, sqm, rft = helper._calc_metrics()
        assert round(sqft, 2) == 42.0
        assert round(rft, 2) == 7.0
        assert round(sqm, 2) == round(42.0 * 0.092903, 2)

    def test_fractional_feet_inch_calculation(self):
        """Verify dimensions with inches (e.g. 6'6" x 4'0")."""
        helper = MeasurementHelper()
        helper.f1.setValue(6)
        helper.i1.setValue(6)  # 6.5 ft
        helper.f2.setValue(4)
        helper.i2.setValue(0)  # 4.0 ft
        sqft, _, rft = helper._calc_metrics()
        # 6.5 * 4.0 = 26.0 sq ft
        assert round(sqft, 2) == 26.0
        assert round(rft, 2) == 6.5

    def test_insert_modes(self):
        """Test insert size only vs insert with qty."""
        helper = MeasurementHelper(current="8' x 9'")
        helper._on_insert_size_only()
        assert helper.result() == "8' × 9'"
        assert helper.sqft() is None

        helper2 = MeasurementHelper(current="8' x 9'")
        helper2._on_insert_with_qty()
        assert helper2.result() == "8' × 9'"
        assert helper2.sqft() == 72.0


class TestFurniturePresets:
    def test_presets_catalog_populated(self):
        """Verify presets cover major furniture categories."""
        assert len(FURNITURE_PRESETS) >= 15
        categories = {p["category"] for p in FURNITURE_PRESETS}
        assert "LIVING ROOM" in categories
        assert "MASTER BEDROOM" in categories
        assert "KITCHEN" in categories

    def test_dialog_filtering(self):
        """Filter dialog items by search query."""
        selected = []
        dlg = FurniturePresetsDialog(
            target_area="BEDROOM",
            on_select=lambda a, d, s, q, r: selected.append((a, d, s, q, r))
        )
        dlg.f_search.setText("wardrobe")
        dlg._filter_items()
        assert len(dlg._filtered_list) >= 2
        for item in dlg._filtered_list:
            assert "wardrobe" in item["name"].lower()


class TestInvoiceEditorEnterprise:
    def test_add_preset_item_in_editor(self, db):
        """Adding a preset item creates row in editor with computed amount."""
        editor = InvoiceEditor()
        editor._add_preset_item(
            area="LIVING ROOM",
            description="3-Seater Fabric Sofa",
            size="7'0\" × 3'0\"",
            qty="1",
            rate="24000"
        )
        items = editor.current_items()
        assert len(items) == 1
        assert items[0]["description"] == "3-Seater Fabric Sofa"
        assert items[0]["area"] == "LIVING ROOM"
        assert items[0]["amount"] == 24000.0
        assert "₹ 24,000.00" in editor.lbl_dock_grand.text()

    def test_inline_advance_and_save(self, db):
        """Entering inline advance updates balance and records payment in DB on save."""
        cust = Customer(name="Advance Test Client", mobile="9822334455")
        db.add(cust)
        db.commit()

        editor = InvoiceEditor()
        editor._load_customers()

        # Select customer
        idx = editor.f_customer.findData(cust.id)
        assert idx >= 0
        editor.f_customer.setCurrentIndex(idx)

        # Add item
        editor._add_preset_item(
            area="MASTER BEDROOM",
            description="King Size Hydraulic Storage Bed",
            size="6'0\" × 6'6\"",
            qty="1",
            rate="50000"
        )

        # Total is 50,000 (no GST)
        editor.cb_gst.setChecked(False)
        editor._recalc()

        # Set 50% advance (₹25,000)
        editor._apply_adv_pct(50)
        assert editor.f_adv_amount.value() == 25000.0
        assert "25,000.00" in editor.l_paid.text()
        assert "25,000.00" in editor.l_balance.text()
        assert "25,000.00" in editor.lbl_dock_bal.text()

        # Save invoice
        editor._save("SAVED")
        inv_id = editor.get_invoice_id()
        assert inv_id is not None

        # Verify payment was recorded in DB
        payments = payment_service.list_payments(inv_id)
        assert len(payments) == 1
        assert float(payments[0].amount) == 25000.0
        assert payments[0].mode == "UPI"

        # Advance field is reset to 0 after being committed
        assert editor.f_adv_amount.value() == 0.0
