"""Test the PDF generation pipeline (no GUI / QWebEngine required).

Validates:
  - build_linear_html produces valid HTML with all layout blocks
  - _render produces a complete multi-page HTML document
  - The full pipeline (build_layout -> build_linear_html -> _render)
  - The _measure signal-disconnect fix is present in source code
"""
import os

import pytest

from app.pdf.html_template import build_css, build_layout
from app.pdf.paginate import (
    FOOT_H,
    GAP,
    MARGIN,
    PAGE_H,
    THEAD_H,
    _render,
    _usable_cap,
    build_linear_html,
)

# ---------------------------------------------------------------------------
# Fake ORM objects (same as test_pdf_themes.py but self-contained)
# ---------------------------------------------------------------------------

class _FakeProfile:
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


class _FakeDate:
    def strftime(self, fmt):
        return "01-Jan-2026"


class _FakeInvoice:
    invoice_number = "INV-0001"
    invoice_date = _FakeDate()
    due_date = _FakeDate()
    site_address = "Site 1"
    status = "SAVED"
    subtotal = 1000.00
    discount = 0.00
    gst_enabled = True
    gst_rate = 18.0
    gst_amount = 180.00
    grand_total = 1180.00
    amount_in_words = "One Thousand One Hundred Eighty Rupees Only"


class _FakeCustomer:
    name = "Test Customer"
    mobile = "9876543210"
    address = "456 Customer Ave"
    city = "Pune"
    state = "MH"
    gstin = "27BBBBB0000B1Z5"


class _FakeProject:
    name = "Test Project"
    site_address = "789 Project Rd"


def _make_item(area="HALL", desc="TV Unit", qty="2", rate="800", amount=1600.0):
    class It:
        pass
    it = It()
    it.area = area
    it.description = desc
    it.size = "6' x 4'"
    it.qty_raw = qty
    it.rate_raw = rate
    it.amount = amount
    return it


def _build_layout(items=None):
    if items is None:
        items = [_make_item()]
    return build_layout(
        _FakeProfile(), _FakeInvoice(), _FakeCustomer(),
        _FakeProject(), items,
    )


# ---------------------------------------------------------------------------
# Tests: build_linear_html
# ---------------------------------------------------------------------------

class TestBuildLinearHTML:
    """build_linear_html wraps all blocks in a single #lin container."""

    def test_contains_lin_div(self):
        layout = _build_layout()
        css = build_css()
        html = build_linear_html(layout, css)
        assert "id='lin'" in html

    def test_contains_header_block(self):
        layout = _build_layout()
        css = build_css()
        html = build_linear_html(layout, css)
        assert "BLK-HEAD" in html

    def test_contains_billto_block(self):
        layout = _build_layout()
        css = build_css()
        html = build_linear_html(layout, css)
        assert "BLK-GRID" in html

    def test_contains_item_blocks(self):
        layout = _build_layout()
        css = build_css()
        html = build_linear_html(layout, css)
        assert "IR-1" in html  # first item row
        assert "AR-" in html   # area row
        assert "AT-" in html   # area total row

    def test_contains_final_blocks(self):
        layout = _build_layout()
        css = build_css()
        html = build_linear_html(layout, css)
        assert "BLK-TOT" in html    # totals
        assert "BLK-WORDS" in html  # amount in words
        assert "BLK-SIG" in html    # signature

    def test_contains_css(self):
        layout = _build_layout()
        css = build_css()
        html = build_linear_html(layout, css)
        assert css in html

    def test_linear_is_single_page(self):
        """Linear HTML should NOT have page-break classes (it's one continuous doc)."""
        layout = _build_layout()
        css = build_css()
        html = build_linear_html(layout, css)
        assert "page-break-before" not in html
        assert "page-break-after" not in html

    def test_thead_is_measureable_in_linear(self):
        """The table header and footer are rendered in-flow in the linear doc
        so their REAL heights are measured for dynamic page capacities."""
        layout = _build_layout()
        css = build_css()
        html = build_linear_html(layout, css)
        assert 'id="BLK-THEAD"' in html
        assert 'id="BLK-FOOT"' in html


# ---------------------------------------------------------------------------
# Tests: _render (with fake heights)
# ---------------------------------------------------------------------------

class TestRender:
    """_render packs blocks into pages using provided heights."""

    def _fake_heights(self, layout):
        """Return a dict of reasonable fake heights for all blocks."""
        h = {"BLK-HEAD": 34.0, "BLK-GRID": 24.0, "BLK-THEAD": 9.5}
        for bid, _ in layout.items:
            h[bid] = 6.5
        for bid, _ in layout.final:
            h[bid] = 10.0
        return h

    def test_single_page_output(self):
        layout = _build_layout()
        css = build_css()
        heights = self._fake_heights(layout)
        html = _render(_FakeProfile(), layout, heights, css)
        assert html.startswith("<!DOCTYPE html>")
        assert html.endswith("</body></html>")

    def test_has_page_divs(self):
        layout = _build_layout()
        css = build_css()
        heights = self._fake_heights(layout)
        html = _render(_FakeProfile(), layout, heights, css)
        assert html.count('class="page"') >= 1

    def test_first_page_has_header_and_billto(self):
        layout = _build_layout()
        css = build_css()
        heights = self._fake_heights(layout)
        html = _render(_FakeProfile(), layout, heights, css)
        assert "BLK-HEAD" in html
        assert "BLK-GRID" in html

    def test_has_totals(self):
        layout = _build_layout()
        css = build_css()
        heights = self._fake_heights(layout)
        html = _render(_FakeProfile(), layout, heights, css)
        assert "BLK-TOT" in html
        assert "GRAND TOTAL" in html

    def test_has_amount_in_words(self):
        layout = _build_layout()
        css = build_css()
        heights = self._fake_heights(layout)
        html = _render(_FakeProfile(), layout, heights, css)
        assert "BLK-WORDS" in html
        assert "One Thousand" in html

    def test_has_signature(self):
        layout = _build_layout()
        css = build_css()
        heights = self._fake_heights(layout)
        html = _render(_FakeProfile(), layout, heights, css)
        assert "BLK-SIG" in html
        assert "AUTHORIZED SIGNATURE" in html

    def test_has_footer(self):
        layout = _build_layout()
        css = build_css()
        heights = self._fake_heights(layout)
        html = _render(_FakeProfile(), layout, heights, css)
        assert "Page 1 of" in html
        assert "Thank you for your business." in html

    def test_page_break_before_on_page_2(self):
        """Second page should have page-break-before: always."""
        layout = _build_layout()
        css = build_css()
        heights = self._fake_heights(layout)
        # Force many items to trigger a second page
        items = [_make_item(area=f"AREA{i}") for i in range(50)]
        layout = build_layout(
            _FakeProfile(), _FakeInvoice(), _FakeCustomer(),
            _FakeProject(), items,
        )
        heights = self._fake_heights(layout)
        html = _render(_FakeProfile(), layout, heights, css)
        pages = html.count('class="page"')
        if pages > 1:
            assert "page-break-before: always" in html

    def test_first_page_has_after_break(self):
        layout = _build_layout()
        css = build_css()
        heights = self._fake_heights(layout)
        html = _render(_FakeProfile(), layout, heights, css)
        assert "page-break-after: always" in html

    def test_empty_items_renders(self):
        """An invoice with no items should still produce valid HTML."""
        layout = _build_layout(items=[])
        css = build_css()
        heights = {"BLK-HEAD": 34.0, "BLK-GRID": 24.0}
        for bid, _ in layout.final:
            heights[bid] = 10.0
        html = _render(_FakeProfile(), layout, heights, css)
        assert "BLK-TOT" in html
        assert "GRAND TOTAL" in html
        assert 'class="page"' in html


# ---------------------------------------------------------------------------
# Tests: _usable_cap
# ---------------------------------------------------------------------------

class TestUsableCap:
    def test_first_page_smaller_than_later(self):
        first, later = _usable_cap(34.0, 24.0)
        assert first < later

    def test_later_page_is_usable_minus_thead(self):
        USABLE = PAGE_H - MARGIN - MARGIN - FOOT_H - 3.0 - 6.0
        _, later = _usable_cap(34.0, 24.0)
        expected = USABLE - THEAD_H - GAP
        assert abs(later - expected) < 0.1


# ---------------------------------------------------------------------------
# Tests: signal disconnect fix in _measure source
# ---------------------------------------------------------------------------

class TestSignalFix:
    """Verify the _measure function disconnects the loadFinished handler."""

    def test_disconnect_in_source(self):
        """The _measure source must disconnect the loadFinished handler after
        the loop exits, using the signal/slot form (QMetaObject.Connection has
        no .disconnect() method in PySide6)."""
        src_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "app", "pdf", "paginate.py",
        )
        with open(src_path) as f:
            source = f.read()
        # Find the _measure function and check it has a working disconnect
        measure_fn = source[source.index("def _measure("):source.index("\ndef _", source.index("def _measure(") + 1)]
        assert "conn = view.page().loadFinished.connect" in measure_fn, (
            "_measure must store the connection object for later disconnection"
        )
        # Must NOT call conn.disconnect() — that crashes in PySide6. It must
        # disconnect via the signal/slot form instead.
        assert "conn.disconnect()" not in measure_fn, (
            "conn.disconnect() crashes in PySide6 (no such attribute). "
            "Use view.page().loadFinished.disconnect(_on_load) instead."
        )
        assert "loadFinished.disconnect(_on_load)" in measure_fn, (
            "_measure must disconnect the loadFinished handler via the signal "
            "after measurement"
        )

    def test_set_html_after_connect_in_measure(self):
        """In _measure, setHtml must be called BEFORE connect (signal safety)."""
        src_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "app", "pdf", "paginate.py",
        )
        with open(src_path) as f:
            source = f.read()
        measure_fn = source[source.index("def _measure("):source.index("\ndef _", source.index("def _measure(") + 1)]
        set_html_pos = measure_fn.index("view.setHtml(")
        connect_pos = measure_fn.index("view.page().loadFinished.connect")
        # setHtml must come before connect to ensure the signal fires
        assert set_html_pos < connect_pos, (
            "setHtml() must be called before loadFinished.connect() in _measure"
        )


# ---------------------------------------------------------------------------
# Tests: CSS completeness in final render
# ---------------------------------------------------------------------------

class TestRenderCSS:
    """Verify the rendered HTML includes complete CSS."""

    def test_css_all_replaced_tokens(self):
        css = build_css()
        assert "__NAVY__" not in css
        assert "__GOLD__" not in css
        assert "__INK__" not in css
        assert "__MUTED__" not in css

    def test_rendered_html_has_style_tag(self):
        layout = _build_layout()
        css = build_css()
        heights = {"BLK-HEAD": 34.0, "BLK-GRID": 24.0}
        for bid, _ in layout.items:
            heights[bid] = 6.5
        for bid, _ in layout.final:
            heights[bid] = 10.0
        html = _render(_FakeProfile(), layout, heights, css)
        assert "<style>" in html
        assert "</style>" in html
        assert ".page" in html
        assert ".head" in html


# ---------------------------------------------------------------------------
# Tests: multi-area layout rendering
# ---------------------------------------------------------------------------

class TestMultiAreaRender:
    """Verify rendering with multiple areas works correctly."""

    def test_three_areas_all_present(self):
        items = [
            _make_item(area="HALL", desc="TV Unit"),
            _make_item(area="KITCHEN", desc="Cabinet"),
            _make_item(area="BEDROOM", desc="Wardrobe"),
        ]
        layout = build_layout(
            _FakeProfile(), _FakeInvoice(), _FakeCustomer(),
            _FakeProject(), items,
        )
        css = build_css()
        heights = {"BLK-HEAD": 34.0, "BLK-GRID": 24.0}
        for bid, _ in layout.items:
            heights[bid] = 6.5
        for bid, _ in layout.final:
            heights[bid] = 10.0
        html = _render(_FakeProfile(), layout, heights, css)

        # All three area names should appear
        assert "HALL" in html
        assert "KITCHEN" in html
        assert "BEDROOM" in html

        # All three area totals should appear
        assert "HALL TOTAL" in html
        assert "KITCHEN TOTAL" in html
        assert "BEDROOM TOTAL" in html

    def test_item_amounts_correct(self):
        items = [_make_item(qty="3", rate="100", amount=300.0)]
        layout = build_layout(
            _FakeProfile(), _FakeInvoice(), _FakeCustomer(),
            _FakeProject(), items,
        )
        css = build_css()
        heights = {"BLK-HEAD": 34.0, "BLK-GRID": 24.0}
        for bid, _ in layout.items:
            heights[bid] = 6.5
        for bid, _ in layout.final:
            heights[bid] = 10.0
        html = _render(_FakeProfile(), layout, heights, css)
        assert "300.00" in html  # item amount
        assert "1,000.00" in html  # subtotal
        assert "1,180.00" in html  # grand total with GST


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
