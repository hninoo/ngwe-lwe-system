from typing import Optional

from models.account import Account
from repositories.account_repository import AccountRepository


class AccountViewModel:

    def __init__(
        self,
        account_repo: Optional[AccountRepository] = None,
    ) -> None:
        self._account_repo = account_repo or AccountRepository()

    def get_accounts_by_service(self, service_id: int) -> list[Account]:
        return self._account_repo.get_by_service(service_id)

    def get_all_active(self) -> list[Account]:
        return self._account_repo.get_all_active()

    def update_balance(self, account_id: int, new_balance: float) -> bool:
        return self._account_repo.update_balance(account_id, new_balance)
