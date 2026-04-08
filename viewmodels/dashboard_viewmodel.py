from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Optional

MMT = timezone(timedelta(hours=6, minutes=30))  # Myanmar Time (Yangon)

from models.account import Account
from models.transaction import Transaction
from repositories.account_repository import AccountRepository
from repositories.transaction_repository import TransactionRepository


@dataclass
class DaySummary:
    total_deposit: float = 0.0
    total_withdraw: float = 0.0
    total_transfer: float = 0.0
    total_exchange: float = 0.0
    total_commission: float = 0.0
    total_customer_fees: float = 0.0
    transaction_count: int = 0


class DashboardViewModel:

    def __init__(
        self,
        account_repo: Optional[AccountRepository] = None,
        transaction_repo: Optional[TransactionRepository] = None,
    ) -> None:
        self._account_repo = account_repo or AccountRepository()
        self._transaction_repo = transaction_repo or TransactionRepository()

    def get_all_accounts(self) -> list[Account]:
        return self._account_repo.get_all_active()

    def get_recent_transactions(self, limit: int = 20) -> list[Transaction]:
        return self._transaction_repo.get_recent(limit)

    def get_today_summary(self) -> DaySummary:
        today = datetime.now(MMT).date()
        start = datetime.combine(today, datetime.min.time())
        end = datetime.combine(today, datetime.max.time())
        transactions = self._transaction_repo.get_by_date_range(start, end)
        return self._build_summary(transactions)

    def _build_summary(self, transactions: list[Transaction]) -> DaySummary:
        summary = DaySummary()
        summary.transaction_count = len(transactions)

        for txn in transactions:
            amount = txn.amount or 0.0
            summary.total_commission += txn.commission_amount or 0.0
            summary.total_customer_fees += txn.customer_fee or 0.0

            if txn.transaction_type == "deposit":
                summary.total_deposit += amount
            elif txn.transaction_type == "withdraw":
                summary.total_withdraw += amount
            elif txn.transaction_type == "transfer":
                summary.total_transfer += amount
            elif txn.transaction_type == "exchange":
                summary.total_exchange += amount

        return summary
