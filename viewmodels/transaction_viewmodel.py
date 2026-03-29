import math
from typing import Optional

from models.account import Account
from models.transaction import Transaction
from repositories.account_repository import AccountRepository
from repositories.transaction_repository import TransactionRepository
from repositories.exchange_rate_repository import ExchangeRateRepository
from repositories.service_repository import ServiceRepository


class TransactionViewModel:

    def __init__(
        self,
        transaction_repo: Optional[TransactionRepository] = None,
        account_repo: Optional[AccountRepository] = None,
        exchange_rate_repo: Optional[ExchangeRateRepository] = None,
        service_repo: Optional[ServiceRepository] = None,
    ) -> None:
        self._txn_repo = transaction_repo or TransactionRepository()
        self._account_repo = account_repo or AccountRepository()
        self._rate_repo = exchange_rate_repo or ExchangeRateRepository()
        self._service_repo = service_repo or ServiceRepository()

    def _calc_commission(self, account: Account, amount: float) -> float:
        if account.account_type == "agent":
            return round(amount * (account.commission_rate or 0.0), 2)
        return 0.0

    def _calc_balance_change(self, account: Account, amount: float, commission: float) -> float:
        if account.account_type == "agent":
            return round(amount - commission, 2)
        return amount

    def _get_customer_fee(self, account: Account) -> float:
        service = self._service_repo.get_by_id(account.service_id)
        if service is None:
            return 0.0
        return service.default_customer_fee or 0.0

    @staticmethod
    def round_fee(amount: float) -> int:
        return math.ceil(amount / 50) * 50

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
        fee_account_id: Optional[int] = None,
        note: Optional[str] = None,
    ) -> Transaction:
        account = self._account_repo.get_by_id(account_id)
        commission = self._calc_commission(account, amount)
        balance_change = self._calc_balance_change(account, amount, commission)

        new_balance = (account.balance or 0.0) + balance_change
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
            "balance_change": balance_change,
            "currency": "MMK",
            "fee_account_id": fee_account_id,
            "screenshot_path": screenshot_path,
            "note": note,
            "created_by": created_by,
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
        fee_account_id: Optional[int] = None,
        note: Optional[str] = None,
    ) -> Transaction:
        account = self._account_repo.get_by_id(account_id)
        commission = self._calc_commission(account, amount)
        balance_change = self._calc_balance_change(account, amount, commission)

        new_balance = (account.balance or 0.0) - balance_change
        self._account_repo.update_balance(account_id, new_balance)
        self._update_fee_account(fee_account_id, customer_fee)

        data = {
            "transaction_type": "withdraw",
            "account_id": account_id,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "amount": amount,
            "commission_amount": commission,
            "customer_fee": customer_fee,
            "balance_change": -balance_change,
            "currency": "MMK",
            "fee_account_id": fee_account_id,
            "screenshot_path": screenshot_path,
            "note": note,
            "created_by": created_by,
        }
        txn_id = self._txn_repo.create(data)
        return self._txn_repo.get_by_id(txn_id)

    def create_transfer(
        self,
        from_account_id: int,
        to_account_id: int,
        amount: float,
        created_by: int,
        screenshot_path: Optional[str] = None,
        customer_fee: float = 0.0,
        fee_account_id: Optional[int] = None,
        note: Optional[str] = None,
    ) -> Transaction:
        from_account = self._account_repo.get_by_id(from_account_id)
        commission = self._calc_commission(from_account, amount)
        balance_change = self._calc_balance_change(from_account, amount, commission)

        from_balance = (from_account.balance or 0.0) - balance_change
        self._account_repo.update_balance(from_account_id, from_balance)

        to_account = self._account_repo.get_by_id(to_account_id)
        to_balance = (to_account.balance or 0.0) + amount
        self._account_repo.update_balance(to_account_id, to_balance)
        self._update_fee_account(fee_account_id, customer_fee)

        data = {
            "transaction_type": "transfer",
            "account_id": from_account_id,
            "to_account_id": to_account_id,
            "amount": amount,
            "commission_amount": commission,
            "customer_fee": customer_fee,
            "balance_change": -balance_change,
            "currency": "MMK",
            "fee_account_id": fee_account_id,
            "screenshot_path": screenshot_path,
            "note": note,
            "created_by": created_by,
        }
        txn_id = self._txn_repo.create(data)
        return self._txn_repo.get_by_id(txn_id)

    def create_exchange(
        self,
        account_id: int,
        amount: float,
        currency: str,
        created_by: int,
        screenshot_path: Optional[str] = None,
        customer_fee: float = 0.0,
        fee_account_id: Optional[int] = None,
        note: Optional[str] = None,
    ) -> Transaction:
        rate = self._rate_repo.get_latest("MMK/THB")
        if rate is None:
            raise ValueError("Exchange rate not set for MMK/THB")

        if currency == "MMK":
            exchange_rate = rate.buy_rate
        else:
            exchange_rate = rate.sell_rate

        account = self._account_repo.get_by_id(account_id)
        commission = self._calc_commission(account, amount)
        balance_change = self._calc_balance_change(account, amount, commission)

        new_balance = (account.balance or 0.0) + balance_change
        self._account_repo.update_balance(account_id, new_balance)
        self._update_fee_account(fee_account_id, customer_fee)

        data = {
            "transaction_type": "exchange",
            "account_id": account_id,
            "amount": amount,
            "commission_amount": commission,
            "customer_fee": customer_fee,
            "balance_change": balance_change,
            "currency": currency,
            "exchange_rate": exchange_rate,
            "fee_account_id": fee_account_id,
            "screenshot_path": screenshot_path,
            "note": note,
            "created_by": created_by,
        }
        txn_id = self._txn_repo.create(data)
        return self._txn_repo.get_by_id(txn_id)
