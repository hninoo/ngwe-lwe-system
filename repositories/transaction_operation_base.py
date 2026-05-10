import json
import math
import sqlite3
from typing import Optional

from backend.database import atomic, get_cursor
from models.account import Account
from repositories.account_repository import AccountRepository
from repositories.cash_float_repository import CashFloatRepository, InsufficientFloatError
from repositories.commission_tier_repository import CommissionTierRepository
from repositories.exchange_rate_repository import ExchangeRateRepository
from repositories.service_type_repository import ServiceTypeRepository
from repositories.transaction_repository import TransactionRepository
from services.vault_service import VaultService


class TransactionOperationBase:
    """Shared, UI-agnostic business rules for transaction operation repositories."""

    def __init__(
        self,
        transaction_repo: Optional[TransactionRepository] = None,
        account_repo: Optional[AccountRepository] = None,
        exchange_rate_repo: Optional[ExchangeRateRepository] = None,
        commission_tier_repo: Optional[CommissionTierRepository] = None,
        service_type_repo: Optional[ServiceTypeRepository] = None,
        float_repo: Optional[CashFloatRepository] = None,
        vault_service: Optional[VaultService] = None,
    ) -> None:
        self._txn_repo = transaction_repo or TransactionRepository()
        self._account_repo = account_repo or AccountRepository()
        self._rate_repo = exchange_rate_repo or ExchangeRateRepository()
        self._tier_repo = commission_tier_repo or CommissionTierRepository()
        self._service_type_repo = service_type_repo or ServiceTypeRepository()
        self._float_repo = float_repo or CashFloatRepository()
        self._vault_service = vault_service or VaultService(float_repo=self._float_repo)

    def _validate_amount(self, amount: float) -> None:
        if amount <= 0:
            raise ValueError("Amount must be greater than zero.")

    def _get_account(self, account_id: int) -> Account:
        account = self._account_repo.get_by_id(account_id)
        if account is None:
            raise ValueError(f"Account #{account_id} not found.")
        return account

    def _get_company_id(self, service_type_id: Optional[int]) -> Optional[int]:
        if service_type_id is None:
            return None
        service_type = self._service_type_repo.get_by_id(service_type_id)
        return service_type.company_id if service_type else None

    def _get_tier(self, account: Account, amount: float):
        return self._tier_repo.get_tier_for_amount(
            service_type_id=account.service_type_id,
            amount=amount,
        )

    def _calc_amount_by_type(self, amount: float, value: float, value_type: str) -> float:
        if (value_type or "FIXED").upper() == "PERCENTAGE":
            return round(amount * (value or 0.0), 2)
        return value or 0.0

    def _calc_commission(self, account: Account, amount: float, comm_type: str) -> float:
        tier = self._get_tier(account, amount)
        if tier is None:
            return 0.0
        raw = (tier.comm_deposit if comm_type == "send" else tier.comm_withdraw) or 0.0
        if tier.comm_type == "PERCENTAGE":
            return round(amount * raw, 2)
        return raw

    def _resolve_fee_values(
        self,
        account: Account,
        amount: float,
        fee_mode: str,
        customer_fee: float,
        additional_fee_amount: float,
    ) -> tuple[float, float]:
        if customer_fee > 0 or additional_fee_amount > 0:
            return customer_fee, additional_fee_amount
        tier = self._get_tier(account, amount)
        if tier is None:
            return 0.0, 0.0
        if fee_mode == "withdraw":
            base_raw = tier.fee_amount_withdraw or 0.0
            add_raw = tier.additional_fee_withdraw_amount or 0.0
        else:
            base_raw = tier.fee_amount_deposit or 0.0
            add_raw = tier.additional_fee_deposit_amount or 0.0
        base_fee = self._calc_amount_by_type(amount, base_raw, tier.fee_amount_type)
        additional = self._calc_amount_by_type(amount, add_raw, tier.additional_fee_type)
        return base_fee + additional, additional

    def _validate_employee_float(
        self,
        employee_id: Optional[int],
        amount: float,
        denominations: Optional[dict],
    ):
        if employee_id is None:
            return None
        active_float = self._float_repo.get_active_float_for_employee(employee_id)
        if active_float is None:
            raise ValueError("Vault Insufficient: no active vault found for this employee.")
        if denominations:
            self._vault_service.validate_withdrawal(
                float_id=active_float.id,
                employee_id=employee_id,
                denominations=denominations,
                amount=amount,
            )
            return active_float
        current = float(active_float.current_balance or 0)
        if amount > current:
            raise InsufficientFloatError(available=current, required=amount)
        return active_float

    def _process_employee_withdrawal(
        self,
        employee_id: Optional[int],
        amount: float,
        denominations: Optional[dict],
        active_float,
        transaction_id: int,
    ) -> None:
        if employee_id is None:
            return
        if denominations and active_float:
            self._vault_service.process_withdrawal(
                float_id=active_float.id,
                employee_id=employee_id,
                denominations=denominations,
                transaction_id=transaction_id,
            )
        else:
            self._float_repo.deduct_float_balance(employee_id, amount)

    def _update_fee_account(self, fee_account_id: Optional[int], fee: float) -> None:
        if fee_account_id is not None and fee > 0:
            self._account_repo.increment_balance(fee_account_id, fee)

    def _log(self, user_id: int, action: str, entity_id: int, details: dict) -> None:
        try:
            with get_cursor(commit=True) as cur:
                cur.execute(
                    "INSERT INTO activity_logs (user_id, action, entity_type, entity_id, details) "
                    "VALUES (?, ?, 'transaction', ?, ?)",
                    (user_id, action, entity_id, json.dumps(details, default=str)),
                )
        except sqlite3.OperationalError as exc:
            if "no such table: activity_logs" not in str(exc):
                raise

    @staticmethod
    def round_fee(amount: float) -> int:
        return math.ceil(amount / 50) * 50

    @staticmethod
    def atomic():
        return atomic()
