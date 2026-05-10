from typing import Optional

from backend.database import atomic
from models.transaction import Transaction
from repositories.account_repository import AccountRepository
from repositories.cash_float_repository import CashFloatRepository, InsufficientFloatError
from repositories.cash_in_repo import CashInRepository
from repositories.cash_out_repo import CashOutRepository
from repositories.commission_tier_repository import CommissionTierRepository
from repositories.exchange_rate_repository import ExchangeRateRepository
from repositories.exchange_repo import ExchangeRepository
from repositories.service_type_repository import ServiceTypeRepository
from repositories.transaction_repository import TransactionRepository
from repositories.transfer_repo import TransferRepository
from services.vault_service import InsufficientDenominationError, VaultService


def _log(*args, **kwargs) -> None:
    """Compatibility hook retained for older tests/imports; repositories own logging now."""
    return None

__all__ = [
    "TransactionViewModel",
    "InsufficientFloatError",
    "InsufficientDenominationError",
]


class TransactionViewModel:
    """Thin application facade over transaction-specific repositories."""

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

        operation_deps = {
            "transaction_repo": self._txn_repo,
            "account_repo": self._account_repo,
            "exchange_rate_repo": self._rate_repo,
            "commission_tier_repo": self._tier_repo,
            "service_type_repo": self._service_type_repo,
            "float_repo": self._float_repo,
            "vault_service": self._vault_service,
        }
        self._cash_in_repo = CashInRepository(**operation_deps)
        self._cash_out_repo = CashOutRepository(**operation_deps)
        self._transfer_repo = TransferRepository(**operation_deps)
        self._exchange_repo = ExchangeRepository(**operation_deps)

    def _calc_commission(self, account, amount: float, comm_type: str = "send") -> float:
        return self._cash_in_repo._calc_commission(account, amount, comm_type)

    def _resolve_fee_values(
        self,
        account,
        amount: float,
        fee_mode: str,
        customer_fee: float,
        additional_fee_amount: float,
    ) -> tuple[float, float]:
        return self._cash_in_repo._resolve_fee_values(
            account, amount, fee_mode, customer_fee, additional_fee_amount
        )

    def create_deposit(
        self,
        account_id: int,
        amount: float,
        customer_name: str,
        customer_phone: str,
        created_by: int,
        screenshot_path: Optional[str] = None,
        customer_fee: float = 0.0,
        additional_fee_amount: float = 0.0,
        fee_account_id: Optional[int] = None,
        note: Optional[str] = None,
        employee_id: Optional[int] = None,
    ) -> Transaction:
        return self._cash_in_repo.create(
            account_id=account_id,
            amount=amount,
            customer_name=customer_name,
            customer_phone=customer_phone,
            created_by=created_by,
            screenshot_path=screenshot_path,
            customer_fee=customer_fee,
            additional_fee_amount=additional_fee_amount,
            fee_account_id=fee_account_id,
            note=note,
            employee_id=employee_id,
        )

    def create_withdraw(
        self,
        account_id: int,
        amount: float,
        customer_name: str,
        customer_phone: str,
        created_by: int,
        screenshot_path: Optional[str] = None,
        customer_fee: float = 0.0,
        additional_fee_amount: float = 0.0,
        fee_account_id: Optional[int] = None,
        note: Optional[str] = None,
        employee_id: Optional[int] = None,
        denominations: Optional[dict] = None,
    ) -> Transaction:
        return self._cash_out_repo.create(
            account_id=account_id,
            amount=amount,
            customer_name=customer_name,
            customer_phone=customer_phone,
            created_by=created_by,
            screenshot_path=screenshot_path,
            customer_fee=customer_fee,
            additional_fee_amount=additional_fee_amount,
            fee_account_id=fee_account_id,
            note=note,
            employee_id=employee_id,
            denominations=denominations,
        )

    def create_transfer(
        self,
        from_account_id: int,
        to_account_id: int,
        amount: float,
        created_by: int,
        screenshot_path: Optional[str] = None,
        customer_fee: float = 0.0,
        additional_fee_amount: float = 0.0,
        fee_account_id: Optional[int] = None,
        note: Optional[str] = None,
        employee_id: Optional[int] = None,
        denominations: Optional[dict] = None,
    ) -> Transaction:
        return self._transfer_repo.create(
            from_account_id=from_account_id,
            to_account_id=to_account_id,
            amount=amount,
            created_by=created_by,
            screenshot_path=screenshot_path,
            customer_fee=customer_fee,
            additional_fee_amount=additional_fee_amount,
            fee_account_id=fee_account_id,
            note=note,
            employee_id=employee_id,
            denominations=denominations,
        )

    def create_exchange(
        self,
        account_id: int,
        amount: float,
        currency: str,
        created_by: int,
        screenshot_path: Optional[str] = None,
        customer_fee: float = 0.0,
        additional_fee_amount: float = 0.0,
        fee_account_id: Optional[int] = None,
        note: Optional[str] = None,
        employee_id: Optional[int] = None,
        denominations: Optional[dict] = None,
    ) -> Transaction:
        return self._exchange_repo.create(
            account_id=account_id,
            amount=amount,
            currency=currency,
            created_by=created_by,
            screenshot_path=screenshot_path,
            customer_fee=customer_fee,
            additional_fee_amount=additional_fee_amount,
            fee_account_id=fee_account_id,
            note=note,
            employee_id=employee_id,
            denominations=denominations,
        )
