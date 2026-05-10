from typing import Optional

from services.api_client import ApiClient


class TransactionUiRepository:
    """Client-side repository facade for transaction views."""

    def __init__(self, api_client: ApiClient) -> None:
        self._api = api_client

    @property
    def current_user(self) -> dict:
        return self._api.user or {}

    def get_companies(self) -> list[dict]:
        return self._api.get_companies()

    def get_logo(self, company_id: int) -> bytes:
        return self._api.get_logo(company_id)

    def get_accounts(self, service_type_id: Optional[int] = None) -> list[dict]:
        return self._api.get_accounts(service_type_id=service_type_id)

    def get_account(self, account_id: int) -> dict:
        return self._api.get_account(account_id)

    def get_service_types(self, company_id: int) -> list[dict]:
        return self._api.get_service_types(company_id)

    def get_recent_transactions(self, limit: int = 50) -> list[dict]:
        return self._api.get_recent_transactions(limit)

    def get_floats(self) -> list[dict]:
        return self._api.get_floats()

    def lookup_tier(self, service_type_id: int, amount: float) -> dict:
        return self._api.lookup_tier(service_type_id, amount)

    def create_cash_in(self, **payload) -> dict:
        return self._api.create_cash_in(**payload)

    def create_cash_out(self, **payload) -> dict:
        return self._api.create_cash_out(**payload)

    def create_transfer(self, **payload) -> dict:
        return self._api.create_transfer(**payload)

    def create_exchange(self, **payload) -> dict:
        return self._api.create_exchange(**payload)

    def change_password(self, old_password: str, new_password: str) -> dict:
        return self._api.change_password(old_password, new_password)

    def set_user_pin(self, user_id: int, pin: str) -> dict:
        return self._api.set_user_pin(user_id, pin)

    def change_pin(self, current_pin: str, new_pin: str) -> dict:
        return self._api.change_pin(current_pin, new_pin)
