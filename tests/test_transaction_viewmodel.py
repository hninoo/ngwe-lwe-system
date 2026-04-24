"""
Regression tests for commission calculation after service_type_id refactor.

Uses dependency injection (mock repositories) — no live DB required.
These will be RED until T034 updates TransactionViewModel.
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.account import Account
from models.commission_tier import CommissionTier


def _make_account(service_type_id: int, balance: float = 100000.0) -> Account:
    """Build an Account with the new service_type_id field."""
    return Account(
        id=1,
        account_name="Test Account",
        phone_number="09100000001",
        service_type_id=service_type_id,
        company_id=1,
        balance=balance,
        commission_rate=0.0,
        is_active=True,
    )


def _make_tier(service_type_id: int, comm_deposit: float, comm_withdraw: float) -> CommissionTier:
    return CommissionTier(
        id=1,
        service_type_id=service_type_id,
        amount_from=None,
        amount_to=None,
        fee_amount_type="FIXED",
        fee_amount_deposit=0.0,
        fee_amount_withdraw=0.0,
        comm_type="FIXED",
        comm_deposit=comm_deposit,
        comm_withdraw=comm_withdraw,
        additional_fee_type="FIXED",
        additional_fee_deposit_amount=0.0,
        additional_fee_withdraw_amount=0.0,
        is_active=True,
    )


def _make_vm(account: Account, tier: CommissionTier):
    """Create a TransactionViewModel with mocked repositories."""
    from viewmodels.transaction_viewmodel import TransactionViewModel

    account_repo = MagicMock()
    account_repo.get_by_id.return_value = account
    account_repo.update_balance.return_value = True

    tier_repo = MagicMock()
    tier_repo.get_tier_for_amount.return_value = tier

    txn_repo = MagicMock()
    txn_repo.create.return_value = 1
    txn_repo.get_by_id.return_value = None  # not important for commission test

    rate_repo = MagicMock()

    vm = TransactionViewModel(
        transaction_repo=txn_repo,
        account_repo=account_repo,
        exchange_rate_repo=rate_repo,
        commission_tier_repo=tier_repo,
    )
    return vm, tier_repo


# ─────────────────────────────────────────────────────────────────────────────

def test_commission_calc_kpay_wst():
    """Commission for KBZ Pay WST at 50,000 MMK = 500.0 (seeded value)."""
    KPAY_WST_ID = 1
    account = _make_account(service_type_id=KPAY_WST_ID)
    tier    = _make_tier(KPAY_WST_ID, comm_deposit=500.0, comm_withdraw=500.0)

    vm, tier_repo = _make_vm(account, tier)
    comm = vm._calc_commission(account, 50000.0, "send")

    assert comm == 500.0, f"Expected 500.0, got {comm}"
    # Verify lookup was called with service_type_id (not strings)
    tier_repo.get_tier_for_amount.assert_called_with(
        service_type_id=KPAY_WST_ID, amount=50000.0
    )


def test_commission_calc_wave_wst():
    """Commission for Wave Money WST agent account at 10,000 MMK = 400.0."""
    WAVE_WST_ID = 2
    account = _make_account(service_type_id=WAVE_WST_ID)
    tier    = _make_tier(WAVE_WST_ID, comm_deposit=400.0, comm_withdraw=400.0)

    vm, tier_repo = _make_vm(account, tier)
    comm = vm._calc_commission(account, 10000.0, "send")

    assert comm == 400.0, f"Expected 400.0, got {comm}"
    tier_repo.get_tier_for_amount.assert_called_with(
        service_type_id=WAVE_WST_ID, amount=10000.0
    )


def test_commission_calc_wave_account():
    """Commission for Wave Money Pay_To_Pay personal account."""
    WAVE_P2P_ID = 3
    account = _make_account(service_type_id=WAVE_P2P_ID)
    tier    = _make_tier(WAVE_P2P_ID, comm_deposit=300.0, comm_withdraw=300.0)

    vm, tier_repo = _make_vm(account, tier)
    comm = vm._calc_commission(account, 10000.0, "send")

    assert comm == 300.0, f"Expected 300.0, got {comm}"
    tier_repo.get_tier_for_amount.assert_called_with(
        service_type_id=WAVE_P2P_ID, amount=10000.0
    )


def test_commission_calc_true_money_wst():
    """True Money WST returns its own dedicated tier (not KPAY tier)."""
    TRUE_MONEY_WST_ID = 5  # distinct ID from KPAY
    account = _make_account(service_type_id=TRUE_MONEY_WST_ID)
    tier    = _make_tier(TRUE_MONEY_WST_ID, comm_deposit=500.0, comm_withdraw=500.0)

    vm, tier_repo = _make_vm(account, tier)
    comm = vm._calc_commission(account, 50000.0, "send")

    assert comm == 500.0
    # Critically: lookup uses True Money's own service_type_id, not KPAY's
    tier_repo.get_tier_for_amount.assert_called_with(
        service_type_id=TRUE_MONEY_WST_ID, amount=50000.0
    )
