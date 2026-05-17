"""
Unit tests for CommissionTierRepository with service_type_id-based lookup.

These will be RED until T030 updates CommissionTierRepository.
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


def _get_service_type_id(seeded_db, company_name: str, st_name: str) -> int:
    """Helper: resolve (company_name, service_type_name) → service_type_id."""
    row = seeded_db.execute(
        "SELECT st.id FROM service_types st "
        "JOIN companies c ON c.id = st.company_id "
        "WHERE c.name = ? AND st.name = ? AND st.is_active = 1",
        (company_name, st_name),
    ).fetchone()
    assert row is not None, f"No service_type found for {company_name}/{st_name}"
    return row["id"] if isinstance(row, dict) else row[0]


def test_tier_lookup_by_id(seeded_db):
    """
    get_tier_for_amount(service_type_id=<kpay_wst_id>, amount=50000)
    returns the correct tier (verify comm_cash_in matches seeded value).
    """
    from repositories.commission_tier_repository import CommissionTierRepository

    kpay_wst_id = _get_service_type_id(seeded_db, "KBZ Pay", "WST")

    with _patch_db(seeded_db):
        repo = CommissionTierRepository()
        tier = repo.get_tier_for_amount(service_type_id=kpay_wst_id, amount=50000)

    assert tier is not None, "Should find a tier for KBZ Pay WST at 50000"
    assert tier.service_type_id == kpay_wst_id
    assert tier.comm_cash_in == 500.0, (
        f"Expected comm_cash_in=500.0, got {tier.comm_cash_in}"
    )


def test_tier_lookup_wave_wst(seeded_db):
    """Wave Money WST lookup returns distinct tier from KBZ Pay WST."""
    from repositories.commission_tier_repository import CommissionTierRepository

    kpay_wst_id  = _get_service_type_id(seeded_db, "KBZ Pay",    "WST")
    wave_wst_id  = _get_service_type_id(seeded_db, "Wave Money", "WST")

    with _patch_db(seeded_db):
        repo = CommissionTierRepository()
        kpay_tier = repo.get_tier_for_amount(service_type_id=kpay_wst_id, amount=10000)
        wave_tier = repo.get_tier_for_amount(service_type_id=wave_wst_id, amount=10000)

    assert wave_tier is not None, "Should find a tier for Wave Money WST"
    assert kpay_tier is not None, "Should find a tier for KBZ Pay WST"
    assert wave_tier.service_type_id != kpay_tier.service_type_id, (
        "Wave WST and KPAY WST should be distinct tiers"
    )
    assert wave_tier.comm_cash_in == 400.0, (
        f"Expected Wave WST comm_cash_in=400.0, got {wave_tier.comm_cash_in}"
    )


def test_tier_lookup_true_money(seeded_db):
    """True Money WST has its own dedicated tier row (not the KPAY tier)."""
    from repositories.commission_tier_repository import CommissionTierRepository

    kpay_wst_id  = _get_service_type_id(seeded_db, "KBZ Pay",    "WST")
    tm_wst_id    = _get_service_type_id(seeded_db, "True Money", "WST")

    with _patch_db(seeded_db):
        repo = CommissionTierRepository()
        kpay_tier = repo.get_tier_for_amount(service_type_id=kpay_wst_id, amount=50000)
        tm_tier   = repo.get_tier_for_amount(service_type_id=tm_wst_id,   amount=50000)

    assert tm_tier is not None, "True Money WST should have its own tier"
    assert tm_tier.service_type_id == tm_wst_id, (
        "True Money tier should map to True Money WST service_type_id"
    )
    assert tm_tier.service_type_id != kpay_tier.service_type_id, (
        "True Money tier should be distinct from KBZ Pay tier"
    )


def test_tier_lookup_no_match(seeded_db):
    """Returns None for a service_type_id with no tier rows."""
    from repositories.commission_tier_repository import CommissionTierRepository

    # Use a very high ID that definitely doesn't exist
    fake_id = 99999

    with _patch_db(seeded_db):
        repo = CommissionTierRepository()
        tier = repo.get_tier_for_amount(service_type_id=fake_id, amount=50000)

    assert tier is None, "Should return None for an unknown service_type_id"


def test_tier_lookup_uses_next_adjacent_range_at_boundary(seeded_db):
    """Adjacent ranges are half-open: [from, to), so amount == to uses the next tier."""
    from repositories.commission_tier_repository import CommissionTierRepository

    st_id = _get_service_type_id(seeded_db, "Wave Money", "Pay_To_Pay")
    seeded_db.execute(
        "INSERT INTO commission_tiers "
        "(service_type_id, amount_from, amount_to, comm_deposit, comm_withdraw) "
        "VALUES (?, ?, ?, ?, ?)",
        (st_id, 100000, 200000, 111.0, 111.0),
    )
    seeded_db.execute(
        "INSERT INTO commission_tiers "
        "(service_type_id, amount_from, amount_to, comm_deposit, comm_withdraw) "
        "VALUES (?, ?, ?, ?, ?)",
        (st_id, 200000, 300000, 222.0, 222.0),
    )
    seeded_db.commit()

    with _patch_db(seeded_db):
        repo = CommissionTierRepository()
        tier = repo.get_tier_for_amount(service_type_id=st_id, amount=200000)

    assert tier is not None
    assert tier.amount_from == 200000
    assert tier.amount_to == 300000
    assert tier.comm_cash_in == 222.0


def test_tier_lookup_prefers_bounded_range_over_catch_all(seeded_db):
    """Migrated catch-all tiers should not hide newly configured From/To ranges."""
    from repositories.commission_tier_repository import CommissionTierRepository

    st_id = _get_service_type_id(seeded_db, "Wave Money", "Pay_To_Pay")
    seeded_db.execute(
        "INSERT INTO commission_tiers "
        "(service_type_id, amount_from, amount_to, comm_deposit, comm_withdraw) "
        "VALUES (?, ?, ?, ?, ?)",
        (st_id, 400000, 500000, 444.0, 444.0),
    )
    seeded_db.commit()

    with _patch_db(seeded_db):
        repo = CommissionTierRepository()
        tier = repo.get_tier_for_amount(service_type_id=st_id, amount=450000)

    assert tier is not None
    assert tier.amount_from == 400000
    assert tier.amount_to == 500000
    assert tier.comm_cash_in == 444.0
