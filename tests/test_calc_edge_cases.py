"""Edge-case tests for calculations — discount clamping, negative amounts,
NaN/Infinity handling, and boundary conditions.

Run with:  python -m pytest tests/test_calc_edge_cases.py -q
"""
import math

import pytest

from app.utils.calculations import (
    apply_gst,
    amount_in_words,
    compute_area_totals,
    compute_full_invoice,
    compute_rows,
    format_qty,
    format_rate,
    is_number,
    row_amount,
    row_is_ls,
    to_number,
)


def d(area="HALL", qty="1", rate="100", amount=None):
    """Build a dict row the way the editor does."""
    return {"area": area, "description": "x", "size": "1",
            "qty_raw": qty, "rate_raw": rate, "amount": amount}


# ===========================================================================
# is_number — edge cases
# ===========================================================================

class TestIsNumber:
    def test_none(self):
        assert is_number(None) is False

    def test_bool_false(self):
        assert is_number(False) is False

    def test_bool_true(self):
        assert is_number(True) is False

    def test_nan(self):
        assert is_number(float("nan")) is False

    def test_positive_infinity(self):
        assert is_number(float("inf")) is False

    def test_negative_infinity(self):
        assert is_number(float("-inf")) is False

    def test_string_inf(self):
        assert is_number("inf") is False

    def test_string_neg_inf(self):
        assert is_number("-inf") is False

    def test_empty_string(self):
        assert is_number("") is False

    def test_random_string(self):
        assert is_number("abc") is False

    def test_zero(self):
        assert is_number(0) is True

    def test_negative_zero(self):
        assert is_number(-0.0) is True

    def test_negative_number(self):
        assert is_number(-42) is True

    def test_large_number(self):
        assert is_number(10**18) is True

    def test_small_float(self):
        assert is_number(0.000001) is True

    def test_string_number(self):
        assert is_number("123") is True

    def test_string_float(self):
        assert is_number("3.14") is True

    def test_string_negative(self):
        assert is_number("-5") is True

    def test_whitespace_string(self):
        assert is_number("  ") is False

    def test_list(self):
        assert is_number([1]) is False

    def test_dict(self):
        assert is_number({}) is False


# ===========================================================================
# to_number — edge cases
# ===========================================================================

class TestToNumber:
    def test_default_for_none(self):
        assert to_number(None) == 0.0

    def test_custom_default(self):
        assert to_number(None, default=-1) == -1.0

    def test_string_number(self):
        assert to_number("42") == 42.0

    def test_string_not_number(self):
        assert to_number("abc", default=99) == 99.0

    def test_negative(self):
        assert to_number("-3.5") == -3.5

    def test_zero(self):
        assert to_number("0") == 0.0

    def test_large_number(self):
        assert to_number("999999999999") == 999999999999.0


# ===========================================================================
# format_qty / format_rate — edge cases
# ===========================================================================

class TestFormatQty:
    def test_integer(self):
        assert format_qty(10) == "10"

    def test_decimal(self):
        assert format_qty(10.5) == "10.5"

    def test_zero(self):
        assert format_qty(0) == "0"

    def test_string_ls(self):
        assert format_qty("LS") == "LS"

    def test_string_number(self):
        assert format_qty("3.5") == "3.5"

    def test_large_integer(self):
        assert format_qty(1000) == "1000"

    def test_negative(self):
        assert format_qty(-5) == "-5"

    def test_float_ending_in_zero(self):
        assert format_qty(2.0) == "2"

    def test_very_small(self):
        result = format_qty(0.001)
        assert result == "0.001"


class TestFormatRate:
    def test_integer(self):
        assert format_rate(500) == "500"

    def test_decimal(self):
        assert format_rate(500.50) == "500.5"

    def test_string_ls(self):
        assert format_rate("LS") == "LS"

    def test_zero(self):
        assert format_rate(0) == "0"


# ===========================================================================
# row_amount — edge cases
# ===========================================================================

class TestRowAmount:
    def test_both_numeric_multiply(self):
        assert row_amount("3", "500") == 1500.0

    def test_negative_qty(self):
        assert row_amount("-2", "1000") == -2000.0

    def test_negative_rate(self):
        assert row_amount("2", "-1000") == -2000.0

    def test_both_negative(self):
        assert row_amount("-2", "-1000") == 2000.0

    def test_zero_qty(self):
        assert row_amount("0", "1000") == 0.0

    def test_zero_rate(self):
        assert row_amount("5", "0") == 0.0

    def test_both_zero(self):
        assert row_amount("0", "0") == 0.0

    def test_decimal_qty_times_rate(self):
        assert row_amount("0.5", "1000") == 500.0

    def test_very_large_numbers(self):
        result = row_amount("1000000", "1000000")
        assert result == 1000000000000.0

    def test_very_small_decimal(self):
        result = row_amount("0.001", "100")
        assert result == 0.1

    def test_ls_with_manual_amount(self):
        assert row_amount("LS", "LS", 5000) == 5000.0

    def test_ls_with_numeric_rate(self):
        assert row_amount("LS", "3000") == 3000.0

    def test_ls_with_numeric_qty(self):
        assert row_amount("100", "LS") == 100.0

    def test_ls_all_text_no_manual(self):
        assert row_amount("LS", "LS") is None

    def test_ls_manual_overrides_rate(self):
        # manual_amount takes priority over rate
        assert row_amount("LS", "3000", 7000) == 7000.0

    def test_nan_qty_treated_as_ls(self):
        assert row_amount(float("nan"), "1000") == 1000.0

    def test_nan_rate_treated_as_ls(self):
        assert row_amount("100", float("nan")) == 100.0

    def test_none_qty_with_numeric_rate(self):
        # None is not a number → LS row, rate is numeric candidate
        assert row_amount(None, "500") == 500.0

    def test_none_rate_with_numeric_qty(self):
        assert row_amount("500", None) == 500.0

    def test_both_none(self):
        assert row_amount(None, None) is None

    def test_empty_strings(self):
        assert row_amount("", "") is None

    def test_overflow_precision(self):
        # Python handles big floats; verify no crash
        result = row_amount("999999999999", "999999999999")
        assert result > 0

    def test_negative_amount_ls(self):
        assert row_amount("LS", "LS", -500) == -500.0


# ===========================================================================
# row_is_ls — edge cases
# ===========================================================================

class TestRowIsLs:
    def test_both_numeric(self):
        assert row_is_ls("2", "100") is False

    def test_qty_ls(self):
        assert row_is_ls("LS", "100") is True

    def test_rate_ls(self):
        assert row_is_ls("2", "LS") is True

    def test_both_ls(self):
        assert row_is_ls("LS", "LS") is True

    def test_none_qty(self):
        assert row_is_ls(None, "100") is True

    def test_none_rate(self):
        assert row_is_ls("100", None) is True

    def test_empty_strings(self):
        assert row_is_ls("", "") is True

    def test_numeric_zero(self):
        assert row_is_ls("0", "0") is False


# ===========================================================================
# compute_rows — edge cases
# ===========================================================================

class TestComputeRows:
    def test_empty_rows(self):
        computed, subtotal = compute_rows([])
        assert computed == []
        assert subtotal == 0.0

    def test_all_ls_no_manual(self):
        computed, subtotal = compute_rows([
            d(qty="LS", rate="LS"),
            d(qty="LS", rate="LS"),
        ])
        assert computed == [None, None]
        assert subtotal == 0.0

    def test_mixed_ls_and_numeric(self):
        computed, subtotal = compute_rows([
            d(qty="2", rate="1000"),   # 2000
            d(qty="LS", rate="LS", amount=500),  # 500
            d(qty="LS", rate="LS"),    # None
        ])
        assert computed[0] == 2000.0
        assert computed[1] == 500.0
        assert computed[2] is None
        assert subtotal == 2500.0

    def test_negative_items(self):
        computed, subtotal = compute_rows([
            d(qty="-1", rate="500"),   # -500
            d(qty="3", rate="100"),     # 300
        ])
        assert computed == [-500.0, 300.0]
        assert subtotal == -200.0

    def test_zero_items(self):
        computed, subtotal = compute_rows([
            d(qty="0", rate="1000"),
            d(qty="5", rate="0"),
        ])
        assert computed == [0.0, 0.0]
        assert subtotal == 0.0


# ===========================================================================
# compute_area_totals — edge cases
# ===========================================================================

class TestComputeAreaTotals:
    def test_empty(self):
        assert compute_area_totals([]) == {}

    def test_all_ls_no_manual(self):
        rows = [d(area="HALL", qty="LS", rate="LS")]
        assert compute_area_totals(rows) == {}

    def test_mixed_none_and_numeric(self):
        rows = [
            d(area="A", qty="2", rate="100"),     # 200
            d(area="A", qty="LS", rate="LS"),       # None → skip
            d(area="A", qty="LS", rate="LS", amount=500),  # 500
        ]
        assert compute_area_totals(rows) == {"A": 700.0}

    def test_negative_items_reduce_area(self):
        rows = [
            d(area="HALL", qty="3", rate="1000"),   # 3000
            d(area="HALL", qty="-1", rate="1000"),   # -1000
        ]
        assert compute_area_totals(rows) == {"HALL": 2000.0}

    def test_many_areas(self):
        rows = [d(area=f"AREA{i}", qty="1", rate=str(i)) for i in range(1, 101)]
        totals = compute_area_totals(rows)
        assert len(totals) == 100
        assert totals["AREA1"] == 1.0
        assert totals["AREA100"] == 100.0

    def test_area_name_case_preserved(self):
        rows = [d(area="hall", qty="1", rate="100"), d(area="HALL", qty="1", rate="200")]
        totals = compute_area_totals(rows)
        assert "hall" in totals
        assert "HALL" in totals


# ===========================================================================
# apply_gst — discount clamping
# ===========================================================================

class TestDiscountClamping:
    def test_discount_exceeds_subtotal_clamped(self):
        """Discount > subtotal → clamped to subtotal, grand total = 0."""
        result = apply_gst(subtotal=1000, discount=5000, gst_rate=18)
        assert result["discount"] == 1000.0
        assert result["grand_total"] == 0.0

    def test_discount_equals_subtotal(self):
        """Discount = subtotal → net = 0, GST = 0, grand = 0."""
        result = apply_gst(subtotal=2000, discount=2000, gst_rate=18)
        assert result["discount"] == 2000.0
        assert result["gst_amount"] == 0.0
        assert result["grand_total"] == 0.0

    def test_discount_one_more_than_subtotal(self):
        """Discount = subtotal + 1 → still clamped to subtotal."""
        result = apply_gst(subtotal=100, discount=101, gst_rate=0)
        assert result["discount"] == 100.0
        assert result["grand_total"] == 0.0

    def test_zero_discount(self):
        result = apply_gst(subtotal=1000, discount=0, gst_rate=18)
        assert result["discount"] == 0.0
        assert result["grand_total"] == 1180.0

    def test_fractional_discount_clamped(self):
        """Discount = 1500.5 on subtotal 1000 → clamped to 1000."""
        result = apply_gst(subtotal=1000, discount=1500.5, gst_rate=0)
        assert result["discount"] == 1000.0
        assert result["grand_total"] == 0.0

    def test_negative_discount_clamped_to_zero(self):
        """Negative discount is clamped to 0 — it must never increase the total."""
        result = apply_gst(subtotal=1000, discount=-200, gst_rate=0)
        assert result["discount"] == 0.0
        assert result["grand_total"] == 1000.0

    def test_very_large_discount_on_small_subtotal(self):
        result = apply_gst(subtotal=1, discount=999999, gst_rate=0)
        assert result["discount"] == 1.0
        assert result["grand_total"] == 0.0

    # --- Additional negative discount regression tests ---

    def test_negative_discount_with_gst_on(self):
        """Negative discount with GST ON must not increase total."""
        result = apply_gst(subtotal=10000, discount=-500, gst_rate=18)
        assert result["discount"] == 0.0
        assert result["grand_total"] == 11800.0

    def test_negative_discount_with_gst_off(self):
        """Negative discount with GST OFF must not increase total."""
        result = apply_gst(subtotal=5000, discount=-1000, gst_rate=0)
        assert result["discount"] == 0.0
        assert result["grand_total"] == 5000.0

    def test_decimal_negative_discount(self):
        """Decimal negative discount must be clamped to 0."""
        result = apply_gst(subtotal=3000, discount=-150.75, gst_rate=12)
        assert result["discount"] == 0.0
        assert result["grand_total"] == 3360.0

    def test_positive_decimal_discount_still_works(self):
        """Decimal positive discount must work correctly."""
        result = apply_gst(subtotal=10000, discount=1500.75, gst_rate=18)
        nett = 10000 - 1500.75
        expected_gst = round(nett * 18 / 100, 2)
        assert result["discount"] == 1500.75
        assert result["gst_amount"] == expected_gst
        assert result["grand_total"] == round(nett + expected_gst, 2)

    def test_negative_discount_near_zero(self):
        """Tiny negative discount (-0.01) must be clamped to 0."""
        result = apply_gst(subtotal=1000, discount=-0.01, gst_rate=0)
        assert result["discount"] == 0.0
        assert result["grand_total"] == 1000.0

    def test_discount_boundary_at_zero(self):
        """Discount exactly 0 must remain 0."""
        result = apply_gst(subtotal=500, discount=0, gst_rate=18)
        assert result["discount"] == 0.0
        assert result["grand_total"] == 590.0

    def test_discount_exceeds_subtotal_with_gst(self):
        """Discount > subtotal with GST ON → grand total must be 0."""
        result = apply_gst(subtotal=500, discount=1000, gst_rate=18)
        assert result["discount"] == 500.0
        assert result["grand_total"] == 0.0

    def test_compute_full_invoice_negative_discount(self):
        """Full invoice chain: negative discount must be clamped to 0."""
        rows = [d(area="A", qty="5", rate="1000")]  # 5000
        result = compute_full_invoice(rows, discount=-300, gst_rate=18)
        assert result["subtotal"] == 5000.0
        assert result["discount"] == 0.0
        assert result["gst_amount"] == 900.0  # 5000 * 18%
        assert result["grand_total"] == 5900.0


# ===========================================================================
# apply_gst — zero / negative / edge subtotals
# ===========================================================================

class TestGstEdgeSubtotals:
    def test_zero_subtotal_zero_discount(self):
        result = apply_gst(subtotal=0, discount=0, gst_rate=18)
        assert result["grand_total"] == 0.0

    def test_zero_subtotal_positive_discount_clamped(self):
        result = apply_gst(subtotal=0, discount=100, gst_rate=18)
        assert result["discount"] == 0.0
        assert result["grand_total"] == 0.0

    def test_negative_subtotal(self):
        """Negative subtotal (e.g. all items are credits)."""
        result = apply_gst(subtotal=-500, discount=0, gst_rate=18)
        # disc = min(0, max(-500, 0)) = min(0, 0) = 0
        assert result["discount"] == 0.0
        # nett = -500 - 0 = -500
        assert result["gst_amount"] == -90.0  # -500 * 18%
        assert result["grand_total"] == -590.0

    def test_negative_subtotal_negative_discount_clamped(self):
        result = apply_gst(subtotal=-500, discount=-100, gst_rate=18)
        # disc = max(-100, 0) = 0 (clamped)
        assert result["discount"] == 0.0
        # nett = -500 - 0 = -500
        assert result["gst_amount"] == -90.0
        assert result["grand_total"] == -590.0


# ===========================================================================
# apply_gst — GST rate edge cases
# ===========================================================================

class TestGstRateEdges:
    def test_zero_gst(self):
        result = apply_gst(subtotal=1000, discount=100, gst_rate=0)
        assert result["gst_amount"] == 0.0
        assert result["grand_total"] == 900.0

    def test_100_percent_gst(self):
        result = apply_gst(subtotal=1000, discount=0, gst_rate=100)
        assert result["gst_amount"] == 1000.0
        assert result["grand_total"] == 2000.0

    def test_over_100_percent_gst(self):
        result = apply_gst(subtotal=1000, discount=0, gst_rate=200)
        assert result["gst_amount"] == 2000.0
        assert result["grand_total"] == 3000.0

    def test_fractional_gst_rate(self):
        result = apply_gst(subtotal=1000, discount=0, gst_rate=12.5)
        assert result["gst_amount"] == 125.0
        assert result["grand_total"] == 1125.0

    def test_very_small_gst_rate(self):
        result = apply_gst(subtotal=10000, discount=0, gst_rate=0.01)
        assert result["gst_amount"] == 1.0
        assert result["grand_total"] == 10001.0


# ===========================================================================
# apply_gst — non-numeric inputs
# ===========================================================================

class TestGstNonNumeric:
    def test_none_discount(self):
        result = apply_gst(subtotal=1000, discount=None, gst_rate=18)
        assert result["discount"] == 0.0
        assert result["grand_total"] == 1180.0

    def test_none_gst_rate(self):
        result = apply_gst(subtotal=1000, discount=0, gst_rate=None)
        assert result["gst_rate"] == 0.0
        assert result["grand_total"] == 1000.0

    def test_string_discount(self):
        result = apply_gst(subtotal=1000, discount="abc", gst_rate=18)
        assert result["discount"] == 0.0

    def test_string_gst_rate(self):
        result = apply_gst(subtotal=1000, discount=0, gst_rate="xyz")
        assert result["gst_rate"] == 0.0


# ===========================================================================
# compute_full_invoice — edge cases
# ===========================================================================

class TestFullInvoiceEdges:
    def test_empty_items(self):
        result = compute_full_invoice([], discount=0, gst_rate=18)
        assert result["subtotal"] == 0.0
        assert result["grand_total"] == 0.0
        assert result["area_totals"] == {}

    def test_all_ls_no_manual(self):
        rows = [d(qty="LS", rate="LS"), d(qty="LS", rate="LS")]
        result = compute_full_invoice(rows, discount=0, gst_rate=18)
        assert result["subtotal"] == 0.0
        assert result["grand_total"] == 0.0

    def test_negative_items(self):
        rows = [
            d(area="A", qty="2", rate="1000"),    # 2000
            d(area="A", qty="-1", rate="1000"),    # -1000
        ]
        result = compute_full_invoice(rows, discount=0, gst_rate=18)
        assert result["subtotal"] == 1000.0
        assert result["gst_amount"] == 180.0
        assert result["grand_total"] == 1180.0

    def test_discount_with_negative_items(self):
        """Discount is clamped to subtotal even when items produce negative."""
        rows = [
            d(area="A", qty="1", rate="500"),     # 500
            d(area="B", qty="-1", rate="200"),     # -200
        ]
        result = compute_full_invoice(rows, discount=1000, gst_rate=0)
        # subtotal = 300, discount clamped to 300
        assert result["subtotal"] == 300.0
        assert result["discount"] == 300.0
        assert result["grand_total"] == 0.0

    def test_large_invoice(self):
        rows = [d(area="HALL", qty="1000", rate="100000")]
        result = compute_full_invoice(rows, discount=0, gst_rate=18)
        assert result["subtotal"] == 100000000.0
        assert result["gst_amount"] == 18000000.0
        assert result["grand_total"] == 118000000.0

    def test_subtotal_equals_area_totals_sum(self):
        rows = [
            d(area="A", qty="1", rate="100"),
            d(area="B", qty="2", rate="200"),
            d(area="C", qty="3", rate="300"),
        ]
        result = compute_full_invoice(rows)
        assert result["subtotal"] == sum(result["area_totals"].values())

    def test_discount_gst_combined(self):
        rows = [d(area="A", qty="10", rate="1000")]  # 10000
        result = compute_full_invoice(rows, discount=2000, gst_rate=18)
        # net = 8000, GST = 1440, grand = 9440
        assert result["subtotal"] == 10000.0
        assert result["discount"] == 2000.0
        assert result["gst_amount"] == 1440.0
        assert result["grand_total"] == 9440.0


# ===========================================================================
# amount_in_words — edge cases
# ===========================================================================

class TestAmountInWordsEdges:
    def test_zero(self):
        assert "Zero" in amount_in_words(0)

    def test_exactly_one_rupee(self):
        assert amount_in_words(1) == "One Rupee Only"

    def test_one_paise(self):
        result = amount_in_words(0.01)
        assert "One Paisa" in result

    def test_99_paise(self):
        result = amount_in_words(0.99)
        assert "Ninety Nine Paise" in result

    def test_paise_rounds_up_to_rupee(self):
        """0.999 → rounds to 1.00 → 'One Rupee Only'."""
        result = amount_in_words(0.999)
        assert "One Rupee" in result
        assert "Paise" not in result

    def test_exactly_100_paise(self):
        """1.999 → paise rounds to 100 → becomes 2 rupees."""
        result = amount_in_words(1.999)
        assert "Two Rupees" in result

    def test_negative(self):
        result = amount_in_words(-500)
        assert result.startswith("Minus")
        assert "Five Hundred" in result

    def test_negative_with_paise(self):
        result = amount_in_words(-10.50)
        assert "Minus" in result
        assert "Paise" in result

    def test_string_number(self):
        assert "Five Hundred" in amount_in_words("500")

    def test_none(self):
        assert "Zero" in amount_in_words(None)

    def test_invalid_string(self):
        assert "Zero" in amount_in_words("abc")

    def test_crore_boundary(self):
        result = amount_in_words(10000000)
        assert "One Crore" in result
        assert "Lakh" not in result

    def test_lakh_boundary(self):
        result = amount_in_words(100000)
        assert "One Lakh" in result
        assert "Crore" not in result

    def test_thousand_boundary(self):
        result = amount_in_words(1000)
        assert "One Thousand" in result
        assert "Lakh" not in result

    def test_hundred_boundary(self):
        result = amount_in_words(100)
        assert "One Hundred" in result
        assert "Thousand" not in result

    def test_mixed_places(self):
        """1,23,45,678 → 1 Crore 23 Lakh 45 Thousand 678."""
        result = amount_in_words(12345678)
        assert "One Crore" in result
        assert "Twenty Three Lakh" in result
        assert "Forty Five Thousand" in result
        assert "Six Hundred Seventy Eight" in result

    def test_99_99_999(self):
        result = amount_in_words(9999999)
        assert "Ninety Nine Lakh" in result
        assert "Ninety Nine Thousand" in result
        assert "Nine Hundred Ninety Nine" in result

    def test_exactly_zero_paise(self):
        """100.00 → no paise."""
        result = amount_in_words(100.00)
        assert "Paise" not in result
        assert "Only" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
