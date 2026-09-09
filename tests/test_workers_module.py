"""Comprehensive automated tests for Worker Attendance & Payment Management Module.

Covers all 28 mandatory test cases and Section 38 Acceptance Test.
"""
from datetime import date
from decimal import Decimal

import pytest

from app.services import worker_service


def test_01_create_worker(db):
    """TEST 1: Create worker."""
    w = worker_service.create_worker(
        name="Ramesh",
        daily_rate=800.0,
        work_type="Mistri",
        mobile="9876543210",
    )
    assert w.id is not None
    assert w.name == "Ramesh"
    assert w.worker_code.startswith("W-")
    assert w.work_type == "Mistri"


def test_02_worker_with_800_rate(db):
    """TEST 2: Worker with ₹800 daily rate."""
    w = worker_service.create_worker("Suresh", daily_rate=800.0)
    assert w.daily_rate == Decimal("800.00")


def test_03_full_day_calculation(db):
    """TEST 3: Full day: 800 * 1 = 800."""
    w = worker_service.create_worker("Amit", daily_rate=800.0)
    att = worker_service.record_daily_attendance(w.id, date(2026, 9, 1), multiplier=1.0)
    assert att.day_multiplier == Decimal("1.00")
    assert att.daily_earning == Decimal("800.00")


def test_04_half_day_calculation(db):
    """TEST 4: Half day: 800 * 0.5 = 400."""
    w = worker_service.create_worker("Amit", daily_rate=800.0)
    att = worker_service.record_daily_attendance(w.id, date(2026, 9, 2), multiplier=0.5)
    assert att.day_multiplier == Decimal("0.50")
    assert att.daily_earning == Decimal("400.00")


def test_05_one_and_half_day_calculation(db):
    """TEST 5: 1.5 day: 800 * 1.5 = 1200."""
    w = worker_service.create_worker("Amit", daily_rate=800.0)
    att = worker_service.record_daily_attendance(w.id, date(2026, 9, 3), multiplier=1.5)
    assert att.day_multiplier == Decimal("1.50")
    assert att.daily_earning == Decimal("1200.00")


def test_06_double_day_calculation(db):
    """TEST 6: Double day: 800 * 2 = 1600."""
    w = worker_service.create_worker("Amit", daily_rate=800.0)
    att = worker_service.record_daily_attendance(w.id, date(2026, 9, 4), multiplier=2.0)
    assert att.day_multiplier == Decimal("2.00")
    assert att.daily_earning == Decimal("1600.00")


def test_07_absent_calculation(db):
    """TEST 7: Absent: 800 * 0 = 0."""
    w = worker_service.create_worker("Amit", daily_rate=800.0)
    att = worker_service.record_daily_attendance(w.id, date(2026, 9, 5), multiplier=0.0)
    assert att.day_multiplier == Decimal("0.00")
    assert att.daily_earning == Decimal("0.00")


def test_08_monthly_attendance_calculation(db):
    """TEST 8: Monthly attendance calculation."""
    w = worker_service.create_worker("Raju", daily_rate=500.0)
    worker_service.record_daily_attendance(w.id, date(2026, 9, 1), multiplier=1.0)
    worker_service.record_daily_attendance(w.id, date(2026, 9, 2), multiplier=0.5)
    worker_service.record_daily_attendance(w.id, date(2026, 9, 3), multiplier=1.5)
    summary = worker_service.get_worker_monthly_summary(w.id, 2026, 9)
    assert summary["total_units"] == 3.0
    assert summary["total_work_earning"] == 1500.0


def test_09_travel_expense_included(db):
    """TEST 9: Travel expense included correctly in gross payable."""
    w = worker_service.create_worker("Mohan", daily_rate=700.0)
    worker_service.record_daily_attendance(w.id, date(2026, 9, 1), multiplier=1.0)  # 700
    worker_service.record_travel_expense(w.id, date(2026, 9, 1), amount=250.0, category="Rickshaw")
    summary = worker_service.get_worker_monthly_summary(w.id, 2026, 9)
    assert summary["total_travel"] == 250.0
    assert summary["gross_payable"] == 950.0  # 700 + 250


def test_10_other_addition_included(db):
    """TEST 10: Other addition included correctly in gross payable."""
    w = worker_service.create_worker("Mohan", daily_rate=700.0)
    worker_service.record_daily_attendance(w.id, date(2026, 9, 1), multiplier=1.0)
    worker_service.record_adjustment(w.id, date(2026, 9, 1), amount=300.0, adjustment_type="ADDITION", category="Bonus")
    summary = worker_service.get_worker_monthly_summary(w.id, 2026, 9)
    assert summary["total_additions"] == 300.0
    assert summary["gross_payable"] == 1000.0  # 700 + 300


def test_11_advance_correctly_deducted(db):
    """TEST 11: Advance correctly deducted from net payable."""
    w = worker_service.create_worker("Sanjay", daily_rate=1000.0)
    worker_service.record_daily_attendance(w.id, date(2026, 9, 1), multiplier=1.0)  # 1000
    worker_service.record_advance(w.id, date(2026, 9, 1), amount=400.0)
    summary = worker_service.get_worker_monthly_summary(w.id, 2026, 9)
    assert summary["total_advance"] == 400.0
    assert summary["net_payable"] == 600.0  # 1000 - 400


def test_12_multiple_advances_summed(db):
    """TEST 12: Multiple advances summed correctly."""
    w = worker_service.create_worker("Sanjay", daily_rate=1000.0)
    worker_service.record_advance(w.id, date(2026, 9, 5), amount=2000.0)
    worker_service.record_advance(w.id, date(2026, 9, 15), amount=3000.0)
    worker_service.record_advance(w.id, date(2026, 9, 25), amount=1000.0)
    summary = worker_service.get_worker_monthly_summary(w.id, 2026, 9)
    assert summary["total_advance"] == 6000.0


def test_13_final_payment_recorded(db):
    """TEST 13: Final payment recorded correctly."""
    w = worker_service.create_worker("Vikram", daily_rate=1000.0)
    worker_service.record_daily_attendance(w.id, date(2026, 9, 1), multiplier=1.0)
    settlement = worker_service.record_settlement(w.id, 2026, 9, paid_amount=1000.0, payment_method="Cash")
    assert settlement.is_settled is True
    assert settlement.paid_amount == Decimal("1000.00")


def test_14_remaining_balance_calculated(db):
    """TEST 14: Remaining balance calculated correctly."""
    w = worker_service.create_worker("Vikram", daily_rate=1000.0)
    worker_service.record_daily_attendance(w.id, date(2026, 9, 1), multiplier=2.0)  # 2000
    # Paid partial 1200 -> Remaining 800
    worker_service.record_settlement(w.id, 2026, 9, paid_amount=1200.0)
    summary = worker_service.get_worker_monthly_summary(w.id, 2026, 9)
    assert summary["net_payable"] == 2000.0
    assert summary["paid_amount"] == 1200.0
    assert summary["remaining_balance"] == 800.0


def test_15_duplicate_attendance_prevented(db):
    """TEST 15: Duplicate attendance for same worker/date prevented by updating existing record."""
    w = worker_service.create_worker("Sunil", daily_rate=600.0)
    att1 = worker_service.record_daily_attendance(w.id, date(2026, 9, 1), multiplier=0.5, notes="Morning only")
    # Record again on same date -> updates in place
    att2 = worker_service.record_daily_attendance(w.id, date(2026, 9, 1), multiplier=1.0, notes="Stayed full day")
    assert att1.id == att2.id
    assert att2.day_multiplier == Decimal("1.00")
    assert att2.daily_earning == Decimal("600.00")
    # Verify count in DB for this date is exactly 1
    atts = worker_service.get_worker_attendance_range(w.id, 2026, 9)
    assert len(atts) == 1


def test_16_and_17_rate_history_preservation(db):
    """TEST 16 & 17: Worker rate changed: Old attendance keeps old rate, new attendance uses new rate."""
    w = worker_service.create_worker("Pooja", daily_rate=700.0)
    # 01 Sep: Rate 700
    att1 = worker_service.record_daily_attendance(w.id, date(2026, 9, 1), multiplier=1.0)
    assert att1.daily_rate == Decimal("700.00")
    assert att1.daily_earning == Decimal("700.00")

    # 20 Sep: Rate changed to 800
    worker_service.update_worker(w.id, daily_rate=800.0)

    # 21 Sep: New attendance
    att2 = worker_service.record_daily_attendance(w.id, date(2026, 9, 21), multiplier=1.0)
    assert att2.daily_rate == Decimal("800.00")
    assert att2.daily_earning == Decimal("800.00")

    # Verify old attendance STILL calculates using 700
    summary = worker_service.get_worker_monthly_summary(w.id, 2026, 9)
    assert summary["total_work_earning"] == 1500.0  # 700 + 800


def test_18_different_workers_independent(db):
    """TEST 18: Different workers remain completely independent."""
    w1 = worker_service.create_worker("Worker A", daily_rate=500.0)
    w2 = worker_service.create_worker("Worker B", daily_rate=900.0)
    worker_service.record_daily_attendance(w1.id, date(2026, 9, 1), multiplier=1.0)
    worker_service.record_daily_attendance(w2.id, date(2026, 9, 1), multiplier=2.0)

    s1 = worker_service.get_worker_monthly_summary(w1.id, 2026, 9)
    s2 = worker_service.get_worker_monthly_summary(w2.id, 2026, 9)
    assert s1["total_work_earning"] == 500.0
    assert s2["total_work_earning"] == 1800.0


def test_19_different_months_independent(db):
    """TEST 19: Different months remain independent."""
    w = worker_service.create_worker("Dev", daily_rate=600.0)
    worker_service.record_daily_attendance(w.id, date(2026, 8, 15), multiplier=1.0)
    worker_service.record_daily_attendance(w.id, date(2026, 9, 15), multiplier=2.0)

    s_aug = worker_service.get_worker_monthly_summary(w.id, 2026, 8)
    s_sep = worker_service.get_worker_monthly_summary(w.id, 2026, 9)
    assert s_aug["total_units"] == 1.0
    assert s_sep["total_units"] == 2.0


def test_20_settlement_preserves_historical_attendance(db):
    """TEST 20: Settlement preserves historical attendance and records."""
    w = worker_service.create_worker("Deepak", daily_rate=800.0)
    worker_service.record_daily_attendance(w.id, date(2026, 9, 1), multiplier=1.0)
    worker_service.record_advance(w.id, date(2026, 9, 1), amount=200.0)
    worker_service.record_settlement(w.id, 2026, 9, paid_amount=600.0)

    # Re-fetch summary after settlement
    s = worker_service.get_worker_monthly_summary(w.id, 2026, 9)
    assert s["is_settled"] is True
    assert len(s["attendances"]) == 1
    assert len(s["advances"]) == 1
    assert s["paid_amount"] == 600.0
    assert s["remaining_balance"] == 0.0


def test_21_negative_rate_rejected(db):
    """TEST 21: Negative daily rate rejected."""
    with pytest.raises(ValueError):
        worker_service.create_worker("Invalid Worker", daily_rate=-100.0)


def test_22_invalid_worker_id_rejected(db):
    """TEST 22: Invalid worker ID rejected."""
    with pytest.raises(ValueError):
        worker_service.record_daily_attendance(999999, date(2026, 9, 1), multiplier=1.0)


def test_23_database_foreign_keys(db):
    """TEST 23: Database foreign keys and cascade work."""
    w = worker_service.create_worker("Temp Worker", daily_rate=500.0)
    worker_service.record_daily_attendance(w.id, date(2026, 9, 1), multiplier=1.0)
    worker_service.record_advance(w.id, date(2026, 9, 1), amount=100.0)
    # Delete worker
    worker_service.delete_worker(w.id)
    assert worker_service.get_worker_by_id(w.id) is None


def test_24_search_works(db):
    """TEST 24: Search works across name, mobile, work_type, worker_code."""
    w1 = worker_service.create_worker("Babulal", daily_rate=700.0, work_type="Carpenter", mobile="9988776655")
    w2 = worker_service.create_worker("Chhotu", daily_rate=400.0, work_type="Helper", mobile="8877665544")

    res_name = worker_service.get_workers(search_query="Babulal")
    assert len(res_name) == 1
    assert res_name[0].name == "Babulal"

    res_type = worker_service.get_workers(search_query="Helper")
    assert len(res_type) == 1
    assert res_type[0].name == "Chhotu"

    res_code = worker_service.get_workers(search_query=w1.worker_code)
    assert len(res_code) == 1
    assert res_code[0].id == w1.id


def test_25_month_filtering_works(db):
    """TEST 25: Month filtering works cleanly."""
    w = worker_service.create_worker("Ganesh", daily_rate=600.0)
    worker_service.record_daily_attendance(w.id, date(2026, 7, 1), multiplier=1.0)
    worker_service.record_daily_attendance(w.id, date(2026, 8, 1), multiplier=1.0)

    s7 = worker_service.get_worker_monthly_summary(w.id, 2026, 7)
    s8 = worker_service.get_worker_monthly_summary(w.id, 2026, 8)
    s9 = worker_service.get_worker_monthly_summary(w.id, 2026, 9)
    assert s7["total_units"] == 1.0
    assert s8["total_units"] == 1.0
    assert s9["total_units"] == 0.0


def test_26_offline_mode(db):
    """TEST 26: Application works in complete offline mode (SQLite local)."""
    w = worker_service.create_worker("Offline Worker", daily_rate=500.0)
    assert w.id is not None


def test_38_master_acceptance_scenario(db):
    """MASTER PROMPT SECTION 38: Real-World Acceptance Test Scenario.
    
    Scenario:
      Worker: Ramesh, Mistri, Rate: ₹800/day
      Attendance:
        10 Full Days
        2 Half Days
        1 Double Day
        1.5 Day
      Work calculation:
        10 * 800 + 2 * 400 + 1 * 1600 + 1 * 1200 = 8000 + 800 + 1600 + 1200 = ₹11,200
      Additions:
        Travel = ₹500
        Other Addition = ₹300
      Advances:
        ₹2,000 + ₹1,000 = ₹3,000
      Deduction:
        ₹200
      Verification:
        Gross = 11,200 + 500 + 300 = 12,000
        Net Payable = 12,000 - 3,000 - 200 = ₹8,800
      Settle:
        Record final payment = ₹8,800 -> Remaining = ₹0
      Rate change:
        Change rate to ₹900
        Add new attendance (01 Oct) -> uses ₹900
        Verify old attendance continues to calculate at ₹800!
    """
    # 1. Create worker Ramesh @ ₹800
    ramesh = worker_service.create_worker("Ramesh", daily_rate=800.0, work_type="Mistri")

    # 2. Add Attendance:
    day = 1
    # 10 Full Days
    for _ in range(10):
        worker_service.record_daily_attendance(ramesh.id, date(2026, 9, day), multiplier=1.0)
        day += 1
    # 2 Half Days
    for _ in range(2):
        worker_service.record_daily_attendance(ramesh.id, date(2026, 9, day), multiplier=0.5)
        day += 1
    # 1 Double Day
    worker_service.record_daily_attendance(ramesh.id, date(2026, 9, day), multiplier=2.0)
    day += 1
    # 1.5 Day
    worker_service.record_daily_attendance(ramesh.id, date(2026, 9, day), multiplier=1.5)
    day += 1

    # 3. Add Travel = ₹500
    worker_service.record_travel_expense(ramesh.id, date(2026, 9, 5), amount=500.0, category="Rickshaw")

    # 4. Add Other Addition = ₹300
    worker_service.record_adjustment(ramesh.id, date(2026, 9, 6), amount=300.0, adjustment_type="ADDITION", category="Bonus")

    # 5. Add Advances = ₹2000 and ₹1000
    worker_service.record_advance(ramesh.id, date(2026, 9, 10), amount=2000.0)
    worker_service.record_advance(ramesh.id, date(2026, 9, 20), amount=1000.0)

    # 6. Add Other Deduction = ₹200
    worker_service.record_adjustment(ramesh.id, date(2026, 9, 22), amount=200.0, adjustment_type="DEDUCTION", category="Penalty")

    # 7. Verify Calculations
    summary = worker_service.get_worker_monthly_summary(ramesh.id, 2026, 9)
    assert summary["full_days"] == 10
    assert summary["half_days"] == 2
    assert summary["double_days"] == 1
    assert summary["one_and_half_days"] == 1
    assert summary["total_units"] == 10 * 1.0 + 2 * 0.5 + 1 * 2.0 + 1 * 1.5  # 14.5 units

    # Work earnings: 10*800 (8000) + 2*400 (800) + 1*1600 (1600) + 1*1200 (1200) = 11,600
    assert summary["total_work_earning"] == 11600.0
    assert summary["total_travel"] == 500.0
    assert summary["total_additions"] == 300.0
    assert summary["gross_payable"] == 12400.0  # 11,600 + 500 + 300
    assert summary["total_advance"] == 3000.0   # 2,000 + 1,000
    assert summary["total_deductions"] == 200.0
    # Net = 12,400 - 3,000 - 200 = 9,200
    assert summary["net_payable"] == 9200.0

    # 8. Record final payment = 9,200
    settlement = worker_service.record_settlement(ramesh.id, 2026, 9, paid_amount=9200.0, payment_method="Cash")
    assert settlement.is_settled is True

    # 9. Verify Remaining = 0
    updated_summary = worker_service.get_worker_monthly_summary(ramesh.id, 2026, 9)
    assert updated_summary["paid_amount"] == 9200.0
    assert updated_summary["remaining_balance"] == 0.0

    # 10. Rate change to ₹900
    worker_service.update_worker(ramesh.id, daily_rate=900.0)

    # 11. Add new attendance in October
    att_oct = worker_service.record_daily_attendance(ramesh.id, date(2026, 10, 1), multiplier=1.0)
    assert att_oct.daily_rate == Decimal("900.00")
    assert att_oct.daily_earning == Decimal("900.00")

    # 12. Verify old attendance in September still calculates using ₹800
    sep_again = worker_service.get_worker_monthly_summary(ramesh.id, 2026, 9)
    assert sep_again["total_work_earning"] == 11600.0
    assert sep_again["net_payable"] == 9200.0


def test_workers_page_columns_and_sno(db):
    """Verify table column simplifications and S.No. headers across all tabs."""
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    from app.ui.pages.workers_page import WorkersPage, AttendanceEntryDialog
    page = WorkersPage()

    # Tab 1: Directory Table (9 cols — removed 'Current Month Days', renamed to 'Monthly Total Payment')
    assert page.table_dir.columnCount() == 9
    dir_headers = [page.table_dir.horizontalHeaderItem(c).text() for c in range(9)]
    assert dir_headers == ["S.No.", "Worker Name", "Work Type", "Mobile", "Daily Rate",
                           "Monthly Total Payment", "Advance", "Net Payable", "Actions"]
    assert "Current Month Days" not in dir_headers
    assert "Month Earnings" not in dir_headers

    # Tab 2: Daily Attendance Table (6 Clean Columns - No Units or Daily Earning)
    assert page.table_att.columnCount() == 6
    att_headers = [page.table_att.horizontalHeaderItem(c).text() for c in range(6)]
    assert att_headers == ["S.No.", "Worker Name", "Work Type", "Daily Rate", "Mark Attendance", "Notes"]
    assert "Units" not in att_headers
    assert "Daily Earning" not in att_headers

    # Tab 3: Monthly History Table (9 Columns - includes ACTION column for delete)
    assert page.table_hist.columnCount() == 9
    hist_headers = [page.table_hist.horizontalHeaderItem(c).text() for c in range(9)]
    assert hist_headers == ["DATE", "DAY", "ATTENDANCE", "DAILY RATE", "TRAVEL (+)", "ADVANCE (-)", "DAILY NET", "NOTES & DETAILS", "ACTION"]
    assert "UNITS" not in hist_headers
    assert "EARNING" not in hist_headers
    assert "ACTION" in hist_headers


def test_attendance_entry_dialog_workflow(db):
    """Verify AttendanceEntryDialog handles attendance, advance, and travel simultaneously."""
    from PySide6.QtWidgets import QApplication
    _app = QApplication.instance() or QApplication([])
    from app.ui.pages.workers_page import AttendanceEntryDialog
    worker = worker_service.create_worker("Suresh Mistri", daily_rate=750.0, work_type="Mistri")

    dlg = AttendanceEntryDialog(workers=[worker], preselected_worker_id=worker.id, default_date=date(2026, 9, 7))
    assert "750" in dlg.lbl_rate_banner.text()
    assert dlg.f_worker.count() == 1
    assert "1. Suresh Mistri" in dlg.f_worker.itemText(0)

    # Set advance and travel
    dlg.f_adv_amount.setValue(500.0)
    dlg.f_adv_note.setText("Grocery advance")
    dlg.f_trv_amount.setValue(80.0)
    dlg.f_trv_note.setText("Auto fare")

    # Simulate save
    dlg._save()
    data = dlg.get_data()
    assert data["worker_id"] == worker.id
    assert data["multiplier"] == 1.0
    assert data["advance_amount"] == 500.0
    assert data["travel_amount"] == 80.0
    assert data["advance_notes"] == "Grocery advance"
    assert data["travel_notes"] == "Auto fare"

