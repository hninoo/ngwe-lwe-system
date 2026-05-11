"""
Regression tests for commission calculation after service_type_id refactor.

Uses dependency injection (mock repositories) — no live DB required.
These will be RED until T034 updates TransactionViewModel.
"""
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from pydantic import ValidationError

ROOT = Path(__file__).parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from models.account import Account
from models.commission_tier import CommissionTier
from models.transaction import Transaction


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
    comm_cash_in: float,
    comm_cash_out: float,
    fee_amount_type: str = "FIXED",
    fee_amount_cash_in: float = 0.0,
    fee_amount_cash_out: float = 0.0,
    additional_fee_type: str = "FIXED",
    additional_fee_cash_in_amount: float = 0.0,
    additional_fee_cash_out_amount: float = 0.0,
) -> CommissionTier:
    return CommissionTier(
        id=1,
        service_type_id=service_type_id,
        amount_from=None,
        amount_to=None,
        fee_amount_type=fee_amount_type,
        fee_amount_cash_in=fee_amount_cash_in,
        fee_amount_cash_out=fee_amount_cash_out,
        comm_type="FIXED",
        comm_cash_in=comm_cash_in,
        comm_cash_out=comm_cash_out,
        additional_fee_type=additional_fee_type,
        additional_fee_cash_in_amount=additional_fee_cash_in_amount,
        additional_fee_cash_out_amount=additional_fee_cash_out_amount,
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
    tier    = _make_tier(KPAY_WST_ID, comm_cash_in=500.0, comm_cash_out=500.0)

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
    tier    = _make_tier(WAVE_WST_ID, comm_cash_in=400.0, comm_cash_out=400.0)

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
    tier    = _make_tier(WAVE_P2P_ID, comm_cash_in=300.0, comm_cash_out=300.0)

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
    tier    = _make_tier(TRUE_MONEY_WST_ID, comm_cash_in=500.0, comm_cash_out=500.0)

    vm, tier_repo, _, _ = _make_vm(account, tier)
    comm = vm._calc_commission(account, 50000.0, "send")

    assert comm == 500.0
    # Critically: lookup uses True Money's own service_type_id, not KPAY's
    tier_repo.get_tier_for_amount.assert_called_with(
        service_type_id=TRUE_MONEY_WST_ID, amount=50000.0
    )


def test_employee_cash_in_is_pending_and_does_not_touch_mini_vault():
    account = _make_account(service_type_id=1)
    tier = _make_tier(1, comm_cash_in=0.0, comm_cash_out=0.0)
    vm, _, account_repo, float_repo = _make_vm(account, tier)

    with patch("repositories.transaction_operation_base.TransactionOperationBase._log"):
        vm.create_cash_in(
            account_id=1,
            amount=25000.0,
            customer_name="A",
            customer_phone="09",
            created_by=7,
            employee_id=7,
        )

    account_repo.increment_balance.assert_any_call(1, -25000.0)
    float_repo.add_float_balance.assert_not_called()
    created = vm._txn_repo.create.call_args.args[0]
    assert created["balance_change"] == -25000.0
    assert created["status"] == "PENDING_CASHIER_CONFIRM"
    assert created["vault_impact"] == "none"


def test_employee_cash_in_overpayment_deducts_change_from_float():
    account = _make_account(service_type_id=1)
    tier = _make_tier(1, comm_cash_in=0.0, comm_cash_out=0.0)
    vm, _, account_repo, float_repo = _make_vm(account, tier)
    active_float = SimpleNamespace(id=5, employee_id=7, status="ACTIVE", current_balance=10000.0)
    float_repo.get_active_float_for_employee.return_value = active_float
    float_repo.get_float.return_value = active_float
    float_repo.get_denomination_balance.return_value = {5000: 2}
    vm._vault_service._vault_txn_repo = MagicMock()

    with patch("repositories.transaction_operation_base.TransactionOperationBase._log"):
        vm.create_cash_in(
            account_id=1,
            amount=25000.0,
            amount_received=30000.0,
            received_breakdown=[{"denomination_id": 10000, "quantity": 3}],
            change_breakdown=[{"denomination_id": 5000, "quantity": 1}],
            customer_name="A",
            customer_phone="09",
            created_by=7,
            employee_id=7,
        )

    account_repo.increment_balance.assert_any_call(1, -25000.0)
    float_repo.deduct_denominations.assert_called_once_with(5, {5000: 1})
    float_repo.deduct_float_balance.assert_called_once_with(7, 5000.0)
    created = vm._txn_repo.create.call_args.args[0]
    assert created["amount"] == 25000.0
    assert created["status"] == "PENDING_CASHIER_CONFIRM"
    assert created["vault_impact"] == "none"


def test_employee_cash_in_overpayment_requires_matching_change_breakdown():
    account = _make_account(service_type_id=1)
    tier = _make_tier(1, comm_cash_in=0.0, comm_cash_out=0.0)
    vm, _, account_repo, float_repo = _make_vm(account, tier)

    with pytest.raises(ValueError, match="change_breakdown total"):
        vm.create_cash_in(
            account_id=1,
            amount=25000.0,
            amount_received=30000.0,
            received_breakdown={"10000": 3},
            change_breakdown={"1000": 1},
            customer_name="A",
            customer_phone="09",
            created_by=7,
            employee_id=7,
        )

    account_repo.increment_balance.assert_not_called()
    float_repo.deduct_denominations.assert_not_called()
    vm._txn_repo.create.assert_not_called()


def test_owner_cash_in_starts_pending_checker_flow():
    account = _make_account(service_type_id=1)
    tier = _make_tier(1, comm_cash_in=0.0, comm_cash_out=0.0)
    vm, _, account_repo, float_repo = _make_vm(account, tier)

    with patch("repositories.transaction_operation_base.TransactionOperationBase._log"):
        vm.create_cash_in(
            account_id=1,
            amount=25000.0,
            customer_name="A",
            customer_phone="09",
            created_by=1,
            employee_id=None,
        )

    account_repo.increment_balance.assert_any_call(1, -25000.0)
    float_repo.add_float_balance.assert_not_called()
    created = vm._txn_repo.create.call_args.args[0]
    assert created["status"] == "PENDING_CASHIER_CONFIRM"
    assert created["vault_impact"] == "none"


def test_cancel_pending_cash_in_auto_reverses_digital_balance():
    account = _make_account(service_type_id=1)
    tier = _make_tier(1, comm_cash_in=0.0, comm_cash_out=0.0)
    vm, _, account_repo, _ = _make_vm(account, tier)
    pending_txn = Transaction(
        id=42,
        transaction_type="cash_in",
        account_id=1,
        amount=25000.0,
        status="PENDING_CASHIER_CONFIRM",
        vault_impact="none",
        created_by=7,
    )
    cancelled_txn = Transaction(
        id=42,
        transaction_type="cash_in",
        account_id=1,
        amount=25000.0,
        status="CANCELLED",
        vault_impact="none",
        created_by=7,
        confirmed_by=3,
    )
    vm._txn_repo.get_by_id.return_value = pending_txn
    vm._txn_repo.cancel_pending_cash_in.return_value = cancelled_txn

    updated = vm._cash_in_repo.cancel_pending_cash_in(42, 3, "Wrong amount")

    account_repo.increment_balance.assert_called_once_with(1, 25000.0)
    vm._txn_repo.cancel_pending_cash_in.assert_called_once_with(42, 3, "Wrong amount")
    assert updated.status == "CANCELLED"


def test_cancel_pending_cash_in_balance_failure_does_not_cancel():
    account = _make_account(service_type_id=1)
    tier = _make_tier(1, comm_cash_in=0.0, comm_cash_out=0.0)
    vm, _, account_repo, _ = _make_vm(account, tier)
    pending_txn = Transaction(
        id=42,
        transaction_type="cash_in",
        account_id=1,
        amount=25000.0,
        status="PENDING_CASHIER_CONFIRM",
        vault_impact="none",
        created_by=7,
    )
    vm._txn_repo.get_by_id.return_value = pending_txn
    account_repo.increment_balance.return_value = False

    with pytest.raises(RuntimeError):
        vm._cash_in_repo.cancel_pending_cash_in(42, 3, "Inactive account")

    vm._txn_repo.cancel_pending_cash_in.assert_not_called()


def test_cancel_pending_cash_in_status_race_rolls_back_reversal():
    account = _make_account(service_type_id=1)
    tier = _make_tier(1, comm_cash_in=0.0, comm_cash_out=0.0)
    vm, _, account_repo, _ = _make_vm(account, tier)
    pending_txn = Transaction(
        id=42,
        transaction_type="cash_in",
        account_id=1,
        amount=25000.0,
        status="PENDING_CASHIER_CONFIRM",
        vault_impact="none",
        created_by=7,
    )
    vm._txn_repo.get_by_id.return_value = pending_txn
    vm._txn_repo.cancel_pending_cash_in.return_value = None

    with pytest.raises(RuntimeError):
        vm._cash_in_repo.cancel_pending_cash_in(42, 3, "Already handled")

    account_repo.increment_balance.assert_called_once_with(1, Decimal("25000.0"))


def test_confirm_cash_in_rejects_negative_denominations():
    from backend.routes.cashier import ConfirmCashInRequest

    with pytest.raises(ValidationError):
        ConfirmCashInRequest(
            pin="1234",
            denominations={"1000": -1},
        )


def test_cashier_denomination_models_reject_negative_counts():
    from backend.routes.cashier import (
        InitiateReturnRequest,
        IssueFloatRequest,
        ReceivedCashRequest,
        ReceiveFloatRequest,
        VaultEntryRequest,
    )

    invalid_payloads = [
        lambda: VaultEntryRequest(entry_type="vault_in", denominations={"1000": -1}),
        lambda: IssueFloatRequest(employee_id=7, denominations={"1000": -1}),
        lambda: ReceiveFloatRequest(pin="1234", denominations={"1000": -1}),
        lambda: InitiateReturnRequest(pin="1234", denominations={"1000": -1}),
        lambda: ReceivedCashRequest(denominations={"1000": -1}),
    ]

    for build_request in invalid_payloads:
        with pytest.raises(ValidationError):
            build_request()


def test_cancel_cash_in_rejects_unexpected_denominations_field():
    from backend.routes.cashier import CancelCashInRequest

    with pytest.raises(ValidationError):
        CancelCashInRequest(
            pin="1234",
            denominations={"1000": -1},
        )


def test_cash_out_increases_account_and_decreases_drawer():
    account = _make_account(service_type_id=1)
    tier = _make_tier(1, comm_cash_in=0.0, comm_cash_out=0.0)
    vm, _, account_repo, float_repo = _make_vm(account, tier)
    active_float = SimpleNamespace(id=1, current_balance=50000.0)
    float_repo.get_active_float_for_employee.return_value = active_float

    with patch("repositories.transaction_operation_base.TransactionOperationBase._log"):
        vm.create_cash_out(
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


def test_cash_out_requires_sufficient_float():
    from repositories.cash_float_repository import InsufficientFloatError

    account = _make_account(service_type_id=1)
    tier = _make_tier(1, comm_cash_in=0.0, comm_cash_out=0.0)
    vm, _, account_repo, float_repo = _make_vm(account, tier)
    active_float = SimpleNamespace(id=1, current_balance=400000.0)
    float_repo.get_active_float_for_employee.return_value = active_float

    with pytest.raises(InsufficientFloatError):
        vm.create_cash_out(
            account_id=1,
            amount=500000.0,
            customer_name="A",
            customer_phone="09",
            created_by=7,
            employee_id=7,
        )

    account_repo.increment_balance.assert_not_called()
    vm._txn_repo.create.assert_not_called()


def test_tier_fee_fallback_combines_fixed_and_percentage():
    account = _make_account(service_type_id=1)
    tier = _make_tier(
        1,
        comm_cash_in=0.0,
        comm_cash_out=0.0,
        fee_amount_type="PERCENTAGE",
        fee_amount_cash_in=0.02,
        additional_fee_type="FIXED",
        additional_fee_cash_in_amount=500.0,
    )
    vm, _, _, _ = _make_vm(account, tier)

    customer_fee, additional = vm._resolve_fee_values(
        account, 100000.0, "cash_in", 0.0, 0.0
    )

    assert customer_fee == 2500.0
    assert additional == 500.0


def test_round_fee_mmk_standard():
    from repositories.transaction_operation_base import TransactionOperationBase

    assert TransactionOperationBase.round_fee(120.0) == 100
    assert TransactionOperationBase.round_fee(1020.0) == 1000
    assert TransactionOperationBase.round_fee(20.0) == 100
    assert TransactionOperationBase.round_fee(0.0) == 0

    assert TransactionOperationBase.round_fee(120.1) == 200
    assert TransactionOperationBase.round_fee(130.0) == 200
    assert TransactionOperationBase.round_fee(140.0) == 200
    assert TransactionOperationBase.round_fee(150.0) == 200
    assert TransactionOperationBase.round_fee(199.99) == 200
    assert TransactionOperationBase.round_fee(1020.1) == 1100
    assert TransactionOperationBase.round_fee(50.0) == 100
    assert TransactionOperationBase.round_fee(99.9) == 100
    assert TransactionOperationBase.round_fee(21.0) == 100
