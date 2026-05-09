import math
from typing import Optional

from models.account import Account
from models.transaction import Transaction
from repositories.account_repository import AccountRepository
from repositories.cash_float_repository import CashFloatRepository, InsufficientFloatError
from repositories.commission_tier_repository import CommissionTierRepository
from repositories.exchange_rate_repository import ExchangeRateRepository
from repositories.service_type_repository import ServiceTypeRepository
from repositories.transaction_repository import TransactionRepository
from services.vault_service import InsufficientDenominationError, VaultService
from backend.database import atomic

# Re-export so routes can import from one place
__all__ = [
    "TransactionViewModel",
    "InsufficientFloatError",
    "InsufficientDenominationError",
]


class TransactionViewModel:

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

    def _get_company_id(self, service_type_id: Optional[int]) -> Optional[int]:
        """Resolve service_type_id → company_id via ServiceTypeRepository."""
        if service_type_id is None:
            return None
        st = self._service_type_repo.get_by_id(service_type_id)
        return st.company_id if st else None

    def _get_tier(self, account: Account, amount: float):
        """Look up commission tier using account.service_type_id directly."""
        return self._tier_repo.get_tier_for_amount(
            service_type_id=account.service_type_id, amount=amount
        )

    def _calc_commission(self, account: Account, amount: float, comm_type: str = "send") -> float:
        tier = self._get_tier(account, amount)
        if tier is None:
            return 0.0
        raw = (tier.comm_deposit if comm_type == "send" else tier.comm_withdraw) or 0.0
        if tier.comm_type == "PERCENTAGE":
            return round(amount * raw, 2)
        return raw

    @staticmethod
    def round_fee(amount: float) -> int:
        return math.ceil(amount / 50) * 50

    def _calc_balance_change(self, account: Account, amount: float, commission: float) -> float:
        # Commission is agent profit tracked separately; balance changes by full amount
        return amount

    def _update_fee_account(self, fee_account_id: Optional[int], fee: float) -> None:
        if fee_account_id is None or fee <= 0:
            return
        acc = self._account_repo.get_by_id(fee_account_id)
        if acc is None:
            return
        new_balance = (acc.balance or 0.0) + fee
        self._account_repo.update_balance(fee_account_id, new_balance)

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
    ) -> Transaction:
        if amount <= 0:
            raise ValueError("Amount must be greater than zero.")
        account = self._account_repo.get_by_id(account_id)
        commission = self._calc_commission(account, amount, "send")
        from_company_id = self._get_company_id(account.service_type_id)

        with atomic():
            new_balance = (account.balance or 0.0) + amount
            self._account_repo.update_balance(account_id, new_balance)
            self._update_fee_account(fee_account_id, customer_fee)
            data = {
                "transaction_type": "deposit",
                "account_id": account_id,
                "customer_name": customer_name,
                "customer_phone": customer_phone,
                "amount": amount,
                "commission_amount": commission,
                "customer_fee": customer_fee,
                "additional_fee_amount": additional_fee_amount,
                "balance_change": amount,
                "currency": "MMK",
                "fee_account_id": fee_account_id,
                "screenshot_path": screenshot_path,
                "note": note,
                "created_by": created_by,
                "from_company_id": from_company_id,
            }
            txn_id = self._txn_repo.create(data)
        return self._txn_repo.get_by_id(txn_id)

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
        if amount <= 0:
            raise ValueError("Amount must be greater than zero.")
        account = self._account_repo.get_by_id(account_id)
        commission = self._calc_commission(account, amount, "receive")
        from_company_id = self._get_company_id(account.service_type_id)

        # ── PRE-VALIDATE float/denominations BEFORE any DB writes ──────────────
        # If validation fails here, no account balance or transaction record has
        # been touched, so the ledger remains consistent.
        active_float = None
        if employee_id is not None:
            active_float = self._float_repo.get_active_float_for_employee(employee_id)
            if denominations and active_float:
                self._vault_service.validate_withdrawal(
                    float_id=active_float.id,
                    employee_id=employee_id,
                    denominations=denominations,
                    amount=amount,
                )
            elif active_float is None:
                raise ValueError("No active float found for this employee.")
            else:
                cur = float(active_float.current_balance or 0)
                if amount > cur:
                    from repositories.cash_float_repository import InsufficientFloatError
                    raise InsufficientFloatError(available=cur, required=amount)

        # ── Writes (validation passed) ─────────────────────────────────────────
        with atomic():
            new_balance = (account.balance or 0.0) - amount
            self._account_repo.update_balance(account_id, new_balance)

            data = {
                "transaction_type": "withdraw",
                "account_id": account_id,
                "customer_name": customer_name,
                "customer_phone": customer_phone,
                "amount": amount,
                "commission_amount": commission,
                "customer_fee": customer_fee,
                "additional_fee_amount": additional_fee_amount,
                "balance_change": -amount,
                "currency": "MMK",
                "fee_account_id": fee_account_id,
                "screenshot_path": screenshot_path,
                "note": note,
                "created_by": created_by,
                "from_company_id": from_company_id,
            }
            txn_id = self._txn_repo.create(data)

            if employee_id is not None:
                if denominations and active_float:
                    self._vault_service.process_withdrawal(
                        float_id=active_float.id,
                        employee_id=employee_id,
                        denominations=denominations,
                        transaction_id=txn_id,
                    )
                else:
                    self._float_repo.deduct_float_balance(employee_id, amount)

            self._update_fee_account(fee_account_id, customer_fee)
        return self._txn_repo.get_by_id(txn_id)

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
        if amount <= 0:
            raise ValueError("Amount must be greater than zero.")
        from_account = self._account_repo.get_by_id(from_account_id)
        to_account = self._account_repo.get_by_id(to_account_id)
        commission = self._calc_commission(from_account, amount, "send")
        balance_change = self._calc_balance_change(from_account, amount, commission)

        from_company_id = self._get_company_id(from_account.service_type_id)
        to_company_id = self._get_company_id(to_account.service_type_id)

        # ── PRE-VALIDATE float/denominations BEFORE any DB writes ──────────────
        active_float = None
        if employee_id is not None:
            active_float = self._float_repo.get_active_float_for_employee(employee_id)
            if denominations and active_float:
                self._vault_service.validate_withdrawal(
                    float_id=active_float.id,
                    employee_id=employee_id,
                    denominations=denominations,
                    amount=amount,
                )
            elif active_float is None:
                raise ValueError("No active float found for this employee.")
            else:
                cur = float(active_float.current_balance or 0)
                if amount > cur:
                    from repositories.cash_float_repository import InsufficientFloatError
                    raise InsufficientFloatError(available=cur, required=amount)

        # ── Writes ─────────────────────────────────────────────────────────────
        with atomic():
            from_balance = (from_account.balance or 0.0) - balance_change
            self._account_repo.update_balance(from_account_id, from_balance)

            to_balance = (to_account.balance or 0.0) + amount
            self._account_repo.update_balance(to_account_id, to_balance)

            data = {
                "transaction_type": "transfer",
                "account_id": from_account_id,
                "to_account_id": to_account_id,
                "amount": amount,
                "commission_amount": commission,
                "customer_fee": customer_fee,
                "additional_fee_amount": additional_fee_amount,
                "balance_change": -balance_change,
                "currency": "MMK",
                "fee_account_id": fee_account_id,
                "screenshot_path": screenshot_path,
                "note": note,
                "created_by": created_by,
                "from_company_id": from_company_id,
                "to_company_id": to_company_id,
            }
            txn_id = self._txn_repo.create(data)

            if employee_id is not None:
                if denominations and active_float:
                    self._vault_service.process_withdrawal(
                        float_id=active_float.id,
                        employee_id=employee_id,
                        denominations=denominations,
                        transaction_id=txn_id,
                    )
                else:
                    self._float_repo.deduct_float_balance(employee_id, amount)

            self._update_fee_account(fee_account_id, customer_fee)
        return self._txn_repo.get_by_id(txn_id)

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
        if amount <= 0:
            raise ValueError("Amount must be greater than zero.")
        rate = self._rate_repo.get_latest("THB", "MMK")
        if rate is None:
            raise ValueError("Exchange rate not set for THB/MMK")

        base_amount = rate.base_amount or 1.0
        if currency == "MMK":
            exchange_rate = rate.sell_rate / base_amount
        else:
            exchange_rate = rate.buy_rate / base_amount

        account = self._account_repo.get_by_id(account_id)
        commission = self._calc_commission(account, amount, "send")
        balance_change = self._calc_balance_change(account, amount, commission)
        from_company_id = self._get_company_id(account.service_type_id)

        # ── PRE-VALIDATE float/denominations BEFORE any DB writes ──────────────
        active_float = None
        if employee_id is not None:
            active_float = self._float_repo.get_active_float_for_employee(employee_id)
            if denominations and active_float:
                self._vault_service.validate_withdrawal(
                    float_id=active_float.id,
                    employee_id=employee_id,
                    denominations=denominations,
                    amount=amount,
                )
            elif active_float is None:
                raise ValueError("No active float found for this employee.")
            else:
                cur = float(active_float.current_balance or 0)
                if amount > cur:
                    from repositories.cash_float_repository import InsufficientFloatError
                    raise InsufficientFloatError(available=cur, required=amount)

        # ── Writes ─────────────────────────────────────────────────────────────
        with atomic():
            new_balance = (account.balance or 0.0) + balance_change
            self._account_repo.update_balance(account_id, new_balance)

            data = {
                "transaction_type": "exchange",
                "account_id": account_id,
                "amount": amount,
                "commission_amount": commission,
                "customer_fee": customer_fee,
                "additional_fee_amount": additional_fee_amount,
                "balance_change": balance_change,
                "currency": currency,
                "exchange_rate": exchange_rate,
                "fee_account_id": fee_account_id,
                "screenshot_path": screenshot_path,
                "note": note,
                "created_by": created_by,
                "from_company_id": from_company_id,
            }
            txn_id = self._txn_repo.create(data)

            if employee_id is not None:
                if denominations and active_float:
                    self._vault_service.process_withdrawal(
                        float_id=active_float.id,
                        employee_id=employee_id,
                        denominations=denominations,
                        transaction_id=txn_id,
                    )
                else:
                    self._float_repo.deduct_float_balance(employee_id, amount)

            self._update_fee_account(fee_account_id, customer_fee)
        return self._txn_repo.get_by_id(txn_id)
