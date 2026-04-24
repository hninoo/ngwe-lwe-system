"""
Unit tests for CompanyRepository.

These will be RED until T027 implements CompanyRepository.
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


def test_get_all_active_returns_only_active(seeded_db):
    """get_all_active() returns only companies where is_active = 1."""
    from repositories.company_repository import CompanyRepository

    with _patch_db(seeded_db):
        repo = CompanyRepository()
        companies = repo.get_all_active()

    assert len(companies) > 0, "Should return at least one company"
    for c in companies:
        assert c.is_active is True or c.is_active == 1, (
            f"Company {c.id} should be active"
        )


def test_get_by_id_returns_correct_company(seeded_db):
    """get_by_id(id) returns the correct Company dataclass instance."""
    from repositories.company_repository import CompanyRepository
    from models.company import Company

    with _patch_db(seeded_db):
        repo = CompanyRepository()
        companies = repo.get_all_active()
        assert len(companies) > 0
        first = companies[0]
        fetched = repo.get_by_id(first.id)

    assert fetched is not None
    assert isinstance(fetched, Company)
    assert fetched.id == first.id
    assert fetched.name == first.name


def test_create_inserts_and_returns_id(seeded_db):
    """create(data) inserts a new company and returns the new id."""
    from repositories.company_repository import CompanyRepository

    with _patch_db(seeded_db):
        repo = CompanyRepository()
        new_id = repo.create({"name": "Test Wallet", "category": "Pay", "is_active": 1})

    assert isinstance(new_id, int)
    assert new_id > 0

    with _patch_db(seeded_db):
        repo2 = CompanyRepository()
        created = repo2.get_by_id(new_id)

    assert created is not None
    assert created.name == "Test Wallet"
    assert created.category == "Pay"


def test_update_changes_name_and_category(seeded_db):
    """update(id, data) updates name and category fields."""
    from repositories.company_repository import CompanyRepository

    with _patch_db(seeded_db):
        repo = CompanyRepository()
        companies = repo.get_all_active()
        target = companies[0]
        result = repo.update(target.id, {"name": "Updated Name", "category": "Both"})

    assert result is True

    with _patch_db(seeded_db):
        repo2 = CompanyRepository()
        updated = repo2.get_by_id(target.id)

    assert updated.name == "Updated Name"
    assert updated.category == "Both"


def test_deactivate_sets_is_active_false(seeded_db):
    """deactivate(id) sets is_active = 0."""
    from repositories.company_repository import CompanyRepository

    with _patch_db(seeded_db):
        repo = CompanyRepository()
        companies = repo.get_all_active()
        assert len(companies) > 0
        target = companies[0]
        result = repo.deactivate(target.id)

    assert result is True

    with _patch_db(seeded_db):
        repo2 = CompanyRepository()
        deactivated = repo2.get_by_id(target.id)

    assert deactivated.is_active is False or deactivated.is_active == 0
