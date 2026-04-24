"""
HTTP route tests for /companies/{id}/service-types and /service-types endpoints.

T015: GET/POST /companies/{id}/service-types, PATCH /service-types/{id}

These will be RED until T036/T037 are implemented.
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


@pytest.fixture(scope="module")
def employee_headers():
    return {"Authorization": f"Bearer {_make_token('employee', 2)}"}


@pytest.fixture
def client(seeded_db):
    from tests.conftest import make_db_patch
    from fastapi.testclient import TestClient
    from backend.main import app
    with make_db_patch(seeded_db):
        with TestClient(app) as c:
            yield c


def _get_first_company_id(client, headers):
    resp = client.get("/companies/", headers=headers)
    assert resp.status_code == 200
    companies = resp.json()
    assert len(companies) > 0
    return companies[0]["id"]


def test_get_service_types_for_company(client, owner_headers):
    """GET /companies/{id}/service-types returns list of service_type dicts."""
    company_id = _get_first_company_id(client, owner_headers)
    resp = client.get(f"/companies/{company_id}/service-types", headers=owner_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0
    for st in data:
        assert "id" in st
        assert "company_id" in st
        assert "name" in st
        assert "operation" in st
        assert "is_active" in st
        assert st["company_id"] == company_id


def test_post_service_type_owner_creates(client, owner_headers):
    """POST /companies/{id}/service-types with owner auth creates new service_type → 201."""
    company_id = _get_first_company_id(client, owner_headers)
    resp = client.post(
        f"/companies/{company_id}/service-types",
        headers=owner_headers,
        json={"name": "NewTestType", "operation": "All"},
    )
    assert resp.status_code == 201, f"Expected 201, got {resp.status_code}: {resp.text}"


def test_post_service_type_employee_forbidden(client, employee_headers):
    """POST /companies/{id}/service-types with employee auth → 403."""
    # Use company_id=1 (should exist after migration)
    resp = client.post(
        "/companies/1/service-types",
        headers=employee_headers,
        json={"name": "ShouldFail", "operation": "All"},
    )
    assert resp.status_code == 403


def test_patch_service_type_owner(client, owner_headers):
    """PATCH /service-types/{id} with owner auth updates name/is_active."""
    company_id = _get_first_company_id(client, owner_headers)
    resp = client.get(f"/companies/{company_id}/service-types", headers=owner_headers)
    sts = resp.json()
    assert len(sts) > 0
    st_id = sts[0]["id"]

    patch_resp = client.patch(
        f"/service-types/{st_id}",
        headers=owner_headers,
        json={"name": "UpdatedName"},
    )
    assert patch_resp.status_code == 200
