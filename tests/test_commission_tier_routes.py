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
