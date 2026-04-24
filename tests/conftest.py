"""
Shared pytest fixtures for Ngwe Lwe System tests.

Provides:
  - tmp_db:    fresh in-memory SQLite, full schema (pre-migration_004 state)
  - seeded_db: tmp_db extended with _migrate_004 seed data
  - test_client: FastAPI TestClient wrapping the app with test DB injected
  - auth_headers: Bearer token header for owner route tests
"""
import sqlite3
import sys
import os
from pathlib import Path

import pytest

# Ensure project root is on sys.path so backend, models, etc. are importable
ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ---------------------------------------------------------------------------
# Pre-migration-004 schema (what exists on disk before the migration runs)
# This mirrors the current database.sql minus the new tables/columns.
# ---------------------------------------------------------------------------
_PRE_MIGRATION_DDL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT (datetime('now')),
    description TEXT
);

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    pin_hash      TEXT,
    full_name     TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'employee'
                  CHECK(role IN ('owner','employee','cashier')),
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS services (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    name                 TEXT NOT NULL UNIQUE,
    service_type         TEXT NOT NULL,
    default_customer_fee REAL NOT NULL DEFAULT 0.00,
    is_active            INTEGER NOT NULL DEFAULT 1,
    created_at           TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at           TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS accounts (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    service_id      INTEGER NOT NULL,
    account_name    TEXT NOT NULL,
    account_type    TEXT NOT NULL DEFAULT 'personal'
                    CHECK(account_type IN ('personal','agent')),
    phone_number    TEXT NOT NULL,
    service_type    TEXT NOT NULL DEFAULT 'KPAY'
                    CHECK(service_type IN ('KPAY','WAVE','BANK')),
    balance         REAL NOT NULL DEFAULT 0.00,
    commission_rate REAL NOT NULL DEFAULT 0.0000,
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (service_id) REFERENCES services(id)
);

CREATE TABLE IF NOT EXISTS transactions (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    transaction_type      TEXT NOT NULL
                          CHECK(transaction_type IN ('deposit','withdraw','transfer','exchange')),
    account_id            INTEGER NOT NULL,
    to_account_id         INTEGER,
    customer_name         TEXT,
    customer_phone        TEXT,
    amount                REAL NOT NULL,
    commission_amount     REAL NOT NULL DEFAULT 0.00,
    customer_fee          REAL NOT NULL DEFAULT 0.00,
    additional_fee_amount REAL NOT NULL DEFAULT 0.00,
    balance_change        REAL NOT NULL DEFAULT 0.00,
    currency              TEXT NOT NULL DEFAULT 'MMK',
    exchange_rate         REAL,
    fee_account_id        INTEGER,
    screenshot_path       TEXT,
    note                  TEXT,
    created_by            INTEGER NOT NULL,
    created_at            TEXT NOT NULL DEFAULT (datetime('now')),
    cash_approved_by      INTEGER,
    cash_approved_at      TEXT,
    FOREIGN KEY (account_id) REFERENCES accounts(id),
    FOREIGN KEY (created_by) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS commission_tiers (
    id                             INTEGER PRIMARY KEY AUTOINCREMENT,
    service_type                   TEXT NOT NULL,
    account_type                   TEXT CHECK(account_type IN ('personal','agent')),
    amount_from                    REAL,
    amount_to                      REAL,
    fee_amount_type                TEXT NOT NULL DEFAULT 'FIXED'
                                   CHECK(fee_amount_type IN ('FIXED','PERCENTAGE')),
    fee_amount_deposit             REAL NOT NULL DEFAULT 0.0,
    fee_amount_withdraw            REAL NOT NULL DEFAULT 0.0,
    comm_type                      TEXT NOT NULL DEFAULT 'FIXED'
                                   CHECK(comm_type IN ('FIXED','PERCENTAGE')),
    comm_deposit                   REAL NOT NULL DEFAULT 0.0,
    comm_withdraw                  REAL NOT NULL DEFAULT 0.0,
    additional_fee_type            TEXT NOT NULL DEFAULT 'FIXED'
                                   CHECK(additional_fee_type IN ('FIXED','PERCENTAGE')),
    additional_fee_deposit_amount  REAL NOT NULL DEFAULT 0.0,
    additional_fee_withdraw_amount REAL NOT NULL DEFAULT 0.0,
    is_active                      INTEGER NOT NULL DEFAULT 1,
    created_at                     TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

_SEED_SERVICES = """
INSERT OR IGNORE INTO services (id, name, service_type, default_customer_fee) VALUES
(1, 'KBZ Pay',   'KPAY', 0),
(2, 'Wave Pay',  'WAVE', 0),
(3, 'KBZ Bank',  'BANK', 0);
"""

_SEED_ACCOUNTS = """
INSERT OR IGNORE INTO accounts
    (id, service_id, account_name, account_type, phone_number, service_type, balance, commission_rate)
VALUES
(1, 1, 'KBZ Agent Account',    'agent',    '09100000001', 'KPAY', 100000.0, 0.0),
(2, 2, 'Wave Agent Account',   'agent',    '09100000002', 'WAVE', 200000.0, 0.0),
(3, 2, 'Wave Personal Acc',    'personal', '09100000003', 'WAVE', 50000.0,  0.0),
(4, 3, 'KBZ Bank Account',     'agent',    '09100000004', 'BANK', 300000.0, 0.0);
"""

_SEED_COMMISSION_TIERS = """
INSERT OR IGNORE INTO commission_tiers
    (service_type, account_type, amount_from, amount_to,
     comm_deposit, comm_withdraw)
VALUES
('KPAY_WST',            'agent',    NULL, NULL, 500.0, 500.0),
('WAVE_WST',            'agent',    NULL, NULL, 400.0, 400.0),
('WAVE_ACCOUNT',        'personal', NULL, NULL, 300.0, 300.0),
('TRUE_MONEY_WST',      'agent',    NULL, NULL, 500.0, 500.0),
('TRUE_MONEY_PAY_TO_PAY','personal',NULL, NULL, 300.0, 300.0);
"""

_SEED_USER = """
INSERT OR IGNORE INTO users (id, username, password_hash, full_name, role)
VALUES (1, 'owner', '$2b$12$fake', 'Test Owner', 'owner');
"""


def _make_connection(path: str = ":memory:") -> sqlite3.Connection:
    """Create a SQLite connection with dict row_factory and FK enforcement."""
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = lambda cur, row: dict(
        zip([col[0] for col in cur.description], row)
    )
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def make_db_patch(conn):
    """
    Return a context manager that patches get_cursor in all repository modules
    to use the provided sqlite3.Connection instead of the real DB file.

    Repositories that do module-level `from backend.database import get_cursor`
    must be patched at their own namespace. BaseRepository uses lazy imports
    inside method bodies, so patching `backend.database.get_cursor` covers those.
    """
    from contextlib import contextmanager, ExitStack
    from unittest.mock import patch

    @contextmanager
    def _fake_cursor(commit: bool = False):
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

    _PATCH_TARGETS = [
        "backend.database.get_cursor",
        "repositories.company_repository.get_cursor",
        "repositories.service_type_repository.get_cursor",
        "repositories.account_repository.get_cursor",
        "repositories.commission_tier_repository.get_cursor",
        "repositories.transaction_repository.get_cursor",
        "repositories.exchange_rate_repository.get_cursor",
        "repositories.user_repository.get_cursor",
    ]

    @contextmanager
    def _multi():
        with ExitStack() as stack:
            for target in _PATCH_TARGETS:
                try:
                    stack.enter_context(patch(target, _fake_cursor))
                except AttributeError:
                    pass
            yield

    return _multi()


@pytest.fixture
def tmp_db():
    """
    Fresh in-memory SQLite DB with the pre-migration-004 schema and minimal
    seed rows.  Yields the sqlite3.Connection; tears down automatically.
    """
    conn = _make_connection()
    conn.executescript(_PRE_MIGRATION_DDL)
    conn.executescript(_SEED_USER)
    conn.executescript(_SEED_SERVICES)
    conn.executescript(_SEED_ACCOUNTS)
    conn.executescript(_SEED_COMMISSION_TIERS)
    conn.commit()
    yield conn
    conn.close()


@pytest.fixture
def seeded_db(tmp_db):
    """
    Extends tmp_db by running _migrate_004 so that companies, service_types
    are present and accounts/commission_tiers use service_type_id FKs.
    """
    from backend.database import _migrate_004
    _migrate_004(tmp_db)
    yield tmp_db


@pytest.fixture
def auth_headers():
    """Bearer token header for owner route tests (stubbed value)."""
    return {"Authorization": "Bearer test-owner-token"}
