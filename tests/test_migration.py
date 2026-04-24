"""
Migration tests for _migrate_004.

Tests run against an in-memory SQLite DB created in the pre-migration-004
state (old schema: accounts has service_id + service_type TEXT,
commission_tiers has service_type TEXT + account_type TEXT).

These tests should be RED before T019 is implemented.
"""
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _get_columns(conn, table_name: str) -> list[str]:
    """Return list of column names for a table."""
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    return [row[1] for row in cursor.fetchall()]


def _get_column_names_dict(conn, table_name: str) -> list[str]:
    """Return column names via dict row_factory."""
    cursor = conn.execute(f"PRAGMA table_info({table_name})")
    rows = cursor.fetchall()
    # row_factory may be dict or tuple depending on the connection
    if rows and isinstance(rows[0], dict):
        return [r["name"] for r in rows]
    return [r[1] for r in rows]


# ─────────────────────────────────────────────────────────────────────────────
# T005 — test_migrate_004_accounts
# ─────────────────────────────────────────────────────────────────────────────

def test_migrate_004_accounts(tmp_db):
    """
    After _migrate_004:
    - Every accounts row has a non-NULL service_type_id INTEGER.
    - service_type_id resolves to a valid row in service_types.
    - The old service_type TEXT column no longer exists.
    - The old service_id column no longer exists.
    """
    from backend.database import _migrate_004

    # Pre-check: old columns exist
    pre_cols = _get_column_names_dict(tmp_db, "accounts")
    assert "service_id" in pre_cols, "Pre-migration: service_id should exist"
    assert "service_type" in pre_cols, "Pre-migration: service_type TEXT should exist"

    _migrate_004(tmp_db)

    # Post-check: new columns
    post_cols = _get_column_names_dict(tmp_db, "accounts")
    assert "service_id" not in post_cols, "service_id should be dropped"
    assert "service_type" not in post_cols, "service_type TEXT should be dropped"
    assert "service_type_id" in post_cols, "service_type_id should exist"

    # Every account row has a non-NULL service_type_id
    rows = tmp_db.execute("SELECT id, service_type_id FROM accounts").fetchall()
    assert len(rows) > 0, "There should be at least one account row"
    for row in rows:
        if isinstance(row, dict):
            assert row["service_type_id"] is not None, (
                f"Account {row['id']} has NULL service_type_id"
            )
        else:
            assert row[1] is not None, "service_type_id should not be NULL"

    # service_type_id resolves to a valid service_types row
    st_ids = {
        r["id"] if isinstance(r, dict) else r[0]
        for r in tmp_db.execute("SELECT id FROM service_types").fetchall()
    }
    assert len(st_ids) > 0, "service_types table should have rows"

    for row in rows:
        st_id = row["service_type_id"] if isinstance(row, dict) else row[1]
        assert st_id in st_ids, (
            f"service_type_id={st_id} does not map to a valid service_types row"
        )


# ─────────────────────────────────────────────────────────────────────────────
# T006 — test_migrate_004_tiers
# ─────────────────────────────────────────────────────────────────────────────

def test_migrate_004_tiers(tmp_db):
    """
    After _migrate_004:
    - Every commission_tiers row has a non-NULL service_type_id INTEGER.
    - The old service_type TEXT column no longer exists.
    - The old account_type TEXT column no longer exists.
    """
    from backend.database import _migrate_004

    pre_cols = _get_column_names_dict(tmp_db, "commission_tiers")
    assert "service_type" in pre_cols, "Pre-migration: service_type TEXT should exist"
    assert "account_type" in pre_cols, "Pre-migration: account_type TEXT should exist"

    _migrate_004(tmp_db)

    post_cols = _get_column_names_dict(tmp_db, "commission_tiers")
    assert "service_type" not in post_cols, "service_type TEXT should be dropped"
    assert "account_type" not in post_cols, "account_type TEXT should be dropped"
    assert "service_type_id" in post_cols, "service_type_id should exist"

    rows = tmp_db.execute("SELECT id, service_type_id FROM commission_tiers").fetchall()
    assert len(rows) > 0, "commission_tiers should have rows"
    for row in rows:
        st_id = row["service_type_id"] if isinstance(row, dict) else row[1]
        assert st_id is not None, "service_type_id should not be NULL"


# ─────────────────────────────────────────────────────────────────────────────
# T007 — test_migrate_004_zero_data_loss
# ─────────────────────────────────────────────────────────────────────────────

def test_migrate_004_zero_data_loss(tmp_db):
    """
    After _migrate_004:
    - Row count in accounts matches pre-migration count.
    - Row count in commission_tiers matches pre-migration count.
    - transactions row count is unchanged.
    """
    from backend.database import _migrate_004

    pre_accounts = tmp_db.execute("SELECT COUNT(*) FROM accounts").fetchone()
    pre_tiers    = tmp_db.execute("SELECT COUNT(*) FROM commission_tiers").fetchone()
    pre_txns     = tmp_db.execute("SELECT COUNT(*) FROM transactions").fetchone()

    def _count(row):
        return row[0] if not isinstance(row, dict) else list(row.values())[0]

    pre_acc_count  = _count(pre_accounts)
    pre_tier_count = _count(pre_tiers)
    pre_txn_count  = _count(pre_txns)

    _migrate_004(tmp_db)

    post_acc_count  = _count(tmp_db.execute("SELECT COUNT(*) FROM accounts").fetchone())
    post_tier_count = _count(tmp_db.execute("SELECT COUNT(*) FROM commission_tiers").fetchone())
    post_txn_count  = _count(tmp_db.execute("SELECT COUNT(*) FROM transactions").fetchone())

    assert post_acc_count == pre_acc_count, (
        f"Account row count changed: {pre_acc_count} → {post_acc_count}"
    )
    # commission_tiers may gain new True Money tier rows (seeded in step 6)
    # but no existing rows should be deleted — post count >= pre count
    assert post_tier_count >= pre_tier_count, (
        f"commission_tiers lost rows: {pre_tier_count} → {post_tier_count}"
    )
    assert post_txn_count == pre_txn_count, (
        f"transactions row count changed: {pre_txn_count} → {post_txn_count}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# T008 — test_migrate_004_transaction_company_columns
# ─────────────────────────────────────────────────────────────────────────────

def test_migrate_004_transaction_company_columns(tmp_db):
    """
    After _migrate_004:
    - transactions has from_company_id and to_company_id columns.
    - A transfer transaction's from_company_id is non-NULL and maps to the
      correct company row (the KPAY company).
    """
    from backend.database import _migrate_004

    # Insert a user for created_by FK
    # user already seeded by conftest via _SEED_USER

    # Insert a transfer transaction referencing account_id=1 (KPAY agent)
    tmp_db.execute(
        "INSERT INTO transactions "
        "(transaction_type, account_id, to_account_id, amount, "
        " balance_change, created_by) "
        "VALUES ('transfer', 1, 4, 50000.0, -50000.0, 1)"
    )
    tmp_db.commit()

    _migrate_004(tmp_db)

    # transactions should have the new columns
    txn_cols = _get_column_names_dict(tmp_db, "transactions")
    assert "from_company_id" in txn_cols, "from_company_id column should exist"
    assert "to_company_id" in txn_cols, "to_company_id column should exist"

    # The transfer row's from_company_id should be non-NULL
    txns = tmp_db.execute(
        "SELECT from_company_id, to_company_id FROM transactions "
        "WHERE transaction_type = 'transfer'"
    ).fetchall()
    assert len(txns) > 0, "No transfer transactions found after migration"

    row = txns[0]
    fc = row["from_company_id"] if isinstance(row, dict) else row[0]
    assert fc is not None, "from_company_id should not be NULL for a transfer"

    # Verify it maps to a real company
    company = tmp_db.execute(
        "SELECT id, name FROM companies WHERE id = ?", (fc,)
    ).fetchone()
    assert company is not None, f"from_company_id={fc} not found in companies"
    company_name = company["name"] if isinstance(company, dict) else company[1]
    assert "KBZ Pay" in company_name or "KBZ" in company_name, (
        f"Expected KBZ Pay company, got: {company_name}"
    )
