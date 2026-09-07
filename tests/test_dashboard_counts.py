"""Verify dashboard_stats returns correct counts (no Cartesian product).

The previous implementation used a cross-join between Customer and Invoice,
inflating counts to customers × invoices.  This test ensures each count
matches the actual row count in its respective table.
"""
import itertools
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.models import Base, Customer, Invoice, Payment
from app.utils.cache import cache

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_inv_counter = itertools.count(1)


@pytest.fixture()
def db_session(tmp_path):
    """Yield a session against a fresh SQLite database with all tables."""
    db = tmp_path / "test_counts.db"
    engine = create_engine(f"sqlite:///{db}", echo=False)
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = Session()

    # Monkey-patch get_session so dashboard_service uses our test DB
    import app.database.database as db_mod
    orig = db_mod._SessionLocal
    db_mod._SessionLocal = Session

    # Clear the global cache so stale data isn't returned
    cache.clear()

    yield session

    # Restore
    db_mod._SessionLocal = orig
    cache.clear()
    session.close()
    engine.dispose()


def _add_customer(session, name):
    c = Customer(name=name, mobile="9000000000")
    session.add(c)
    session.flush()
    return c


def _add_invoice(session, customer_id, status="SAVED", grand_total=1000.0):
    seq = next(_inv_counter)
    inv = Invoice(
        invoice_number=f"INV-{seq:04d}",
        customer_id=customer_id,
        invoice_date=datetime.now(tz=timezone.utc).date(),
        status=status,
        grand_total=grand_total,
        subtotal=grand_total,
        amount_in_words="test",
    )
    session.add(inv)
    session.flush()
    return inv


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestDashboardCounts:
    """dashboard_stats must return exact table row counts."""

    def test_customer_count_exact(self, db_session):
        """With 3 customers, total_customers must be 3 (not 3 * n_invoices)."""
        c1 = _add_customer(db_session, "Alpha")
        c2 = _add_customer(db_session, "Beta")
        c3 = _add_customer(db_session, "Gamma")
        _add_invoice(db_session, c1.id)
        _add_invoice(db_session, c2.id)
        _add_invoice(db_session, c3.id)
        _add_invoice(db_session, c1.id, grand_total=500)
        db_session.commit()
        cache.clear()

        from app.services.dashboard_service import dashboard_stats
        stats = dashboard_stats()

        assert stats["total_customers"] == 3, (
            f"Expected 3 customers, got {stats['total_customers']}"
        )

    def test_invoice_count_exact(self, db_session):
        """With 5 invoices, total_invoices must be 5 (not 5 * n_customers)."""
        c1 = _add_customer(db_session, "Cust1")
        c2 = _add_customer(db_session, "Cust2")
        for i in range(5):
            _add_invoice(db_session, c1.id if i < 3 else c2.id)
        db_session.commit()
        cache.clear()

        from app.services.dashboard_service import dashboard_stats
        stats = dashboard_stats()

        assert stats["total_invoices"] == 5, (
            f"Expected 5 invoices, got {stats['total_invoices']}"
        )

    def test_counts_not_cross_multiplied(self, db_session):
        """4 customers x 6 invoices should NOT yield 24 for either count."""
        customers = [_add_customer(db_session, f"C{i}") for i in range(4)]
        for i in range(6):
            _add_invoice(db_session, customers[i % 4].id)
        db_session.commit()
        cache.clear()

        from app.services.dashboard_service import dashboard_stats
        stats = dashboard_stats()

        # The old cross-join bug would return 24 (4 x 6) for BOTH counts
        assert stats["total_customers"] == 4, (
            f"Expected 4, got {stats['total_customers']} (Cartesian product?)"
        )
        assert stats["total_invoices"] == 6, (
            f"Expected 6, got {stats['total_invoices']} (Cartesian product?)"
        )

    def test_zero_data(self, db_session):
        """Empty database must return 0 for both counts."""
        from app.services.dashboard_service import dashboard_stats
        stats = dashboard_stats()

        assert stats["total_customers"] == 0
        assert stats["total_invoices"] == 0

    def test_single_customer_many_invoices(self, db_session):
        """1 customer with 10 invoices: counts must be 1 and 10."""
        c = _add_customer(db_session, "Solo")
        for i in range(10):
            _add_invoice(db_session, c.id, grand_total=100 * (i + 1))
        db_session.commit()
        cache.clear()

        from app.services.dashboard_service import dashboard_stats
        stats = dashboard_stats()

        assert stats["total_customers"] == 1
        assert stats["total_invoices"] == 10

    def test_many_customers_single_invoice(self, db_session):
        """8 customers with 1 invoice: counts must be 8 and 1."""
        for i in range(8):
            _add_customer(db_session, f"Cust{i}")
        db_session.commit()

        customers = db_session.query(Customer).all()
        _add_invoice(db_session, customers[0].id)
        db_session.commit()
        cache.clear()

        from app.services.dashboard_service import dashboard_stats
        stats = dashboard_stats()

        assert stats["total_customers"] == 8
        assert stats["total_invoices"] == 1

    def test_paid_pending_counts(self, db_session):
        """Paid and pending invoice counts should be correct."""
        c = _add_customer(db_session, "TestCust")
        inv1 = _add_invoice(db_session, c.id, grand_total=1000)
        _add_invoice(db_session, c.id, grand_total=2000)
        db_session.commit()

        # Pay inv1 fully
        payment = Payment(invoice_id=inv1.id, amount=1000, date=datetime.now(tz=timezone.utc).date(), mode="Cash")
        db_session.add(payment)
        db_session.commit()
        cache.clear()

        from app.services.dashboard_service import dashboard_stats
        stats = dashboard_stats()

        assert stats["paid_invoices"] == 1
        assert stats["pending_invoices"] == 1

    def test_total_income_from_payments(self, db_session):
        """total_income should equal the sum of all payments."""
        c = _add_customer(db_session, "IncomeTest")
        inv1 = _add_invoice(db_session, c.id, grand_total=5000)
        inv2 = _add_invoice(db_session, c.id, grand_total=3000)
        db_session.add(Payment(invoice_id=inv1.id, amount=2000, date=datetime.now(tz=timezone.utc).date(), mode="Cash"))
        db_session.add(Payment(invoice_id=inv2.id, amount=1500, date=datetime.now(tz=timezone.utc).date(), mode="UPI"))
        db_session.commit()
        cache.clear()

        from app.services.dashboard_service import dashboard_stats
        stats = dashboard_stats()

        assert stats["total_income"] == 3500.0, (
            f"Expected 3500.0, got {stats['total_income']}"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
