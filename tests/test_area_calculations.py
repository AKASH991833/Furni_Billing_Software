"""Tests for the area-wise calculation engine.

Run with:  python -m pytest tests/test_area_calculations.py -q
(from the project root)
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.utils.calculations import (
    compute_area_totals,
    compute_full_invoice,
    compute_rows,
    row_amount,
    apply_gst,
)


def d(area, qty, rate, amount=None):
    """Build a dict row the way the editor does."""
    return {"area": area, "description": "x", "size": "1",
            "qty_raw": qty, "rate_raw": rate, "amount": amount}


class FakeRow:
    """ORM-like object."""
    def __init__(self, area, qty_raw, rate_raw, amount=None):
        self.area = area
        self.qty_raw = qty_raw
        self.rate_raw = rate_raw
        self.amount = amount
        self.qty = None
        self.rate = None


# --------------------------------------------------------------------------
# row_amount
# --------------------------------------------------------------------------

def test_row_amount_numeric():
    assert row_amount("2", "1000") == 2000.0
    assert row_amount(2, 1000) == 2000.0
    assert row_amount("2.5", "1000.50") == 2501.25


def test_row_amount_ls_uses_manual():
    assert row_amount("LS", "1000", 5000) == 5000.0
    assert row_amount("1000", "LS", 7500) == 7500.0
    assert row_amount("LS", "LS", 1234.5) == 1234.5


def test_row_amount_ls_without_manual():
    assert row_amount("LS", "1000") is None
    assert row_amount("LS", "LS") is None
    assert row_amount("", "") is None


def test_row_amount_decimal_and_invalid():
    assert row_amount("1e3", "2") == 2000.0
    assert row_amount("abc", "100") is None
    assert row_amount("100", "xyz") is None
    assert row_amount(float("nan"), "5") is None


# --------------------------------------------------------------------------
# compute_area_totals
# --------------------------------------------------------------------------

def test_single_area_numeric():
    rows = [d("HALL", "2", "1000"), d("HALL", "3", "500")]
    assert compute_area_totals(rows) == {"HALL": 3500.0}


def test_multiple_areas_so_far():
    rows = [
        d("HALL", "2", "1000"),          # 2000
        d("HALL", "2.5", "800"),         # 2000
        d("BEDROOM", "1", "3000"),       # 3000
        d("KITCHEN", "4", "100"),        # 400
    ]
    assert compute_area_totals(rows) == {
        "HALL": 4000.0, "BEDROOM": 3000.0, "KITCHEN": 400.0,
    }


def test_area_total_mixed_ls_and_numeric():
    rows = [
        d("HALL", "2", "1000"),       # 2000
        d("HALL", "LS", "1000", 5000),  # 5000 manual
        d("HALL", "LS", "LS", 700),     # 700 manual
    ]
    assert compute_area_totals(rows) == {"HALL": 7700.0}


def test_area_total_all_ls():
    rows = [
        d("HALL", "LS", "LS", 1000),
        d("HALL", "LS", "LS", 2000),
    ]
    assert compute_area_totals(rows) == {"HALL": 3000.0}


def test_ls_without_manual_excluded_from_area():
    # LS row with NO manual amount contributes nothing to the area total
    rows = [d("HALL", "2", "1000"), d("HALL", "LS", "LS", None)]
    assert compute_area_totals(rows) == {"HALL": 2000.0}
    # manual amount IS still used for LS rows
    rows2 = [d("HALL", "LS", "LS", 500)]
    assert compute_area_totals(rows2) == {"HALL": 500.0}


def test_single_item_area():
    rows = [d("DINING", "1", "15000")]
    assert compute_area_totals(rows) == {"DINING": 15000.0}


def test_empty_rows():
    assert compute_area_totals([]) == {}
    assert compute_full_invoice([])["subtotal"] == 0.0


def test_area_name_whitespace_normalised():
    rows = [d("  HALL  ", "2", "1000")]
    assert compute_area_totals(rows) == {"HALL": 2000.0}


def test_empty_area_falls_back_to_other():
    rows = [d("   ", "2", "1000"), d(None, "1", "500")]
    assert compute_area_totals(rows) == {"OTHER": 2500.0}


def test_orm_objects_area_totals():
    rows = [FakeRow("HALL", "2", "1000"), FakeRow("KITCHEN", "1", "500")]
    assert compute_area_totals(rows) == {"HALL": 2000.0, "KITCHEN": 500.0}
    # LS row on an ORM object uses the manual amount
    rows2 = [FakeRow("KITCHEN", "LS", "LS", 900)]
    assert compute_area_totals(rows2) == {"KITCHEN": 900.0}


def test_no_fixed_limit_many_items():
    rows = [d("HALL", "1", "100") for _ in range(500)]
    assert compute_area_totals(rows) == {"HALL": 50000.0}
    rows2 = [d(f"AREA{i}", "1", "10") for i in range(300)]
    assert len(compute_area_totals(rows2)) == 300


def test_decimal_qty_rate_area():
    rows = [d("HALL", "2.75", "1000.50")]
    assert compute_area_totals(rows) == {"HALL": 2751.38}


# --------------------------------------------------------------------------
# compute_full_invoice
# --------------------------------------------------------------------------

def test_full_invoice_chain():
    rows = [
        d("HALL", "2", "1000"),        # 2000
        d("BEDROOM", "1", "1000"),     # 1000
        d("KITCHEN", "2", "1000"),     # 2000
    ]
    res = compute_full_invoice(rows, discount=500, gst_rate=18)
    assert res["area_totals"] == {"HALL": 2000.0, "BEDROOM": 1000.0, "KITCHEN": 2000.0}
    assert res["subtotal"] == 5000.0
    assert res["discount"] == 500.0
    nett = 5000 - 500
    assert res["gst_amount"] == round(nett * 18 / 100, 2)   # 810.0
    assert res["grand_total"] == round(nett + 810.0, 2)     # 5310.0


def test_full_invoice_no_discount_no_gst():
    rows = [d("HALL", "2", "1000")]
    res = compute_full_invoice(rows, 0, 0)
    assert res["subtotal"] == 2000.0
    assert res["gst_amount"] == 0.0
    assert res["grand_total"] == 2000.0


def test_full_invoice_large_numbers():
    rows = [d("HALL", "1000000", "1000")]  # 1,000,000,000
    res = compute_full_invoice(rows, gst_rate=18)
    assert res["subtotal"] == 1000000000.0
    assert res["grand_total"] == 1180000000.0


def test_full_invoice_negative_discount():
    res = compute_full_invoice([d("HALL", "2", "1000")], discount=-100, gst_rate=0)
    assert res["subtotal"] == 2000.0
    assert res["grand_total"] == 2100.0


def test_subtotal_equals_sum_of_area_totals():
    rows = [d("A", "1", "100"), d("B", "2", "50"), d("C", "3", "100")]
    res = compute_full_invoice(rows)
    assert res["subtotal"] == sum(res["area_totals"].values())


# --------------------------------------------------------------------------
# compute_rows still works (back-compat)
# --------------------------------------------------------------------------

def test_compute_rows_backward_compatible():
    rows = [d("HALL", "2", "1000"), d("LS", "LS", None, 500)]
    computed, subtotal = compute_rows(rows)
    assert computed == [2000.0, 500.0]
    assert subtotal == 2500.0


def test_apply_gst_unchanged():
    assert apply_gst(1000, 100, 18) == {
        "subtotal": 1000.0, "discount": 100.0, "gst_rate": 18.0,
        "gst_amount": 162.0, "grand_total": 1062.0,
    }


# --------------------------------------------------------------------------
# Standalone runner (no pytest dependency)
# --------------------------------------------------------------------------
if __name__ == "__main__":
    import traceback
    fns = [
        (name, obj) for name, obj in sorted(globals().items())
        if name.startswith("test_") and callable(obj)
    ]
    passed = failed = 0
    for name, fn in fns:
        try:
            fn()
            print(f"PASS  {name}")
            passed += 1
        except Exception:
            print(f"FAIL  {name}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed out of {passed + failed}")
    sys.exit(1 if failed else 0)
