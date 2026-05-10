from typing import Optional

from repositories.transaction_ui_repository import TransactionUiRepository


class HistoryRepository:
    def __init__(self, transaction_repository: TransactionUiRepository) -> None:
        self._transactions = transaction_repository

    def get_accounts(self) -> list[dict]:
        return self._transactions.get_accounts()

    def search_transactions(
        self,
        date_from: str,
        date_to: str,
        transaction_type: Optional[str],
        phone_query: str,
        limit: int = 500,
    ) -> list[dict]:
        txns = self._transactions.get_recent_transactions(limit)
        query = (phone_query or "").lower()
        accounts = self.get_accounts()
        return [
            tx
            for tx in txns
            if date_from <= str(tx.get("created_at", ""))[:10] <= date_to
            and (not transaction_type or tx.get("transaction_type") == transaction_type)
            and self._matches_phone(tx, query, accounts)
        ]

    @staticmethod
    def lookup_account(accounts: list[dict], account_id) -> Optional[dict]:
        if not account_id:
            return None
        for account in accounts:
            if account.get("id") == account_id:
                return account
        return None

    @classmethod
    def _matches_phone(cls, txn: dict, query: str, accounts: list[dict]) -> bool:
        if not query:
            return True
        account = cls.lookup_account(accounts, txn.get("account_id"))
        fields = [
            str(txn.get("customer_phone", "") or "").lower(),
            str(txn.get("customer_name", "") or "").lower(),
            (account.get("phone_number", "") or "").lower() if account else "",
            (account.get("account_name", "") or "").lower() if account else "",
        ]
        return any(query in field for field in fields)
