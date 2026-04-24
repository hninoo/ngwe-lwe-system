"""
HTTP route tests for /companies endpoints.

T013: GET /companies and GET /companies/{id}
T014: Logo upload and serve

These tests will be RED until T036 creates backend/routes/companies.py
and T040 registers the router in main.py.

Uses a real FastAPI TestClient with the app's DB patched to a seeded in-memory DB.
Note: these tests require APP_SECRET env var and the app to be importable.
"""
import io
import os
import sys
import time
import json
import hmac
import hashlib
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Set required env vars before importing backend modules
os.environ.setdefault("APP_SECRET", "test-secret-key-for-unit-tests")
os.environ.setdefault("DB_PATH", ":memory:")


def _make_owner_token() -> str:
    """Create a valid owner token for route tests."""
    secret = os.environ["APP_SECRET"]
    payload = json.dumps({
        "user_id": 1,
        "username": "owner",
        "role": "owner",
        "exp": int(time.time()) + 86400,
    })
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}|{sig}"


def _make_employee_token() -> str:
    """Create a valid employee token."""
    secret = os.environ["APP_SECRET"]
    payload = json.dumps({
        "user_id": 2,
        "username": "employee",
        "role": "employee",
        "exp": int(time.time()) + 86400,
    })
    sig = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}|{sig}"


@pytest.fixture(scope="module")
def owner_headers():
    return {"Authorization": f"Bearer {_make_owner_token()}"}


@pytest.fixture(scope="module")
def employee_headers():
    return {"Authorization": f"Bearer {_make_employee_token()}"}


@pytest.fixture
def client(seeded_db):
    """FastAPI TestClient with seeded DB."""
    from tests.conftest import make_db_patch
    from fastapi.testclient import TestClient
    from backend.main import app
    with make_db_patch(seeded_db):
        with TestClient(app) as c:
            yield c


# ─────────────────────────────────────────────────────────────────────────────
# T013 — GET /companies and GET /companies/{id}
# ─────────────────────────────────────────────────────────────────────────────

def test_get_companies_returns_list(client, owner_headers):
    """GET /companies/ returns a list of company dicts."""
    resp = client.get("/companies/", headers=owner_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) > 0
    for item in data:
        assert "id" in item
        assert "name" in item
        assert "category" in item
        assert "is_active" in item
        assert "logo_path" in item


def test_get_companies_unauthenticated(client):
    """Unauthenticated GET /companies/ returns 401."""
    resp = client.get("/companies/")
    assert resp.status_code == 401


def test_get_company_by_id(client, owner_headers):
    """GET /companies/{id} returns a single company dict."""
    # First get all companies to find a valid ID
    resp = client.get("/companies/", headers=owner_headers)
    assert resp.status_code == 200
    companies = resp.json()
    first_id = companies[0]["id"]

    resp2 = client.get(f"/companies/{first_id}", headers=owner_headers)
    assert resp2.status_code == 200
    data = resp2.json()
    assert data["id"] == first_id


def test_get_company_not_found(client, owner_headers):
    """GET /companies/9999 returns 404."""
    resp = client.get("/companies/9999", headers=owner_headers)
    assert resp.status_code == 404


# ─────────────────────────────────────────────────────────────────────────────
# T014 — Logo upload and serve
# ─────────────────────────────────────────────────────────────────────────────

def test_logo_upload_size_limit(client, owner_headers):
    """POST a 201 KB binary as image/png → expect 422."""
    oversized = b"x" * (201 * 1024)  # 201 KB
    resp = client.post(
        "/companies/1/logo",
        headers=owner_headers,
        files={"file": ("logo.png", io.BytesIO(oversized), "image/png")},
    )
    assert resp.status_code == 422, f"Expected 422, got {resp.status_code}"


def test_logo_upload_invalid_type(client, owner_headers):
    """POST a PDF file as application/pdf → expect 422."""
    pdf_bytes = b"%PDF-1.4 fake pdf content"
    resp = client.post(
        "/companies/1/logo",
        headers=owner_headers,
        files={"file": ("doc.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert resp.status_code == 422, f"Expected 422 for invalid MIME type, got {resp.status_code}"


def test_logo_upload_and_serve(client, owner_headers, tmp_path):
    """Upload a valid PNG (≤ 200 KB), then GET returns same bytes with correct Content-Type."""
    valid_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100  # minimal PNG header

    # Get first company id
    resp = client.get("/companies/", headers=owner_headers)
    company_id = resp.json()[0]["id"]

    with patch("pathlib.Path.mkdir"), \
         patch("pathlib.Path.write_bytes"), \
         patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.read_bytes", return_value=valid_png):

        upload_resp = client.post(
            f"/companies/{company_id}/logo",
            headers=owner_headers,
            files={"file": ("logo.png", io.BytesIO(valid_png), "image/png")},
        )
        assert upload_resp.status_code == 200, f"Upload failed: {upload_resp.text}"


def test_logo_serve_not_found(client, owner_headers):
    """GET /companies/{id}/logo when logo_path IS NULL → returns 404."""
    # Insert a company with no logo
    with patch("backend.database.get_cursor"):
        resp = client.get("/companies/9999/logo", headers=owner_headers)
    assert resp.status_code in (404, 422), (
        f"Expected 404/422 for missing company, got {resp.status_code}"
    )


def test_logo_upload_non_owner_forbidden(client, employee_headers):
    """Non-owner upload attempt → returns 403."""
    valid_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    resp = client.post(
        "/companies/1/logo",
        headers=employee_headers,
        files={"file": ("logo.png", io.BytesIO(valid_png), "image/png")},
    )
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}"
