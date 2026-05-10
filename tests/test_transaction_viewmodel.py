"""
Regression tests for commission calculation after service_type_id refactor.

Uses dependency injection (mock repositories) — no live DB required.
These will be RED until T034 updates TransactionViewModel.
"""
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from unittest.mock import patch

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


def _make_tier(
    service_type_id: int,
    comm_deposit: float,
    comm_withdraw: float,
    fee_amount_type: str = "FIXED",
    fee_amount_deposit: float = 0.0,
    fee_amount_withdraw: float = 0.0,
    additional_fee_type: str = "FIXED",
    additional_fee_deposit_amount: float = 0.0,
    additional_fee_withdraw_amount: float = 0.0,
) -> CommissionTier:
    return CommissionTier(
        id=1,
        service_type_id=service_type_id,
        amount_from=None,
        amount_to=None,
        fee_amount_type=fee_amount_type,
        fee_amount_deposit=fee_amount_deposit,
        fee_amount_withdraw=fee_amount_withdraw,
        comm_type="FIXED",
        comm_deposit=comm_deposit,
        comm_withdraw=comm_withdraw,
        additional_fee_type=additional_fee_type,
        additional_fee_deposit_amount=additional_fee_deposit_amount,
        additional_fee_withdraw_amount=additional_fee_withdraw_amount,
        is_active=True,
    )


def _make_vm(account: Account, tier: CommissionTier):
    """Create a TransactionViewModel with mocked repositories."""
    from viewmodels.transaction_viewmodel import TransactionViewModel

    account_repo = MagicMock()
    account_repo.get_by_id.return_value = account
    account_repo.increment_balance.return_value = True

    tier_repo = MagicMock()
    tier_repo.get_tier_for_amount.return_value = tier

    txn_repo = MagicMock()
    txn_repo.create.return_value = 1
    txn_repo.get_by_id.return_value = None  # not important for commission test

    rate_repo = MagicMock()
    service_type_repo = MagicMock()
    service_type_repo.get_by_id.return_value = SimpleNamespace(company_id=account.company_id)
    float_repo = MagicMock()

    vm = TransactionViewModel(
        transaction_repo=txn_repo,
        account_repo=account_repo,
        exchange_rate_repo=rate_repo,
        commission_tier_repo=tier_repo,
        service_type_repo=service_type_repo,
        float_repo=float_repo,
    )
    return vm, tier_repo, account_repo, float_repo


# ─────────────────────────────────────────────────────────────────────────────

def test_commission_calc_kpay_wst():
    """Commission for KBZ Pay WST at 50,000 MMK = 500.0 (seeded value)."""
    KPAY_WST_ID = 1
    account = _make_account(service_type_id=KPAY_WST_ID)
    tier    = _make_tier(KPAY_WST_ID, comm_deposit=500.0, comm_withdraw=500.0)

    vm, tier_repo, _, _ = _make_vm(account, tier)
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

    vm, tier_repo, _, _ = _make_vm(account, tier)
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

    vm, tier_repo, _, _ = _make_vm(account, tier)
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

    vm, tier_repo, _, _ = _make_vm(account, tier)
    comm = vm._calc_commission(account, 50000.0, "send")

    assert comm == 500.0
    # Critically: lookup uses True Money's own service_type_id, not KPAY's
    tier_repo.get_tier_for_amount.assert_called_with(
        service_type_id=TRUE_MONEY_WST_ID, amount=50000.0
    )


def test_cash_in_decreases_account_and_increases_drawer():
    account = _make_account(service_type_id=1)
    tier = _make_tier(1, comm_deposit=0.0, comm_withdraw=0.0)
    vm, _, account_repo, float_repo = _make_vm(account, tier)

    with patch("viewmodels.transaction_viewmodel._log"), patch("viewmodels.transaction_viewmodel.atomic"):
        vm.create_deposit(
            account_id=1,
            amount=25000.0,
            customer_name="A",
            customer_phone="09",
            created_by=7,
            employee_id=7,
        )

    account_repo.increment_balance.assert_any_call(1, -25000.0)
    float_repo.add_float_balance.assert_called_once_with(7, 25000.0)
    created = vm._txn_repo.create.call_args.args[0]
    assert created["balance_change"] == -25000.0


def test_cash_out_increases_account_and_decreases_drawer():
    account = _make_account(service_type_id=1)
    tier = _make_tier(1, comm_deposit=0.0, comm_withdraw=0.0)
    vm, _, account_repo, float_repo = _make_vm(account, tier)
    active_float = SimpleNamespace(id=1, current_balance=50000.0)
    float_repo.get_active_float_for_employee.return_value = active_float

    with patch("viewmodels.transaction_viewmodel._log"), patch("viewmodels.transaction_viewmodel.atomic"):
        vm.create_withdraw(
            account_id=1,
            amount=25000.0,
            customer_name="A",
            customer_phone="09",
            created_by=7,
            employee_id=7,
        )

    account_repo.increment_balance.assert_any_call(1, 25000.0)
    float_repo.deduct_float_balance.assert_called_once_with(7, 25000.0)
    created = vm._txn_repo.create.call_args.args[0]
    assert created["balance_change"] == 25000.0


def test_tier_fee_fallback_combines_fixed_and_percentage():
    account = _make_account(service_type_id=1)
    tier = _make_tier(
        1,
        comm_deposit=0.0,
        comm_withdraw=0.0,
        fee_amount_type="PERCENTAGE",
        fee_amount_deposit=0.02,
        additional_fee_type="FIXED",
        additional_fee_deposit_amount=500.0,
    )
    vm, _, _, _ = _make_vm(account, tier)

    customer_fee, additional = vm._resolve_fee_values(
        account, 100000.0, "deposit", 0.0, 0.0
    )

    assert customer_fee == 2500.0
    assert additional == 500.0
