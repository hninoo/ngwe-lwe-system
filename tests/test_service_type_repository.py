"""
Unit tests for ServiceTypeRepository.

These will be RED until T028 implements ServiceTypeRepository.
Uses seeded_db fixture (post-migration-004 state).
"""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _patch_db(seeded_db):
    from tests.conftest import make_db_patch
    return make_db_patch(seeded_db)


def _get_any_company_id(seeded_db):
    """Return the id of the first active company (e.g. KBZ Pay)."""
    row = seeded_db.execute(
        "SELECT id FROM companies WHERE is_active = 1 ORDER BY id LIMIT 1"
    ).fetchone()
    assert row is not None, "No active companies found"
    return row["id"] if isinstance(row, dict) else row[0]


def test_get_by_company_returns_only_that_company(seeded_db):
    """get_by_company(company_id) returns only service_types for that company."""
    from repositories.service_type_repository import ServiceTypeRepository

    company_id = _get_any_company_id(seeded_db)
    with _patch_db(seeded_db):
        repo = ServiceTypeRepository()
        sts = repo.get_by_company(company_id)

    assert len(sts) > 0, "Should return at least one service_type"
    for st in sts:
        assert st.company_id == company_id, (
            f"Expected company_id={company_id}, got {st.company_id}"
        )
        assert st.is_active is True or st.is_active == 1


def test_get_by_id_returns_correct_service_type(seeded_db):
    """get_by_id(id) returns the correct ServiceType dataclass instance."""
    from repositories.service_type_repository import ServiceTypeRepository
    from models.service_type import ServiceType

    company_id = _get_any_company_id(seeded_db)
    with _patch_db(seeded_db):
        repo = ServiceTypeRepository()
        sts = repo.get_by_company(company_id)
        assert len(sts) > 0
        first = sts[0]
        fetched = repo.get_by_id(first.id)

    assert fetched is not None
    assert isinstance(fetched, ServiceType)
    assert fetched.id == first.id
    assert fetched.company_id == company_id


def test_create_inserts_and_returns_id(seeded_db):
    """create(data) inserts a new service_type and returns the new id."""
    from repositories.service_type_repository import ServiceTypeRepository

    company_id = _get_any_company_id(seeded_db)
    with _patch_db(seeded_db):
        repo = ServiceTypeRepository()
        # Use a unique name to avoid UNIQUE constraint failure
        new_id = repo.create({
            "company_id": company_id,
            "name": "TestServiceType",
            "operation": "All",
            "is_active": 1,
        })

    assert isinstance(new_id, int)
    assert new_id > 0

    with _patch_db(seeded_db):
        repo2 = ServiceTypeRepository()
        created = repo2.get_by_id(new_id)

    assert created is not None
    assert created.name == "TestServiceType"
    assert created.company_id == company_id


def test_deactivate_does_not_affect_siblings(seeded_db):
    """deactivate(id) sets is_active = 0 and does not affect sibling rows."""
    from repositories.service_type_repository import ServiceTypeRepository

    company_id = _get_any_company_id(seeded_db)
    with _patch_db(seeded_db):
        repo = ServiceTypeRepository()
        sts = repo.get_by_company(company_id)
        assert len(sts) >= 2, "Need at least 2 service_types to test sibling isolation"
        target = sts[0]
        sibling = sts[1]

        result = repo.deactivate(target.id)

    assert result is True

    with _patch_db(seeded_db):
        repo2 = ServiceTypeRepository()
        deactivated = repo2.get_by_id(target.id)
        sibling_after = repo2.get_by_id(sibling.id)

    assert deactivated.is_active is False or deactivated.is_active == 0
    # Sibling should still be active
    assert sibling_after.is_active is True or sibling_after.is_active == 1
