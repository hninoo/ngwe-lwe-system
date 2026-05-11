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
    from backend.database import _migrate_011
    from repositories.cash_denomination_repository import CashDenominationRepository
    from services.vault_service import VaultService

    conn = _connection()
    _migrate_011(conn)
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


def test_exchange_denomination_moves_cash_between_float_and_vault():
    from backend.database import _migrate_013
    from services.vault_service import VaultService

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = lambda cur, row: dict(zip([col[0] for col in cur.description], row))
    conn.executescript("""
        CREATE TABLE users (id INTEGER PRIMARY KEY);
        CREATE TABLE cash_float_assignments (id INTEGER PRIMARY KEY);
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
    _migrate_013(conn)

    class FloatObj:
        id = 7
        employee_id = 2
        status = "ACTIVE"

    class FloatRepo:
        def __init__(self) -> None:
            self.balance = {10000: 1, 5000: 0}

        def get_float(self, float_id):
            return FloatObj() if float_id == 7 else None

        def get_denomination_balance(self, float_id):
            return dict(self.balance)

        def deduct_denominations(self, float_id, denominations):
            for denom, qty in denominations.items():
                self.balance[denom] = self.balance.get(denom, 0) - qty

        def add_denominations(self, float_id, denominations):
            for denom, qty in denominations.items():
                self.balance[denom] = self.balance.get(denom, 0) + qty

    class DenomRepo:
        def __init__(self) -> None:
            self.vault = {10000: 0, 5000: 2}

        def get_vault_balance(self):
            return dict(self.vault)

        def record_bulk_entry(self, entry_type, denominations, created_by, float_id=None, note=None):
            sign = 1 if entry_type in ("vault_in", "float_returned", "adjustment") else -1
            for denom, qty in denominations.items():
                self.vault[denom] = self.vault.get(denom, 0) + sign * qty

    class VaultTxnRepo:
        def record_bulk(self, **kwargs):
            return None

    float_repo = FloatRepo()
    denom_repo = DenomRepo()

    def fake_cursor(commit: bool = False):
        return _cursor_for(conn, commit=commit)

    with patch("services.vault_service.get_cursor", fake_cursor), \
         patch("services.vault_service.atomic", lambda: _atomic_for(conn)):
        result = VaultService(
            float_repo=float_repo,
            denom_repo=denom_repo,
            vault_txn_repo=VaultTxnRepo(),
        ).exchange_denomination(
            float_id=7,
            employee_id=2,
            from_denominations={"10000": 1},
            to_denominations={"5000": 2},
            performed_by=3,
        )

    assert result["success"] is True
    assert result["exchange_id"] == 1
    assert float_repo.balance == {10000: 0, 5000: 2}
    assert denom_repo.vault == {10000: 1, 5000: 0}

    row = conn.execute("SELECT * FROM denomination_exchanges").fetchone()
    assert row["exchange_type"] == "BREAK_DOWN"
    assert row["given_denom"] == 10000
    assert row["given_quantity"] == 1
    assert row["total_amount"] == 10000
