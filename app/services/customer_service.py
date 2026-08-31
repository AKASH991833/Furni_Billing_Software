"""Customer management service."""
from __future__ import annotations

from sqlalchemy import or_

from app.database.database import get_session
from app.models.models import Customer, Invoice, Payment
from sqlalchemy.orm import joinedload, selectinload


def add_customer(data: dict) -> Customer:
    session = get_session()
    try:
        c = Customer(**data)
        session.add(c)
        session.commit()
        session.refresh(c)
        return c
    finally:
        session.close()


def update_customer(customer_id: int, data: dict) -> Customer:
    session = get_session()
    try:
        c = session.query(Customer).get(customer_id)
        if c:
            for k, v in data.items():
                setattr(c, k, v)
            session.commit()
        return c
    finally:
        session.close()


def delete_customer(customer_id: int) -> bool:
    session = get_session()
    try:
        c = session.query(Customer).get(customer_id)
        if c:
            session.delete(c)
            session.commit()
            return True
        return False
    finally:
        session.close()


def get_customer(customer_id: int) -> Customer | None:
    session = get_session()
    try:
        return session.query(Customer).get(customer_id)
    finally:
        session.close()


def search_customers(query: str = "", limit: int = 200) -> list[Customer]:
    session = get_session()
    try:
        q = session.query(Customer)
        if query:
            pat = f"%{query}%"
            q = q.filter(
                or_(
                    Customer.name.ilike(pat),
                    Customer.mobile.ilike(pat),
                    Customer.email.ilike(pat),
                )
            )
        return q.order_by(Customer.name).limit(limit).all()
    finally:
        session.close()


def customer_invoices(customer_id: int) -> list[Invoice]:
    session = get_session()
    try:
        return (
            session.query(Invoice)
            .filter(Invoice.customer_id == customer_id)
            .options(selectinload(Invoice.payments))
            .order_by(Invoice.invoice_date.desc())
            .all()
        )
    finally:
        session.close()


def customer_totals(customer_id: int) -> dict:
    """Total invoiced, total paid, outstanding for a customer."""
    session = get_session()
    try:
        invoices = (
            session.query(Invoice)
            .filter(Invoice.customer_id == customer_id, Invoice.status != "DRAFT")
            .options(selectinload(Invoice.payments))
            .all()
        )
        total_invoiced = sum(float(i.grand_total or 0) for i in invoices)
        total_paid = 0.0
        for i in invoices:
            for p in i.payments:
                total_paid += float(p.amount or 0)
        return {
            "total_invoiced": total_invoiced,
            "total_paid": total_paid,
            "outstanding": total_invoiced - total_paid,
            "invoice_count": len(invoices),
        }
    finally:
        session.close()


def customer_payments(customer_id: int) -> list[Payment]:
    session = get_session()
    try:
        return (
            session.query(Payment)
            .join(Invoice)
            .filter(Invoice.customer_id == customer_id)
            .options(joinedload(Payment.invoice))
            .order_by(Payment.date.desc())
            .all()
        )
    finally:
        session.close()
