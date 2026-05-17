import sqlite3
from contextlib import contextmanager
from unittest.mock import patch

import pytest


def _connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = lambda cur, row: dict(zip([col[0] for col in cur.description], row))
    conn.executescript("""
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_fee REAL NOT NULL DEFAULT 0
        );
        CREATE TABLE cash_denomination_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            entry_type TEXT NOT NULL,
            denomination INTEGER NOT NULL,
            quantity INTEGER NOT NULL,
            float_id INTEGER,
            created_by INTEGER NOT NULL,
            note TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE activity_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            action TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id INTEGER,
            details TEXT,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
    """)
    return conn


@contextmanager
def _cursor_for(conn: sqlite3.Connection, commit: bool = False):
    cursor = conn.cursor()
    try:
        yield cursor
        if commit:
            conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()


@contextmanager
def _atomic_for(conn: sqlite3.Connection):
    conn.execute("BEGIN")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def test_calculate_change_uses_available_denominations():
    from services.vault_service import VaultService

    result = VaultService.calculate_change_from_balance(
        26_500,
        {20_000: 1, 10_000: 0, 5_000: 1, 1_000: 1, 500: 1},
    )

    assert result == {20_000: 1, 5_000: 1, 1_000: 1, 500: 1}


def test_calculate_change_raises_when_exact_change_unavailable():
    from services.vault_service import InsufficientDenominationError, VaultService

    with pytest.raises(InsufficientDenominationError):
        VaultService.calculate_change_from_balance(6_500, {5_000: 1})


def test_record_transaction_payment_updates_vault_and_payment_rows():
    from backend.database import _migrate_011, _migrate_014
    from repositories.cash_denomination_repository import CashDenominationRepository
    from services.vault_service import VaultService

    conn = _connection()
    _migrate_011(conn)
    _migrate_014(conn)
    conn.execute("INSERT INTO transactions (id, customer_fee) VALUES (1, 5000)")
    conn.commit()

    def fake_cursor(commit: bool = False):
        return _cursor_for(conn, commit=commit)

    with patch("repositories.cash_denomination_repository.get_cursor", fake_cursor), \
         patch("services.vault_service.get_cursor", fake_cursor), \
         patch("services.vault_service.atomic", lambda: _atomic_for(conn)):
        denom_repo = CashDenominationRepository()
        denom_repo.record_bulk_entry("vault_in", {5000: 1}, created_by=3)
        service = VaultService(denom_repo=denom_repo)

        result = service.record_transaction_payment(
            transaction_id=1,
            cashier_id=3,
            fee_amount=5000,
            received_denominations={"10000": 1},
        )

    assert result["change_due"] == 5000
    assert result["change_denominations"] == {"5000": 1}

    balances = {
        row["denomination_id"]: row["quantity"]
        for row in conn.execute("SELECT denomination_id, quantity FROM vault_denomination_balances")
    }
    assert balances[10000] == 1
    assert balances[5000] == 0

    rows = conn.execute(
        "SELECT denomination_id, quantity_paid, quantity_returned "
        "FROM transaction_payment_denominations ORDER BY denomination_id"
    ).fetchall()
    assert [dict(row) for row in rows] == [
        {"denomination_id": 5000, "quantity_paid": 0, "quantity_returned": 1},
        {"denomination_id": 10000, "quantity_paid": 1, "quantity_returned": 0},
    ]

    txn = conn.execute("SELECT change_given, change_denominations FROM transactions WHERE id = 1").fetchone()
    assert txn["change_given"] == 5000
    assert txn["change_denominations"] == '{"5000": 1}'
