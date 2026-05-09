from typing import Optional

from models.account import Account
from repositories.account_repository import AccountRepository


class AccountViewModel:

    def __init__(
        self,
        account_repo: Optional[AccountRepository] = None,
    ) -> None:
        self._account_repo = account_repo or AccountRepository()

    def get_all_active(self) -> list[Account]:
        return self._account_repo.get_all_active()

    def get_accounts_by_company(self, company_id: int) -> list[Account]:
        return self._account_repo.get_by_company(company_id)

    def get_accounts_by_service_type(self, service_type_id: int) -> list[Account]:
        return self._account_repo.get_by_service_type(service_type_id)

    def update_balance(self, *args, **kwargs) -> None:
        raise NotImplementedError(
            "update_balance() is removed. Use POST /accounts/{id}/balance-adjust "
            "for all audited balance mutations."
        )
