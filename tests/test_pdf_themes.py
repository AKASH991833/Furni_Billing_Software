"""Tests for the PDF template / layout (single Colour theme).

Run with:  python -m pytest tests/test_pdf_themes.py -q
(from the project root)
"""
from app.pdf.html_template import Layout, build_css, build_layout
from app.pdf.theme import COLOUR

# ---------------------------------------------------------------------------
# Theme configuration tests
# ---------------------------------------------------------------------------

class TestThemeConfig:
    def test_colour_theme_exists(self):
        assert COLOUR.name == "colour"
        assert COLOUR.label == "Colour / Premium"

    def test_colour_has_navy(self):
        assert COLOUR.navy.startswith("#")


# ---------------------------------------------------------------------------
# CSS generation tests
# ---------------------------------------------------------------------------

class TestBuildCSS:
    def test_css_contains_navy(self):
        css = build_css()
        assert COLOUR.navy in css

    def test_css_length_nonzero(self):
        assert len(build_css()) > 100

    def test_css_has_page_rules(self):
        css = build_css()
        assert "@page" in css
        assert "A4" in css

    def test_css_has_all_theme_tokens(self):
        css = build_css()
        # Verify no unreplaced __PLACEHOLDER__ tokens remain
        assert "__NAVY__" not in css
        assert "__GOLD__" not in css
        assert "__INK__" not in css
        assert "__MUTED__" not in css
        assert "__BORDER__" not in css

    def test_css_contains_all_classes(self):
        css = build_css()
        for cls in [".page", ".head", ".thead", ".r", ".area-row",
                     ".area-total", ".totals", ".grand", ".words",
                     ".terms", ".sign-row", ".foot"]:
            assert cls in css, f"Missing CSS class: {cls}"


# ---------------------------------------------------------------------------
# Layout tests (no GUI required)
# ---------------------------------------------------------------------------

class TestBuildLayout:
    """Test the layout builder (single fixed colour theme)."""

    def _make_fake_objects(self):
        """Create minimal fake ORM objects for testing."""
        class FakeProfile:
            business_name = "Test Business"
            business_type = "Furniture"
            mobile = "1234567890"
            email = "test@test.com"
            gstin = "22AAAAA0000A1Z5"
            show_gst = True
            logo_path = None
            signature_path = None
            terms_conditions = "Terms apply."
            address = "123 Test St"
            city = "Mumbai"
            state = "MH"
            pincode = "400001"
            currency = "\u20B9"
            invoice_prefix = "INV"
            default_gst_rate = 18.0

        class FakeDate:
            def strftime(self, fmt):
                return "01-Jan-2026"

        class FakeInvoice:
            invoice_number = "INV-0001"
            invoice_date = FakeDate()
            due_date = FakeDate()
            site_address = "Site 1"
            status = "SAVED"
            subtotal = 1000.00
            discount = 0.00
            gst_enabled = True
            gst_rate = 18.0
            gst_amount = 180.00
            grand_total = 1180.00
            amount_in_words = "One Thousand One Hundred Eighty Rupees Only"

        class FakeCustomer:
            name = "Test Customer"
            mobile = "9876543210"
            address = "456 Customer Ave"
            city = "Pune"
            state = "MH"
            gstin = "27BBBBB0000B1Z5"

        class FakeProject:
            name = "Test Project"
            site_address = "789 Project Rd"

        class FakeItem:
            area = "HALL"
            description = "TV Unit"
            size = "6' x 4'"
            qty_raw = "2"
            rate_raw = "800"
            amount = 1600.00

        return (FakeProfile(), FakeInvoice(), FakeCustomer(),
                FakeProject(), [FakeItem()])

    def test_build_layout(self):
        profile, invoice, customer, project, items = self._make_fake_objects()
        layout = build_layout(profile, invoice, customer, project, items)
        assert isinstance(layout, Layout)
        assert "BLK-HEAD" in layout.header_html
        assert "BLK-GRID" in layout.billto_html
        assert len(layout.items) > 0
        assert len(layout.final) > 0

    def test_multiple_areas(self):
        """Test with multiple areas."""
        profile, invoice, customer, project, _ = self._make_fake_objects()
        items = []
        for area in ["HALL", "KITCHEN", "BEDROOM"]:
            class FakeItem:
                pass
            fi = FakeItem()
            fi.area = area
            fi.description = f"Item in {area}"
            fi.size = "5' x 3'"
            fi.qty_raw = "1"
            fi.rate_raw = "500"
            fi.amount = 500.00
            items.append(fi)
        layout = build_layout(profile, invoice, customer, project, items)
        # 3 area rows + 3 item rows + 3 area totals = 9 item blocks
        assert len(layout.items) == 9

    def test_decimal_quantity(self):
        """Decimal quantities must work."""
        profile, invoice, customer, project, _ = self._make_fake_objects()
        class FakeItem:
            area = "HALL"
            description = "Custom Item"
            size = "10' x 5'"
            qty_raw = "1.5"
            rate_raw = "200"
            amount = 300.00
        layout = build_layout(profile, invoice, customer, project, [FakeItem()])
        assert len(layout.items) == 3  # area row + item + area total

    def test_ls_manual_amount(self):
        """LS/manual amount rows must continue working."""
        profile, invoice, customer, project, _ = self._make_fake_objects()
        class FakeItem:
            area = "HALL"
            description = "LS Item"
            size = ""
            qty_raw = "LS"
            rate_raw = "LS"
            amount = 5000.00
        layout = build_layout(profile, invoice, customer, project, [FakeItem()])
        assert len(layout.items) == 3  # area row + item + area total

    def test_gst_off(self):
        """When GST is OFF, no GST row in final blocks."""
        profile, invoice, customer, project, _ = self._make_fake_objects()
        invoice.gst_enabled = False
        invoice.gst_amount = 0
        invoice.grand_total = 1000.00
        layout = build_layout(profile, invoice, customer, project, [])
        tot_html = next(h for bid, h in layout.final if bid == "BLK-TOT")
        assert "GST" not in tot_html or "GST (0%)" not in tot_html

    def test_gst_on(self):
        """When GST is ON with amount, GST row appears."""
        profile, invoice, customer, project, _ = self._make_fake_objects()
        invoice.gst_enabled = True
        invoice.gst_rate = 18.0
        invoice.gst_amount = 180.00
        invoice.grand_total = 1180.00
        layout = build_layout(profile, invoice, customer, project, [])
        tot_html = next(h for bid, h in layout.final if bid == "BLK-TOT")
        assert "GST (18%)" in tot_html


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
