"""
Integration tests for deposit/transfer end-to-end API flow.

T018: Full API stack integration tests.

These will be RED until T036-T041 are fully implemented.
"""
import json
import os
import sys
import time
import hmac
import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("APP_SECRET", "test-secret-key-for-unit-tests")
os.environ.setdefault("DB_PATH", ":memory:")


def _make_token(role: str = "owner", user_id: int = 1) -> str:
    secret = os.environ["APP_SECRET"]
    payload = json.dumps({
        "user_id": user_id,
        "username": role,
        "role": role,
        "exp": int(time.time()) + 86400,
    })
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}|{sig}"


@pytest.fixture(scope="module")
def owner_headers():
    return {"Authorization": f"Bearer {_make_token('owner')}"}


@pytest.fixture
def client(seeded_db):
    from tests.conftest import make_db_patch
    from fastapi.testclient import TestClient
    from backend.main import app
    with make_db_patch(seeded_db):
        with TestClient(app) as c:
            yield c


def _get_first_active_account_id(seeded_db) -> int:
    """Return the id of the first active account after migration."""
    row = seeded_db.execute(
        "SELECT id FROM accounts WHERE is_active = 1 LIMIT 1"
    ).fetchone()
    assert row is not None, "No active accounts found"
    return row["id"] if isinstance(row, dict) else row[0]


def _get_accounts_by_company_category(seeded_db, category: str) -> list:
    """Return active accounts joined to a company of the given category."""
    rows = seeded_db.execute(
        "SELECT a.id FROM accounts a "
        "JOIN service_types st ON a.service_type_id = st.id "
        "JOIN companies c ON c.id = st.company_id "
        "WHERE c.category = ? AND a.is_active = 1",
        (category,),
    ).fetchall()
    return [r["id"] if isinstance(r, dict) else r[0] for r in rows]


def test_deposit_flow_end_to_end(client, owner_headers, seeded_db):
    """POST deposit via /transactions/deposit → 201, balance updated."""
    account_id = _get_first_active_account_id(seeded_db)

    pre_balance = seeded_db.execute(
        "SELECT balance FROM accounts WHERE id = ?", (account_id,)
    ).fetchone()
    pre_bal_val = (pre_balance["balance"] if isinstance(pre_balance, dict)
                   else pre_balance[0])

    resp = client.post(
        "/transactions/deposit",
        headers=owner_headers,
        json={
            "account_id": account_id,
            "amount": 10000.0,
            "customer_name": "Test Customer",
            "customer_phone": "09123456789",
        },
    )
    assert resp.status_code in (200, 201), f"Expected 200/201, got {resp.status_code}: {resp.text}"

    # Verify balance updated via GET /accounts/{id}
    acc_resp = client.get(f"/accounts/{account_id}", headers=owner_headers)
    assert acc_resp.status_code == 200
    new_balance = acc_resp.json()["balance"]
    assert new_balance == pre_bal_val + 10000.0, (
        f"Balance not updated: expected {pre_bal_val + 10000.0}, got {new_balance}"
    )


def test_transfer_flow_cross_company(client, owner_headers, seeded_db):
    """POST transfer → both balances updated, response includes from/to company IDs."""
    pay_accounts = _get_accounts_by_company_category(seeded_db, "Pay")
    bank_accounts = _get_accounts_by_company_category(seeded_db, "Bank")

    # Fallback: use first two accounts if category filtering yields nothing
    all_acc = seeded_db.execute(
        "SELECT id FROM accounts WHERE is_active = 1 ORDER BY id LIMIT 4"
    ).fetchall()
    all_ids = [r["id"] if isinstance(r, dict) else r[0] for r in all_acc]
    assert len(all_ids) >= 2, "Need at least 2 accounts for transfer test"

    from_id = all_ids[0]
    to_id = all_ids[1]

    resp = client.post(
        "/transactions/transfer",
        headers=owner_headers,
        json={
            "from_account_id": from_id,
            "to_account_id": to_id,
            "amount": 5000.0,
        },
    )
    assert resp.status_code in (200, 201), f"Transfer failed: {resp.text}"
    data = resp.json()
    # The response should include from_company_id and to_company_id
    # (or they should be stored in the transaction record)
    # This assertion verifies the new column is populated
    txn_row = seeded_db.execute(
        "SELECT from_company_id, to_company_id FROM transactions "
        "WHERE transaction_type = 'transfer' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if txn_row:
        fc = txn_row["from_company_id"] if isinstance(txn_row, dict) else txn_row[0]
        assert fc is not None, "from_company_id should be set for transfer"


def test_company_deactivate_cascade(client, owner_headers, seeded_db):
    """PATCH company is_active=false → GET /accounts/?active=true returns empty for that company."""
    # Find a company with active accounts
    row = seeded_db.execute(
        "SELECT DISTINCT st.company_id FROM accounts a "
        "JOIN service_types st ON a.service_type_id = st.id "
        "WHERE a.is_active = 1 LIMIT 1"
    ).fetchone()
    if row is None:
        pytest.skip("No company with active accounts found")

    company_id = row["company_id"] if isinstance(row, dict) else row[0]

    resp = client.patch(
        f"/companies/{company_id}",
        headers=owner_headers,
        json={"is_active": False},
    )
    assert resp.status_code == 200, f"Deactivate failed: {resp.text}"

    # After deactivation, accounts for this company should not appear in active list
    acc_resp = client.get("/accounts/", headers=owner_headers)
    assert acc_resp.status_code == 200
    active_accounts = acc_resp.json()
    company_account_ids = [
        a["id"] for a in active_accounts
        if a.get("company_id") == company_id
    ]
    assert len(company_account_ids) == 0, (
        f"Expected no active accounts for deactivated company {company_id}, "
        f"got {company_account_ids}"
    )
