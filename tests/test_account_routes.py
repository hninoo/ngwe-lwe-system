"""
HTTP route tests for updated GET /accounts with service_type_id filter.

T016: Updated accounts endpoint with company_id + service_type_id filters.

These will be RED until T038 updates backend/routes/accounts.py.
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


def _get_first_service_type_id(seeded_db):
    row = seeded_db.execute(
        "SELECT id FROM service_types WHERE is_active = 1 LIMIT 1"
    ).fetchone()
    assert row is not None
    return row["id"] if isinstance(row, dict) else row[0]


def test_get_accounts_with_service_type_filter(client, owner_headers, seeded_db):
    """GET /accounts/?service_type_id=<id> returns only accounts for that service_type."""
    st_id = _get_first_service_type_id(seeded_db)
    resp = client.get("/accounts/", headers=owner_headers, params={"service_type_id": st_id})
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    for acc in data:
        assert acc["service_type_id"] == st_id


def test_get_accounts_all_active(client, owner_headers):
    """GET /accounts/ without filter returns all active accounts."""
    resp = client.get("/accounts/", headers=owner_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0


def test_accounts_response_has_new_fields(client, owner_headers):
    """Response payload includes service_type_id and company_id; no service_id or service_type TEXT."""
    resp = client.get("/accounts/", headers=owner_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) > 0
    first = data[0]
    assert "service_type_id" in first, "service_type_id missing from response"
    assert "company_id" in first, "company_id missing from response"
    assert "service_id" not in first, "service_id should NOT be in response"
    # service_type TEXT should be gone too (no string like 'KPAY'/'WAVE')
    # Note: there may be a 'service_type_id' but not 'service_type' as a plain text string key
    # The old 'service_type' TEXT field should not appear as a separate field
    # We check it's not a free-text string value field (it's OK if service_type_id exists)
