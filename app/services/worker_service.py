"""Worker Attendance & Payment Management Service.

Pure, deterministic, and Decimal-safe business logic for:
- Worker profiles with auto-generated IDs (W-001, W-002, etc.).
- Daily attendance with rate preservation and daily earning calculation.
- Travel/rickshaw expense tracking.
- Other adjustments (strictly separated additions and deductions).
- Advance payments (history permanently preserved).
- Deterministic monthly calculation engine.
- Monthly settlement recording and dashboard metrics.
"""
from __future__ import annotations

import calendar
import re
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import and_, desc, extract, func, or_

from app.database.database import get_session
from app.models.models import (
    Worker,
    WorkerAdjustment,
    WorkerAdvance,
    WorkerAttendance,
    WorkerExpense,
    WorkerSettlement,
)

# Standard multiplier labels
MULTIPLIER_MAP = {
    Decimal("0.0"): "Absent",
    Decimal("0.5"): "Half Day",
    Decimal("1.0"): "Full Day",
    Decimal("1.5"): "1.5 Day",
    Decimal("2.0"): "Double Day",
}


def _dec(v: Any) -> Decimal:
    """Safe Decimal conversion."""
    if v is None:
        return Decimal("0.00")
    try:
        return Decimal(str(v))
    except Exception:
        return Decimal("0.00")


def _quant(d: Decimal) -> Decimal:
    """Quantize to 2 decimal places."""
    return d.quantize(Decimal("0.01"))


# ===========================================================================
# 1. Worker Profiles CRUD
# ===========================================================================

def generate_next_worker_code() -> str:
    """Generate sequential worker code like W-001, W-002."""
    session = get_session()
    try:
        codes = [r[0] for r in session.query(Worker.worker_code).all() if r[0]]
        max_num = 0
        for code in codes:
            match = re.search(r"W-(\d+)", code, re.IGNORECASE)
            if match:
                max_num = max(max_num, int(match.group(1)))
        return f"W-{max_num + 1:03d}"
    finally:
        session.close()


def create_worker(
    name: str,
    daily_rate: float | Decimal,
    mobile: str = "",
    work_type: str = "Mistri",
    joining_date: date | None = None,
    address: str = "",
    notes: str = "",
    worker_code: str | None = None,
) -> Worker:
    """Create a new worker profile. Validates non-empty name and daily_rate >= 0."""
    name_clean = (name or "").strip()
    if not name_clean:
        raise ValueError("Worker name cannot be empty.")

    rate_dec = _dec(daily_rate)
    if rate_dec < Decimal("0.00"):
        raise ValueError("Daily rate cannot be negative.")

    code = (worker_code or "").strip() or generate_next_worker_code()

    session = get_session()
    try:
        # Check duplicate code
        existing = session.query(Worker).filter(Worker.worker_code == code).first()
        if existing:
            code = generate_next_worker_code()

        worker = Worker(
            worker_code=code,
            name=name_clean,
            mobile=(mobile or "").strip(),
            work_type=(work_type or "Mistri").strip(),
            daily_rate=rate_dec,
            joining_date=joining_date or date.today(),
            address=(address or "").strip(),
            is_active=True,
            notes=(notes or "").strip(),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(worker)
        session.commit()
        session.refresh(worker)
        return worker
    finally:
        session.close()


def get_workers(
    search_query: str = "",
    work_type: str | None = None,
    is_active: bool | None = None,
) -> list[Worker]:
    """Retrieve workers with database-side search and filtering."""
    session = get_session()
    try:
        query = session.query(Worker)

        if is_active is not None:
            query = query.filter(Worker.is_active == is_active)

        if work_type and work_type.upper() != "ALL":
            query = query.filter(Worker.work_type == work_type)

        if search_query:
            term = f"%{search_query.strip()}%"
            query = query.filter(
                or_(
                    Worker.name.ilike(term),
                    Worker.mobile.ilike(term),
                    Worker.worker_code.ilike(term),
                    Worker.work_type.ilike(term),
                )
            )

        return query.order_by(desc(Worker.is_active), Worker.name.asc()).all()
    finally:
        session.close()


def get_worker_by_id(worker_id: int) -> Worker | None:
    """Get single worker by ID."""
    session = get_session()
    try:
        return session.query(Worker).filter(Worker.id == worker_id).first()
    finally:
        session.close()


def update_worker(worker_id: int, **kwargs) -> Worker | None:
    """Update worker fields. Validates non-negative daily rate."""
    session = get_session()
    try:
        w = session.query(Worker).filter(Worker.id == worker_id).first()
        if not w:
            return None

        if "name" in kwargs:
            name_clean = (kwargs["name"] or "").strip()
            if not name_clean:
                raise ValueError("Worker name cannot be empty.")
            w.name = name_clean

        if "daily_rate" in kwargs:
            rate_dec = _dec(kwargs["daily_rate"])
            if rate_dec < Decimal("0.00"):
                raise ValueError("Daily rate cannot be negative.")
            w.daily_rate = rate_dec

        if "mobile" in kwargs:
            w.mobile = (kwargs["mobile"] or "").strip()
        if "work_type" in kwargs:
            w.work_type = (kwargs["work_type"] or "Mistri").strip()
        if "joining_date" in kwargs and kwargs["joining_date"]:
            w.joining_date = kwargs["joining_date"]
        if "address" in kwargs:
            w.address = (kwargs["address"] or "").strip()
        if "notes" in kwargs:
            w.notes = (kwargs["notes"] or "").strip()
        if "is_active" in kwargs:
            w.is_active = bool(kwargs["is_active"])

        w.updated_at = datetime.now(timezone.utc)
        session.commit()
        session.refresh(w)
        return w
    finally:
        session.close()


def toggle_worker_status(worker_id: int) -> bool:
    """Toggle active/inactive status."""
    session = get_session()
    try:
        w = session.query(Worker).filter(Worker.id == worker_id).first()
        if not w:
            return False
        w.is_active = not bool(w.is_active)
        w.updated_at = datetime.now(timezone.utc)
        session.commit()
        return bool(w.is_active)
    finally:
        session.close()


def delete_worker(worker_id: int) -> bool:
    """Delete worker and cascade records."""
    session = get_session()
    try:
        w = session.query(Worker).filter(Worker.id == worker_id).first()
        if not w:
            return False
        session.delete(w)
        session.commit()
        return True
    finally:
        session.close()


# ===========================================================================
# 2. Daily Attendance & Rate History Preservation
# ===========================================================================

def record_daily_attendance(
    worker_id: int,
    att_date: date,
    multiplier: float | Decimal,
    status_label: str | None = None,
    notes: str = "",
    rate_override: float | Decimal | None = None,
) -> WorkerAttendance:
    """Record daily attendance with rate freezing and upsert protection.
    
    Guarantees:
      - Multiplier cannot be negative.
      - Daily rate is frozen on the record to protect historical calculations.
      - Daily earning = round(daily_rate * multiplier, 2).
      - If attendance already exists for (worker_id, att_date), updates existing record.
    """
    mult_dec = _dec(multiplier)
    if mult_dec < Decimal("0.00"):
        raise ValueError("Attendance multiplier cannot be negative.")

    session = get_session()
    try:
        worker = session.query(Worker).filter(Worker.id == worker_id).first()
        if not worker:
            raise ValueError(f"Worker with id {worker_id} not found.")

        # Determine rate: use override if provided, else worker's current rate
        if rate_override is not None:
            rate_dec = _dec(rate_override)
            if rate_dec < Decimal("0.00"):
                raise ValueError("Daily rate cannot be negative.")
        else:
            rate_dec = _dec(worker.daily_rate)

        earning_dec = _quant(rate_dec * mult_dec)

        # Label resolution
        if not status_label:
            status_label = MULTIPLIER_MAP.get(mult_dec, f"{mult_dec:g} Day")

        # Upsert: check existing record
        att = (
            session.query(WorkerAttendance)
            .filter(
                WorkerAttendance.worker_id == worker_id,
                WorkerAttendance.attendance_date == att_date,
            )
            .first()
        )

        if att:
            att.day_multiplier = mult_dec
            att.status_label = status_label
            # If rate_override was explicitly given, update rate & earning, otherwise keep or update
            if rate_override is not None:
                att.daily_rate = rate_dec
            att.daily_earning = _quant(att.daily_rate * mult_dec)
            if notes is not None:
                att.notes = (notes or "").strip()
        else:
            att = WorkerAttendance(
                worker_id=worker_id,
                attendance_date=att_date,
                day_multiplier=mult_dec,
                status_label=status_label,
                daily_rate=rate_dec,
                daily_earning=earning_dec,
                notes=(notes or "").strip(),
                created_at=datetime.now(timezone.utc),
            )
            session.add(att)

        session.commit()
        session.refresh(att)
        return att
    finally:
        session.close()


def get_daily_attendance(att_date: date) -> dict[int, dict]:
    """Fetch attendance records for a specific date keyed by worker_id."""
    session = get_session()
    try:
        rows = (
            session.query(WorkerAttendance)
            .filter(WorkerAttendance.attendance_date == att_date)
            .all()
        )
        return {
            r.worker_id: {
                "id": r.id,
                "day_multiplier": float(r.day_multiplier or 0),
                "status_label": r.status_label or "Full Day",
                "daily_rate": float(r.daily_rate or 0),
                "daily_earning": float(r.daily_earning or 0),
                "notes": r.notes or "",
            }
            for r in rows
        }
    finally:
        session.close()


def mark_all_full_day(att_date: date) -> None:
    """Mark all active workers as Full Day (1.0) if not already recorded."""
    session = get_session()
    try:
        workers = session.query(Worker).filter(Worker.is_active.is_(True)).all()
        for w in workers:
            att = (
                session.query(WorkerAttendance)
                .filter(
                    WorkerAttendance.worker_id == w.id,
                    WorkerAttendance.attendance_date == att_date,
                )
                .first()
            )
            if not att:
                rate = _dec(w.daily_rate)
                att = WorkerAttendance(
                    worker_id=w.id,
                    attendance_date=att_date,
                    day_multiplier=Decimal("1.0"),
                    status_label="Full Day",
                    daily_rate=rate,
                    daily_earning=_quant(rate * Decimal("1.0")),
                    notes="",
                    created_at=datetime.now(timezone.utc),
                )
                session.add(att)
        session.commit()
    finally:
        session.close()


def get_worker_attendance_range(
    worker_id: int,
    year: int,
    month: int,
) -> list[WorkerAttendance]:
    """Retrieve ordered monthly attendance for a specific worker."""
    session = get_session()
    try:
        return (
            session.query(WorkerAttendance)
            .filter(
                WorkerAttendance.worker_id == worker_id,
                extract("year", WorkerAttendance.attendance_date) == year,
                extract("month", WorkerAttendance.attendance_date) == month,
            )
            .order_by(WorkerAttendance.attendance_date.asc())
            .all()
        )
    finally:
        session.close()


def delete_attendance(worker_id: int, att_date: date) -> bool:
    """Permanently delete an attendance record for a worker on a specific date.
    
    Returns True if a record was found and deleted, False if no record existed.
    """
    session = get_session()
    try:
        att = (
            session.query(WorkerAttendance)
            .filter(
                WorkerAttendance.worker_id == worker_id,
                WorkerAttendance.attendance_date == att_date,
            )
            .first()
        )
        if att:
            session.delete(att)
            session.commit()
            return True
        return False
    finally:
        session.close()


# ===========================================================================
# 3. Travel & Rickshaw Expenses
# ===========================================================================

def record_travel_expense(
    worker_id: int,
    expense_date: date,
    amount: float | Decimal,
    category: str = "Rickshaw",
    notes: str = "",
) -> WorkerExpense:
    """Record out-of-pocket travel/rickshaw expense incurred by worker."""
    amt_dec = _dec(amount)
    if amt_dec <= Decimal("0.00"):
        raise ValueError("Expense amount must be greater than 0.")

    session = get_session()
    try:
        exp = WorkerExpense(
            worker_id=worker_id,
            expense_date=expense_date,
            amount=amt_dec,
            category=(category or "Rickshaw").strip(),
            notes=(notes or "").strip(),
            created_at=datetime.now(timezone.utc),
        )
        session.add(exp)
        session.commit()
        session.refresh(exp)
        return exp
    finally:
        session.close()


def get_travel_expenses(
    year: int,
    month: int,
    worker_id: int | None = None,
) -> list[dict]:
    """Fetch travel expenses for a given month."""
    session = get_session()
    try:
        q = (
            session.query(WorkerExpense, Worker.name, Worker.work_type, Worker.worker_code)
            .join(Worker, WorkerExpense.worker_id == Worker.id)
            .filter(
                extract("year", WorkerExpense.expense_date) == year,
                extract("month", WorkerExpense.expense_date) == month,
            )
        )
        if worker_id:
            q = q.filter(WorkerExpense.worker_id == worker_id)
        rows = q.order_by(desc(WorkerExpense.expense_date), desc(WorkerExpense.id)).all()
        return [
            {
                "id": exp.id,
                "worker_id": exp.worker_id,
                "worker_code": code,
                "worker_name": name,
                "work_type": wtype,
                "date": exp.expense_date,
                "amount": float(exp.amount or 0),
                "category": exp.category,
                "notes": exp.notes or "",
            }
            for exp, name, wtype, code in rows
        ]
    finally:
        session.close()


def delete_travel_expense(expense_id: int) -> bool:
    """Delete a travel expense entry."""
    session = get_session()
    try:
        exp = session.query(WorkerExpense).filter(WorkerExpense.id == expense_id).first()
        if not exp:
            return False
        session.delete(exp)
        session.commit()
        return True
    finally:
        session.close()


# ===========================================================================
# 4. Other Payments & Adjustments (Additions vs Deductions)
# ===========================================================================

def record_adjustment(
    worker_id: int,
    adjustment_date: date,
    amount: float | Decimal,
    adjustment_type: str = "ADDITION",
    category: str = "Bonus",
    notes: str = "",
) -> WorkerAdjustment:
    """Record positive addition (Bonus/Food) or deduction (Penalty)."""
    amt_dec = _dec(amount)
    if amt_dec <= Decimal("0.00"):
        raise ValueError("Adjustment amount must be greater than 0.")

    adj_clean = (adjustment_type or "ADDITION").upper().strip()
    if adj_clean not in ("ADDITION", "DEDUCTION"):
        raise ValueError("Adjustment type must be either 'ADDITION' or 'DEDUCTION'.")

    session = get_session()
    try:
        adj = WorkerAdjustment(
            worker_id=worker_id,
            adjustment_date=adjustment_date,
            amount=amt_dec,
            adjustment_type=adj_clean,
            category=(category or "Bonus").strip(),
            notes=(notes or "").strip(),
            created_at=datetime.now(timezone.utc),
        )
        session.add(adj)
        session.commit()
        session.refresh(adj)
        return adj
    finally:
        session.close()


def get_adjustments(
    year: int,
    month: int,
    worker_id: int | None = None,
    adjustment_type: str | None = None,
) -> list[dict]:
    """Fetch adjustments for a given month."""
    session = get_session()
    try:
        q = (
            session.query(WorkerAdjustment, Worker.name, Worker.work_type, Worker.worker_code)
            .join(Worker, WorkerAdjustment.worker_id == Worker.id)
            .filter(
                extract("year", WorkerAdjustment.adjustment_date) == year,
                extract("month", WorkerAdjustment.adjustment_date) == month,
            )
        )
        if worker_id:
            q = q.filter(WorkerAdjustment.worker_id == worker_id)
        if adjustment_type:
            q = q.filter(WorkerAdjustment.adjustment_type == adjustment_type.upper())
        rows = q.order_by(desc(WorkerAdjustment.adjustment_date), desc(WorkerAdjustment.id)).all()
        return [
            {
                "id": a.id,
                "worker_id": a.worker_id,
                "worker_code": code,
                "worker_name": name,
                "work_type": wtype,
                "date": a.adjustment_date,
                "amount": float(a.amount or 0),
                "type": a.adjustment_type,
                "category": a.category,
                "notes": a.notes or "",
            }
            for a, name, wtype, code in rows
        ]
    finally:
        session.close()


def delete_adjustment(adjustment_id: int) -> bool:
    """Delete an adjustment entry."""
    session = get_session()
    try:
        adj = session.query(WorkerAdjustment).filter(WorkerAdjustment.id == adjustment_id).first()
        if not adj:
            return False
        session.delete(adj)
        session.commit()
        return True
    finally:
        session.close()


# ===========================================================================
# 5. Advance Payments
# ===========================================================================

def record_advance(
    worker_id: int,
    advance_date: date,
    amount: float | Decimal,
    payment_method: str = "Cash",
    notes: str = "",
) -> WorkerAdvance:
    """Record an advance payment given to a worker."""
    amt_dec = _dec(amount)
    if amt_dec <= Decimal("0.00"):
        raise ValueError("Advance amount must be greater than 0.")

    session = get_session()
    try:
        adv = WorkerAdvance(
            worker_id=worker_id,
            advance_date=advance_date,
            amount=amt_dec,
            payment_method=(payment_method or "Cash").strip(),
            notes=(notes or "").strip(),
            created_at=datetime.now(timezone.utc),
        )
        session.add(adv)
        session.commit()
        session.refresh(adv)
        return adv
    finally:
        session.close()


def get_advances(
    year: int,
    month: int,
    worker_id: int | None = None,
) -> list[dict]:
    """Fetch advance payments for a given month."""
    session = get_session()
    try:
        q = (
            session.query(WorkerAdvance, Worker.name, Worker.work_type, Worker.worker_code)
            .join(Worker, WorkerAdvance.worker_id == Worker.id)
            .filter(
                extract("year", WorkerAdvance.advance_date) == year,
                extract("month", WorkerAdvance.advance_date) == month,
            )
        )
        if worker_id:
            q = q.filter(WorkerAdvance.worker_id == worker_id)
        rows = q.order_by(desc(WorkerAdvance.advance_date), desc(WorkerAdvance.id)).all()
        return [
            {
                "id": a.id,
                "worker_id": a.worker_id,
                "worker_code": code,
                "worker_name": name,
                "work_type": wtype,
                "date": a.advance_date,
                "amount": float(a.amount or 0),
                "payment_method": a.payment_method,
                "notes": a.notes or "",
            }
            for a, name, wtype, code in rows
        ]
    finally:
        session.close()


def delete_advance(advance_id: int) -> bool:
    """Delete an advance payment entry."""
    session = get_session()
    try:
        adv = session.query(WorkerAdvance).filter(WorkerAdvance.id == advance_id).first()
        if not adv:
            return False
        session.delete(adv)
        session.commit()
        return True
    finally:
        session.close()


# ===========================================================================
# 6. Monthly Calculation Engine
# ===========================================================================

def get_worker_monthly_summary(worker_id: int, year: int, month: int) -> dict | None:
    """Compute complete monthly summary for one worker.
    
    Calculation Model:
      total_work_earning = SUM(daily_rate * day_multiplier) [using preserved rate on each record]
      total_travel       = SUM(travel_expenses)
      total_additions    = SUM(adjustments where type == 'ADDITION')
      total_deductions   = SUM(adjustments where type == 'DEDUCTION')
      total_advance      = SUM(advances)
      gross_payable      = total_work_earning + total_travel + total_additions
      net_payable        = gross_payable - total_deductions - total_advance
      remaining_balance  = net_payable - paid_settlement_amount
    """
    month_year = f"{year:04d}-{month:02d}"
    session = get_session()
    try:
        w = session.query(Worker).filter(Worker.id == worker_id).first()
        if not w:
            return None

        # 1. Attendances
        attendances = (
            session.query(WorkerAttendance)
            .filter(
                WorkerAttendance.worker_id == worker_id,
                extract("year", WorkerAttendance.attendance_date) == year,
                extract("month", WorkerAttendance.attendance_date) == month,
            )
            .order_by(WorkerAttendance.attendance_date.asc())
            .all()
        )

        full_days = 0
        half_days = 0
        one_and_half_days = 0
        double_days = 0
        absent_days = 0
        custom_days = 0

        total_units = Decimal("0.0")
        total_work_earning = Decimal("0.00")

        for a in attendances:
            mult = _dec(a.day_multiplier)
            total_units += mult
            total_work_earning += _dec(a.daily_earning)

            if mult == Decimal("1.0"):
                full_days += 1
            elif mult == Decimal("0.5"):
                half_days += 1
            elif mult == Decimal("1.5"):
                one_and_half_days += 1
            elif mult == Decimal("2.0"):
                double_days += 1
            elif mult == Decimal("0.0"):
                absent_days += 1
            else:
                custom_days += 1

        # 2. Travel Expenses
        expenses = (
            session.query(WorkerExpense)
            .filter(
                WorkerExpense.worker_id == worker_id,
                extract("year", WorkerExpense.expense_date) == year,
                extract("month", WorkerExpense.expense_date) == month,
            )
            .order_by(WorkerExpense.expense_date.asc())
            .all()
        )
        total_travel = sum((_dec(e.amount) for e in expenses), Decimal("0.00"))

        # 3. Adjustments (Additions vs Deductions)
        adjustments = (
            session.query(WorkerAdjustment)
            .filter(
                WorkerAdjustment.worker_id == worker_id,
                extract("year", WorkerAdjustment.adjustment_date) == year,
                extract("month", WorkerAdjustment.adjustment_date) == month,
            )
            .order_by(WorkerAdjustment.adjustment_date.asc())
            .all()
        )
        total_additions = sum(
            (_dec(adj.amount) for adj in adjustments if adj.adjustment_type == "ADDITION"),
            Decimal("0.00"),
        )
        total_deductions = sum(
            (_dec(adj.amount) for adj in adjustments if adj.adjustment_type == "DEDUCTION"),
            Decimal("0.00"),
        )

        # 4. Advances
        advances = (
            session.query(WorkerAdvance)
            .filter(
                WorkerAdvance.worker_id == worker_id,
                extract("year", WorkerAdvance.advance_date) == year,
                extract("month", WorkerAdvance.advance_date) == month,
            )
            .order_by(WorkerAdvance.advance_date.asc())
            .all()
        )
        total_advance = sum((_dec(a.amount) for a in advances), Decimal("0.00"))

        # 5. Core Formulas
        gross_payable = _quant(total_work_earning + total_travel + total_additions)
        net_payable = _quant(gross_payable - total_deductions - total_advance)

        # 6. Settlement status
        settlement = (
            session.query(WorkerSettlement)
            .filter(
                WorkerSettlement.worker_id == worker_id,
                WorkerSettlement.month_year == month_year,
            )
            .first()
        )

        paid_amount = _dec(settlement.paid_amount) if settlement else Decimal("0.00")
        is_settled = bool(settlement.is_settled) if settlement else False
        remaining_balance = _quant(net_payable - paid_amount)

        # Most recent settlement cutoff date across all history for this worker
        last_settled_row = (
            session.query(func.coalesce(WorkerSettlement.end_date, WorkerSettlement.payment_date))
            .filter(
                WorkerSettlement.worker_id == worker_id,
                WorkerSettlement.is_settled.is_(True),
            )
            .order_by(desc(func.coalesce(WorkerSettlement.end_date, WorkerSettlement.payment_date)))
            .first()
        )
        last_settled_date = last_settled_row[0] if last_settled_row and last_settled_row[0] else None

        return {
            "worker_id": w.id,
            "worker_code": w.worker_code,
            "name": w.name,
            "mobile": w.mobile or "",
            "work_type": w.work_type or "Mistri",
            "current_daily_rate": float(w.daily_rate or 0),
            "is_active": bool(w.is_active),
            "year": year,
            "month": month,
            "month_name": calendar.month_name[month],
            "month_year": month_year,
            # Attendance Counts
            "total_units": float(total_units),
            "full_days": full_days,
            "half_days": half_days,
            "one_and_half_days": one_and_half_days,
            "double_days": double_days,
            "absent_days": absent_days,
            "custom_days": custom_days,
            # Financials
            "total_work_earning": float(total_work_earning),
            "total_travel": float(total_travel),
            "total_additions": float(total_additions),
            "gross_payable": float(gross_payable),
            "total_advance": float(total_advance),
            "total_deductions": float(total_deductions),
            "net_payable": float(net_payable),
            "paid_amount": float(paid_amount),
            "remaining_balance": float(remaining_balance),
            "is_settled": is_settled,
            "voucher_no": settlement.voucher_no if settlement else "",
            "start_date": settlement.start_date if settlement else None,
            "end_date": settlement.end_date if settlement else None,
            "payment_date": settlement.payment_date if settlement else None,
            "payment_date_str": settlement.payment_date.strftime("%d %b %Y") if settlement and settlement.payment_date else "",
            "payment_method": settlement.payment_method if settlement else "",
            "settlement_notes": settlement.notes if settlement else "",
            "last_settled_date": last_settled_date,
            "last_settled_date_str": last_settled_date.strftime("%d %b %Y") if last_settled_date else "",
            # Itemized lists
            "attendances": [
                {
                    "date": a.attendance_date,
                    "date_str": a.attendance_date.strftime("%d %b"),
                    "day_name": a.attendance_date.strftime("%a"),
                    "status_label": a.status_label,
                    "day_multiplier": float(a.day_multiplier),
                    "daily_rate": float(a.daily_rate),
                    "daily_earning": float(a.daily_earning if a.daily_earning is not None else ((a.daily_rate or 0) * (a.day_multiplier or 0))),
                    "is_settled": bool(last_settled_date and a.attendance_date <= last_settled_date),
                    "notes": a.notes or "",
                }
                for a in attendances
            ],
            "travel_expenses": [
                {
                    "id": e.id,
                    "date": e.expense_date,
                    "date_str": e.expense_date.strftime("%d %b %Y"),
                    "amount": float(e.amount),
                    "category": e.category,
                    "is_settled": bool(last_settled_date and e.expense_date <= last_settled_date),
                    "notes": e.notes or "",
                }
                for e in expenses
            ],
            "adjustments": [
                {
                    "id": adj.id,
                    "date": adj.adjustment_date,
                    "date_str": adj.adjustment_date.strftime("%d %b %Y"),
                    "amount": float(adj.amount),
                    "type": adj.adjustment_type,
                    "category": adj.category,
                    "is_settled": bool(last_settled_date and adj.adjustment_date <= last_settled_date),
                    "notes": adj.notes or "",
                }
                for adj in adjustments
            ],
            "advances": [
                {
                    "id": adv.id,
                    "date": adv.advance_date,
                    "date_str": adv.advance_date.strftime("%d %b %Y"),
                    "amount": float(adv.amount),
                    "payment_method": adv.payment_method,
                    "is_settled": bool(last_settled_date and adv.advance_date <= last_settled_date),
                    "notes": adv.notes or "",
                }
                for adv in advances
            ],
        }
    finally:
        session.close()


def get_all_workers_monthly_summary(
    year: int,
    month: int,
    search_query: str = "",
    work_type: str | None = None,
    is_active: bool | None = None,
) -> list[dict]:
    """Retrieve monthly summaries for all matching workers."""
    workers = get_workers(search_query=search_query, work_type=work_type, is_active=is_active)
    results = []
    for w in workers:
        summary = get_worker_monthly_summary(w.id, year, month)
        if summary:
            results.append(summary)
    return results


# ===========================================================================
# 7. Settlement & Payment Done Management
# ===========================================================================

def get_worker_last_settled_date(worker_id: int) -> date | None:
    """Find the most recent settlement cutoff date (end_date or payment_date) for this worker."""
    session = get_session()
    try:
        res = (
            session.query(func.coalesce(WorkerSettlement.end_date, WorkerSettlement.payment_date))
            .filter(
                WorkerSettlement.worker_id == worker_id,
                WorkerSettlement.is_settled.is_(True),
            )
            .order_by(desc(func.coalesce(WorkerSettlement.end_date, WorkerSettlement.payment_date)))
            .first()
        )
        return res[0] if res and res[0] else None
    finally:
        session.close()


def get_worker_active_cycle(worker_id: int, up_to_date: date | None = None) -> dict:
    """Calculate active unsettled work days, earnings, advances, and net due since last settlement."""
    if up_to_date is None:
        up_to_date = date.today()

    session = get_session()
    try:
        w = session.query(Worker).filter(Worker.id == worker_id).first()
        if not w:
            raise ValueError(f"Worker {worker_id} not found.")

        last_settled = get_worker_last_settled_date(worker_id)
        if last_settled:
            start_date = last_settled + timedelta(days=1)
        else:
            first_att = session.query(func.min(WorkerAttendance.attendance_date)).filter(WorkerAttendance.worker_id == worker_id).scalar()
            first_adv = session.query(func.min(WorkerAdvance.advance_date)).filter(WorkerAdvance.worker_id == worker_id).scalar()
            candidates = [d for d in (first_att, first_adv, w.joining_date, date(up_to_date.year, up_to_date.month, 1)) if d is not None]
            start_date = min(candidates) if candidates else date(up_to_date.year, up_to_date.month, 1)

        # Query attendances in active cycle [start_date, up_to_date]
        attendances = (
            session.query(WorkerAttendance)
            .filter(
                WorkerAttendance.worker_id == worker_id,
                WorkerAttendance.attendance_date >= start_date,
                WorkerAttendance.attendance_date <= up_to_date,
            )
            .order_by(WorkerAttendance.attendance_date.asc())
            .all()
        )

        total_units = Decimal("0.0")
        total_work_earning = Decimal("0.0")
        for a in attendances:
            total_units += _dec(a.day_multiplier)
            total_work_earning += _dec(a.daily_earning)

        # Query expenses
        expenses = (
            session.query(WorkerExpense)
            .filter(
                WorkerExpense.worker_id == worker_id,
                WorkerExpense.expense_date >= start_date,
                WorkerExpense.expense_date <= up_to_date,
            )
            .all()
        )
        total_travel = sum((_dec(e.amount) for e in expenses), Decimal("0.0"))

        # Query adjustments
        adjustments = (
            session.query(WorkerAdjustment)
            .filter(
                WorkerAdjustment.worker_id == worker_id,
                WorkerAdjustment.adjustment_date >= start_date,
                WorkerAdjustment.adjustment_date <= up_to_date,
            )
            .all()
        )
        total_additions = sum((_dec(adj.amount) for adj in adjustments if adj.adjustment_type == "ADDITION"), Decimal("0.0"))
        total_other_deductions = sum((_dec(adj.amount) for adj in adjustments if adj.adjustment_type == "DEDUCTION"), Decimal("0.0"))

        # Query advances
        advances = (
            session.query(WorkerAdvance)
            .filter(
                WorkerAdvance.worker_id == worker_id,
                WorkerAdvance.advance_date >= start_date,
                WorkerAdvance.advance_date <= up_to_date,
            )
            .all()
        )
        total_advances = sum((_dec(adv.amount) for adv in advances), Decimal("0.0"))

        gross_payable = total_work_earning + total_travel + total_additions
        total_deductions = total_advances + total_other_deductions
        net_payable = _quant(gross_payable - total_deductions)

        return {
            "worker_id": w.id,
            "worker_code": w.worker_code,
            "worker_name": w.name,
            "work_type": w.work_type,
            "daily_rate": float(w.daily_rate or 0),
            "last_settled_date": last_settled,
            "last_settled_date_str": last_settled.strftime("%d %b %Y") if last_settled else "None (Fresh)",
            "start_date": start_date,
            "start_date_str": start_date.strftime("%d %b %Y"),
            "end_date": up_to_date,
            "end_date_str": up_to_date.strftime("%d %b %Y"),
            "total_units": float(total_units),
            "work_earnings": float(_quant(total_work_earning)),
            "total_work_earning": float(_quant(total_work_earning)),
            "total_travel": float(_quant(total_travel)),
            "total_additions": float(_quant(total_additions)),
            "gross_payable": float(_quant(gross_payable)),
            "total_advances": float(_quant(total_advances)),
            "total_deductions": float(_quant(total_deductions)),
            "net_payable": float(net_payable),
            "num_attendance_days": len(attendances),
            "num_advances": len(advances),
            "num_expenses": len(expenses),
        }
    finally:
        session.close()


def record_full_payment_done(
    worker_id: int,
    end_date: date,
    paid_amount: float | Decimal,
    payment_method: str = "Cash",
    notes: str = "",
    start_date: date | None = None,
) -> WorkerSettlement:
    """Confirm full payment done for a period, locking the batch and resetting active cycle."""
    session = get_session()
    try:
        w = session.query(Worker).filter(Worker.id == worker_id).first()
        if not w:
            raise ValueError(f"Worker {worker_id} not found.")

        last_settled = get_worker_last_settled_date(worker_id)
        if start_date is None:
            if last_settled:
                start_date = last_settled + timedelta(days=1)
            else:
                start_date = w.joining_date or date(end_date.year, end_date.month, 1)

        active_data = get_worker_active_cycle(worker_id, up_to_date=end_date)
        total_settlements = session.query(func.count(WorkerSettlement.id)).scalar() or 0
        voucher_no = f"PAY-{end_date.year}-{(total_settlements + 1):04d}"

        month_year = f"{end_date.year:04d}-{end_date.month:02d}"
        paid_dec = _dec(paid_amount)

        settlement = WorkerSettlement(
            worker_id=worker_id,
            month_year=month_year,
            voucher_no=voucher_no,
            start_date=start_date,
            end_date=end_date,
            total_units=_dec(active_data["total_units"]),
            total_work_earning=_dec(active_data["work_earnings"]),
            total_travel=_dec(active_data["total_travel"]),
            total_additions=_dec(active_data["total_additions"]),
            gross_payable=_dec(active_data["gross_payable"]),
            total_advances=_dec(active_data["total_advances"]),
            total_deductions=_dec(active_data["total_deductions"]),
            net_payable=_dec(active_data["net_payable"]),
            paid_amount=paid_dec,
            payment_date=date.today(),
            payment_method=payment_method,
            is_settled=True,
            notes=(notes or "").strip(),
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        session.add(settlement)
        session.commit()
        session.refresh(settlement)
        return settlement
    finally:
        session.close()


def record_settlement(
    worker_id: int,
    year: int,
    month: int,
    paid_amount: float | Decimal,
    payment_method: str = "Cash",
    notes: str = "",
    start_date: date | None = None,
    end_date: date | None = None,
) -> WorkerSettlement:
    """Record final payment / settlement for a month without destroying historical records."""
    summary = get_worker_monthly_summary(worker_id, year, month)
    if not summary:
        raise ValueError(f"Worker {worker_id} not found.")

    paid_dec = _dec(paid_amount)
    month_year = f"{year:04d}-{month:02d}"

    if start_date is None:
        start_date = date(year, month, 1)
    if end_date is None:
        last_day = calendar.monthrange(year, month)[1]
        today = date.today()
        if today.year == year and today.month == month:
            end_date = today
        else:
            end_date = date(year, month, last_day)

    session = get_session()
    try:
        settlement = (
            session.query(WorkerSettlement)
            .filter(
                WorkerSettlement.worker_id == worker_id,
                WorkerSettlement.month_year == month_year,
            )
            .first()
        )

        total_settlements = session.query(func.count(WorkerSettlement.id)).scalar() or 0
        voucher_no = f"PAY-{year}-{(total_settlements + 1):04d}"

        if settlement:
            settlement.total_units = _dec(summary["total_units"])
            settlement.total_work_earning = _dec(summary["total_work_earning"])
            settlement.total_travel = _dec(summary["total_travel"])
            settlement.total_additions = _dec(summary["total_additions"])
            settlement.gross_payable = _dec(summary["gross_payable"])
            settlement.total_advances = _dec(summary["total_advance"])
            settlement.total_deductions = _dec(summary["total_deductions"])
            settlement.net_payable = _dec(summary["net_payable"])
            settlement.paid_amount = paid_dec
            settlement.payment_date = date.today()
            settlement.payment_method = payment_method
            settlement.is_settled = True
            settlement.notes = (notes or "").strip()
            if not settlement.voucher_no:
                settlement.voucher_no = voucher_no
            if not settlement.start_date:
                settlement.start_date = start_date
            settlement.end_date = end_date
            settlement.updated_at = datetime.now(timezone.utc)
        else:
            settlement = WorkerSettlement(
                worker_id=worker_id,
                month_year=month_year,
                voucher_no=voucher_no,
                start_date=start_date,
                end_date=end_date,
                total_units=_dec(summary["total_units"]),
                total_work_earning=_dec(summary["total_work_earning"]),
                total_travel=_dec(summary["total_travel"]),
                total_additions=_dec(summary["total_additions"]),
                gross_payable=_dec(summary["gross_payable"]),
                total_advances=_dec(summary["total_advance"]),
                total_deductions=_dec(summary["total_deductions"]),
                net_payable=_dec(summary["net_payable"]),
                paid_amount=paid_dec,
                payment_date=date.today(),
                payment_method=payment_method,
                is_settled=True,
                notes=(notes or "").strip(),
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(settlement)

        session.commit()
        session.refresh(settlement)
        return settlement
    finally:
        session.close()


def is_month_settled(worker_id: int, year: int, month: int) -> bool:
    """Check if worker's month has been settled."""
    month_year = f"{year:04d}-{month:02d}"
    session = get_session()
    try:
        st = (
            session.query(WorkerSettlement)
            .filter(
                WorkerSettlement.worker_id == worker_id,
                WorkerSettlement.month_year == month_year,
                WorkerSettlement.is_settled.is_(True),
            )
            .first()
        )
        return st is not None
    finally:
        session.close()


def get_worker_settlement_history(worker_id: int) -> list[dict]:
    """Retrieve all recorded settlements for a worker ordered newest to oldest."""
    session = get_session()
    try:
        settlements = (
            session.query(WorkerSettlement)
            .filter(WorkerSettlement.worker_id == worker_id, WorkerSettlement.is_settled.is_(True))
            .order_by(desc(WorkerSettlement.payment_date), desc(WorkerSettlement.id))
            .all()
        )
        res = []
        for st in settlements:
            start_str = st.start_date.strftime("%d %b %y") if st.start_date else ""
            end_str = st.end_date.strftime("%d %b %y") if st.end_date else ""
            if start_str and end_str:
                period_label = f"{start_str} → {end_str}"
            else:
                parts = st.month_year.split("-") if st.month_year else ["", ""]
                if len(parts) == 2 and parts[1].isdigit():
                    m_idx = int(parts[1])
                    period_label = f"{calendar.month_name[m_idx][:3]} {parts[0]}"
                else:
                    period_label = st.month_year or "—"

            res.append({
                "id": st.id,
                "voucher_no": st.voucher_no or f"PAY-{st.id:04d}",
                "month_year": st.month_year,
                "month_label": period_label,
                "start_date": st.start_date,
                "end_date": st.end_date,
                "total_units": float(st.total_units or 0),
                "total_work_earning": float(st.total_work_earning or 0),
                "gross_payable": float(st.gross_payable or 0),
                "total_advances": float(st.total_advances or 0),
                "net_payable": float(st.net_payable or 0),
                "paid_amount": float(st.paid_amount or 0),
                "payment_date": st.payment_date,
                "payment_date_str": st.payment_date.strftime("%d %b %y") if st.payment_date else "—",
                "payment_method": st.payment_method or "Cash",
                "is_settled": bool(st.is_settled),
                "notes": st.notes or "",
            })
        return res
    finally:
        session.close()


def get_all_payment_done_records(
    worker_id: int | None = None,
    year: int | None = None,
    month: int | None = None,
    search_query: str = "",
) -> list[dict]:
    """Retrieve all confirmed payment records across workers for the Payment Done ledger."""
    session = get_session()
    try:
        q = (
            session.query(WorkerSettlement, Worker)
            .join(Worker, WorkerSettlement.worker_id == Worker.id)
            .filter(WorkerSettlement.is_settled.is_(True))
        )
        if worker_id:
            q = q.filter(WorkerSettlement.worker_id == worker_id)
        if year:
            q = q.filter(
                or_(
                    extract("year", WorkerSettlement.payment_date) == year,
                    WorkerSettlement.month_year.startswith(f"{year:04d}"),
                )
            )
        if month:
            q = q.filter(
                or_(
                    extract("month", WorkerSettlement.payment_date) == month,
                    WorkerSettlement.month_year.endswith(f"-{month:02d}"),
                )
            )
        if search_query:
            sq = f"%{search_query.strip()}%"
            q = q.filter(
                or_(
                    Worker.name.ilike(sq),
                    WorkerSettlement.voucher_no.ilike(sq),
                    WorkerSettlement.notes.ilike(sq),
                    Worker.work_type.ilike(sq),
                )
            )

        q = q.order_by(desc(WorkerSettlement.payment_date), desc(WorkerSettlement.id))
        records = q.all()

        results = []
        for st, w in records:
            start_str = st.start_date.strftime("%d %b %Y") if st.start_date else ""
            end_str = st.end_date.strftime("%d %b %Y") if st.end_date else ""
            if start_str and end_str:
                period_label = f"{start_str} → {end_str}"
            elif st.end_date:
                period_label = f"Up to {end_str}"
            else:
                parts = st.month_year.split("-") if st.month_year else ["", ""]
                if len(parts) == 2 and parts[1].isdigit():
                    m_idx = int(parts[1])
                    period_label = f"{calendar.month_name[m_idx][:3]} {parts[0]}"
                else:
                    period_label = st.month_year or "—"

            results.append({
                "id": st.id,
                "voucher_no": st.voucher_no or f"PAY-{st.id:04d}",
                "worker_id": w.id,
                "worker_name": w.name,
                "worker_code": w.worker_code,
                "work_type": w.work_type or "Mistri",
                "daily_rate": float(w.daily_rate or 0),
                "mobile": w.mobile or "—",
                "start_date": st.start_date,
                "end_date": st.end_date,
                "start_date_str": start_str,
                "end_date_str": end_str,
                "period_label": period_label,
                "total_units": float(st.total_units or 0),
                "work_earnings": float(st.total_work_earning or 0),
                "gross_payable": float(st.gross_payable or 0),
                "total_advances": float(st.total_advances or 0),
                "total_deductions": float(st.total_deductions or 0),
                "net_payable": float(st.net_payable or 0),
                "paid_amount": float(st.paid_amount or 0),
                "payment_date": st.payment_date,
                "payment_date_str": st.payment_date.strftime("%d %b %Y") if st.payment_date else "—",
                "payment_method": st.payment_method or "Cash",
                "is_settled": bool(st.is_settled),
                "notes": st.notes or "",
            })
        return results
    finally:
        session.close()


def rollback_payment_done(settlement_id: int) -> bool:
    """Delete a settlement record, reopening its days back to the active unsettled pool."""
    session = get_session()
    try:
        st = session.query(WorkerSettlement).filter(WorkerSettlement.id == settlement_id).first()
        if not st:
            return False
        session.delete(st)
        session.commit()
        return True
    finally:
        session.close()


# ===========================================================================
# 8. Dashboard Metrics Aggregator
# ===========================================================================

def get_dashboard_worker_metrics(year: int | None = None, month: int | None = None) -> dict:
    """Efficiently calculate high-level dashboard metrics."""
    if year is None or month is None:
        today = date.today()
        year = year or today.year
        month = month or today.month
    month_year = f"{year:04d}-{month:02d}"
    session = get_session()
    try:
        total_workers = session.query(func.count(Worker.id)).scalar() or 0
        active_workers = (
            session.query(func.count(Worker.id))
            .filter(Worker.is_active.is_(True))
            .scalar()
            or 0
        )

        # Monthly total work earnings across all workers
        month_work_cost = (
            session.query(func.coalesce(func.sum(WorkerAttendance.daily_earning), 0))
            .filter(
                extract("year", WorkerAttendance.attendance_date) == year,
                extract("month", WorkerAttendance.attendance_date) == month,
            )
            .scalar()
            or 0
        )

        month_travel = (
            session.query(func.coalesce(func.sum(WorkerExpense.amount), 0))
            .filter(
                extract("year", WorkerExpense.expense_date) == year,
                extract("month", WorkerExpense.expense_date) == month,
            )
            .scalar()
            or 0
        )

        month_additions = (
            session.query(func.coalesce(func.sum(WorkerAdjustment.amount), 0))
            .filter(
                extract("year", WorkerAdjustment.adjustment_date) == year,
                extract("month", WorkerAdjustment.adjustment_date) == month,
                WorkerAdjustment.adjustment_type == "ADDITION",
            )
            .scalar()
            or 0
        )

        total_gross_cost = float(month_work_cost + month_travel + month_additions)

        # Total advances
        month_advances = (
            session.query(func.coalesce(func.sum(WorkerAdvance.amount), 0))
            .filter(
                extract("year", WorkerAdvance.advance_date) == year,
                extract("month", WorkerAdvance.advance_date) == month,
            )
            .scalar()
            or 0
        )

        # Total deductions
        month_deductions = (
            session.query(func.coalesce(func.sum(WorkerAdjustment.amount), 0))
            .filter(
                extract("year", WorkerAdjustment.adjustment_date) == year,
                extract("month", WorkerAdjustment.adjustment_date) == month,
                WorkerAdjustment.adjustment_type == "DEDUCTION",
            )
            .scalar()
            or 0
        )

        # Total paid settlement
        settled_paid = (
            session.query(func.coalesce(func.sum(WorkerSettlement.paid_amount), 0))
            .filter(WorkerSettlement.month_year == month_year)
            .scalar()
            or 0
        )

        net_due = max(0.0, float(total_gross_cost - float(month_deductions) - float(month_advances) - float(settled_paid)))

        return {
            "total_workers": total_workers,
            "active_workers": active_workers,
            "month_work_cost": total_gross_cost,
            "pending_payments": net_due,
        }
    finally:
        session.close()


# ===========================================================================
# 9. WhatsApp & Report Slip Formatter
# ===========================================================================

def generate_whatsapp_summary_text(
    worker_id: int,
    year: int,
    month: int,
    business_name: str = "",
) -> str:
    """Generate crystal-clear WhatsApp message breaking down salary, expenses & advances."""
    summary = get_worker_monthly_summary(worker_id, year, month)
    if not summary:
        return ""

    shop_title = f"*{business_name}*" if business_name else "*FURNITURE WORKSHOP*"
    month_name = summary["month_name"]

    lines = [
        f"👷 {shop_title}",
        f"📋 *WORKER MONTHLY SUMMARY*",
        f"📅 *Month:* {month_name} {year}",
        f"👤 *Worker:* {summary['name']} ({summary['work_type']})",
        f"🆔 *Worker ID:* {summary['worker_code']}",
        f"💰 *Current Daily Rate:* ₹{summary['current_daily_rate']:,.2f}",
        "──────────────────────",
        "📊 *ATTENDANCE BREAKDOWN:*",
        f"• Full Days (1.0): {summary['full_days']}",
        f"• Half Days (0.5): {summary['half_days']}",
        f"• 1.5 Days: {summary['one_and_half_days']}",
        f"• Double Days (2.0): {summary['double_days']}",
        f"• Absent: {summary['absent_days']}",
    ]
    if summary["custom_days"] > 0:
        lines.append(f"• Custom Days: {summary['custom_days']}")

    lines.extend([
        f"👉 *Total Units:* {summary['total_units']:.1f} Units",
        "──────────────────────",
        "💰 *PAYMENT CALCULATION:*",
        f"• Work Earnings: ₹{summary['total_work_earning']:,.2f}",
        f"• Travel / Rickshaw: ₹{summary['total_travel']:,.2f}",
        f"• Other Additions: ₹{summary['total_additions']:,.2f}",
        f"• *Gross Payable:* ₹{summary['gross_payable']:,.2f}",
        f"• Advance Payments: -₹{summary['total_advance']:,.2f}",
        f"• Other Deductions: -₹{summary['total_deductions']:,.2f}",
        "──────────────────────",
        f"✅ *NET PAYABLE: ₹{summary['net_payable']:,.2f}*",
    ])

    if summary["is_settled"]:
        lines.append(f"💵 *Paid Amount:* ₹{summary['paid_amount']:,.2f}")
        lines.append(f"🔹 *Remaining Balance:* ₹{summary['remaining_balance']:,.2f}")

    lines.append("──────────────────────")
    lines.append("Generated via Furniture Bill Software")
    return "\n".join(lines)


def generate_payment_done_whatsapp_text(
    settlement_id: int,
    business_name: str = "",
) -> str:
    """Generate crisp WhatsApp confirmation message for a settled payment voucher."""
    session = get_session()
    try:
        st = session.query(WorkerSettlement).filter_by(id=settlement_id).first()
        if not st:
            return ""
        w = session.query(Worker).filter_by(id=st.worker_id).first()
        worker_name = w.name if w else "Worker"
        work_type = w.work_type if w else "Staff"
        worker_code = w.worker_code if w else ""

        start_str = st.start_date.strftime("%d %b %Y") if st.start_date else ""
        end_str = st.end_date.strftime("%d %b %Y") if st.end_date else ""
        if start_str and end_str:
            period_label = f"{start_str} to {end_str}"
        elif st.end_date:
            period_label = f"Up to {end_str}"
        else:
            period_label = st.month_year or "—"

        shop_title = f"*{business_name}*" if business_name else "*FURNITURE WORKSHOP*"
        p_date_str = st.payment_date.strftime("%d %b %Y") if st.payment_date else "—"

        lines = [
            f"👷 {shop_title}",
            f"🧾 *PAYMENT RECEIPT / VOUCHER*",
            f"🏷 *Voucher No:* {st.voucher_no or f'PAY-{st.id:04d}'}",
            f"👤 *Worker:* {worker_name} ({work_type})",
            f"🆔 *Worker ID:* {worker_code}",
            f"📅 *Settled Period:* {period_label}",
            f"🗓 *Payment Date:* {p_date_str}",
            f"💳 *Payment Method:* {st.payment_method or 'Cash'}",
            "──────────────────────",
            "📊 *SETTLEMENT BREAKDOWN:*",
            f"• Days Paid: {float(st.total_units or 0):.1f} Days",
            f"• Work Earnings: ₹{float(st.total_work_earning or 0):,.2f}",
        ]
        gross = float(st.gross_payable or 0)
        if gross > float(st.total_work_earning or 0):
            lines.append(f"• Gross Payable (with Travel/Bonuses): ₹{gross:,.2f}")
        adv = float(st.total_advances or 0)
        if adv > 0:
            lines.append(f"• Advances Deducted: -₹{adv:,.2f}")
        ded = float(st.total_deductions or 0)
        if ded > 0:
            lines.append(f"• Other Deductions: -₹{ded:,.2f}")

        lines.extend([
            "──────────────────────",
            f"✅ *NET PAID: ₹{float(st.paid_amount or 0):,.2f}*",
            "Status: ✓ FULLY SETTLED & PAID",
        ])
        if st.notes:
            lines.append(f"📝 *Notes:* {st.notes}")
        lines.append("──────────────────────")
        lines.append("Generated via Furniture Bill Software")
        return "\n".join(lines)
    finally:
        session.close()

