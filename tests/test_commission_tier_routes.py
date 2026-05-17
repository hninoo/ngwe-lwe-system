"""
HTTP route tests for updated GET /commission-tiers with service_type_id filter.

T017: Updated commission_tiers endpoint with service_type_id.

These will be RED until T039 updates backend/routes/commission_tiers.py.
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


def _get_kpay_wst_id(seeded_db) -> int:
    row = seeded_db.execute(
        "SELECT st.id FROM service_types st JOIN companies c ON c.id = st.company_id "
        "WHERE c.name = 'KBZ Pay' AND st.name = 'WST' LIMIT 1"
    ).fetchone()
    assert row is not None, "KBZ Pay WST service_type not found"
    return row["id"] if isinstance(row, dict) else row[0]


def _get_service_type_id(seeded_db, company_name: str, service_type_name: str) -> int:
    row = seeded_db.execute(
        "SELECT st.id FROM service_types st JOIN companies c ON c.id = st.company_id "
        "WHERE c.name = ? AND st.name = ? LIMIT 1",
        (company_name, service_type_name),
    ).fetchone()
    assert row is not None, f"{company_name} {service_type_name} service_type not found"
    return row["id"] if isinstance(row, dict) else row[0]


def test_get_tiers_with_service_type_id_filter(client, owner_headers, seeded_db):
    """GET /commission-tiers/?service_type_id=<id> returns tiers for that service_type."""
    st_id = _get_kpay_wst_id(seeded_db)
    resp = client.get(
        "/commission-tiers/",
        headers=owner_headers,
        params={"service_type_id": st_id},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    for t in data:
        assert t["service_type_id"] == st_id


def test_lookup_tier_with_service_type_id(client, owner_headers, seeded_db):
    """GET /commission-tiers/lookup?service_type_id=<id>&amount=50000 returns correct tier dict."""
    st_id = _get_kpay_wst_id(seeded_db)
    resp = client.get(
        "/commission-tiers/lookup",
        headers=owner_headers,
        params={"service_type_id": st_id, "amount": 50000},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "comm_cash_in" in data
    assert data["comm_cash_in"] == 500.0
    assert "comm_deposit" in data
    assert data["comm_deposit"] == 500.0


def test_legacy_service_type_string_not_accepted(client, owner_headers):
    """Legacy service_type string query param is no longer accepted → 422."""
    resp = client.get(
        "/commission-tiers/",
        headers=owner_headers,
        params={"service_type": "KPAY_WST", "account_type": "agent"},
    )
    # The old params should not work — either 422 (validation) or return empty/fail
    # After T039, the required param is service_type_id (int) so passing strings will 422
    assert resp.status_code == 422, (
        f"Expected 422 for legacy string param, got {resp.status_code}"
    )


def test_create_tier_requires_fee_type_but_allows_optional_commission_and_add_types(
    client,
    owner_headers,
    seeded_db,
):
    """Fee type is required by the client; API defaults optional commission/add types."""
    st_id = _get_service_type_id(seeded_db, "KBZ Pay", "Pay_To_Pay")
    resp = client.post(
        "/commission-tiers/",
        headers=owner_headers,
        json={
            "service_type_id": st_id,
            "amount_from": 100000,
            "amount_to": 200000,
            "fee_amount_type": "FIXED",
            "fee_amount_deposit": 100,
            "fee_amount_withdraw": 100,
        },
    )

    assert resp.status_code == 200, resp.text
    tier_id = resp.json()["id"]
    row = seeded_db.execute(
        "SELECT fee_amount_type, comm_type, additional_fee_type "
        "FROM commission_tiers WHERE id = ?",
        (tier_id,),
    ).fetchone()
    assert row["fee_amount_type"] == "FIXED"
    assert row["comm_type"] == "FIXED"
    assert row["additional_fee_type"] == "FIXED"


def test_create_tier_rejects_missing_fee_type(client, owner_headers, seeded_db):
    st_id = _get_service_type_id(seeded_db, "KBZ Pay", "Pay_To_Pay")
    resp = client.post(
        "/commission-tiers/",
        headers=owner_headers,
        json={
            "service_type_id": st_id,
            "amount_from": 200000,
            "amount_to": 300000,
        },
    )

    assert resp.status_code == 422


def test_update_tier_uses_deposit_withdraw_columns(client, owner_headers, seeded_db):
    st_id = _get_service_type_id(seeded_db, "KBZ Pay", "Pay_To_Pay")
    create_resp = client.post(
        "/commission-tiers/",
        headers=owner_headers,
        json={
            "service_type_id": st_id,
            "amount_from": 1,
            "amount_to": 100000,
            "fee_amount_type": "FIXED",
            "fee_amount_deposit": 100,
            "fee_amount_withdraw": 200,
        },
    )
    assert create_resp.status_code == 200, create_resp.text
    tier_id = create_resp.json()["id"]

    update_resp = client.put(
        f"/commission-tiers/{tier_id}",
        headers=owner_headers,
        json={
            "service_type_id": st_id,
            "amount_from": 1,
            "amount_to": 100000,
            "fee_amount_type": "PERCENTAGE",
            "fee_amount_deposit": 0.01,
            "fee_amount_withdraw": 0.02,
            "comm_type": None,
            "comm_deposit": None,
            "comm_withdraw": 50,
            "additional_fee_type": None,
            "additional_fee_deposit_amount": 0,
            "additional_fee_withdraw_amount": 25,
        },
    )
    assert update_resp.status_code == 200, update_resp.text

    row = seeded_db.execute(
        "SELECT fee_amount_type, fee_amount_deposit, fee_amount_withdraw, "
        "comm_type, comm_deposit, comm_withdraw, additional_fee_type, "
        "additional_fee_deposit_amount, additional_fee_withdraw_amount "
        "FROM commission_tiers WHERE id = ?",
        (tier_id,),
    ).fetchone()
    assert row["fee_amount_type"] == "PERCENTAGE"
    assert row["fee_amount_deposit"] == 0.01
    assert row["fee_amount_withdraw"] == 0.02
    assert row["comm_type"] == "FIXED"
    assert row["comm_deposit"] == 0.0
    assert row["comm_withdraw"] == 50.0
    assert row["additional_fee_type"] == "FIXED"
    assert row["additional_fee_deposit_amount"] == 0.0
    assert row["additional_fee_withdraw_amount"] == 25.0


def test_create_tier_rejects_zero_from_amount(client, owner_headers, seeded_db):
    st_id = _get_service_type_id(seeded_db, "KBZ Pay", "Pay_To_Pay")
    resp = client.post(
        "/commission-tiers/",
        headers=owner_headers,
        json={
            "service_type_id": st_id,
            "amount_from": 0,
            "amount_to": 100000,
            "fee_amount_type": "FIXED",
        },
    )

    assert resp.status_code == 422


def test_range_overlap_is_scoped_to_company_specific_service_type(
    client,
    owner_headers,
    seeded_db,
):
    """The same Pay_To_Pay range may exist for a different company service_type."""
    kbz_st_id = _get_service_type_id(seeded_db, "KBZ Pay", "Pay_To_Pay")
    wave_st_id = _get_service_type_id(seeded_db, "Wave Money", "Pay_To_Pay")
    payload = {
        "amount_from": 250000,
        "amount_to": 350000,
        "fee_amount_type": "FIXED",
    }

    first = client.post(
        "/commission-tiers/",
        headers=owner_headers,
        json={"service_type_id": kbz_st_id, **payload},
    )
    assert first.status_code == 200, first.text

    same_company = client.post(
        "/commission-tiers/",
        headers=owner_headers,
        json={"service_type_id": kbz_st_id, **payload},
    )
    assert same_company.status_code == 422

    other_company = client.post(
        "/commission-tiers/",
        headers=owner_headers,
        json={"service_type_id": wave_st_id, **payload},
    )
    assert other_company.status_code == 200, other_company.text


def test_commission_tiers_table_matches_required_column_contract(seeded_db):
    columns = {
        row["name"]: row
        for row in seeded_db.execute("PRAGMA table_info(commission_tiers)").fetchall()
    }

    assert columns["amount_from"]["notnull"] == 1
    assert columns["amount_to"]["notnull"] == 1
    assert columns["fee_amount_type"]["notnull"] == 1
    assert columns["fee_amount_deposit"]["notnull"] == 1
    assert columns["fee_amount_withdraw"]["notnull"] == 1
    assert columns["comm_type"]["notnull"] == 0
    assert columns["comm_deposit"]["notnull"] == 0
    assert columns["comm_withdraw"]["notnull"] == 0
    assert columns["additional_fee_type"]["notnull"] == 0
    assert columns["additional_fee_deposit_amount"]["notnull"] == 0
    assert columns["additional_fee_withdraw_amount"]["notnull"] == 0
    assert "fee_amount_cash_in" not in columns
    assert "fee_amount_cash_out" not in columns
    assert "comm_cash_in" not in columns
    assert "comm_cash_out" not in columns
    assert "additional_fee_cash_in_amount" not in columns
    assert "additional_fee_cash_out_amount" not in columns
