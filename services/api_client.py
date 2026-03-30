import os
from typing import Any, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")
REQUEST_TIMEOUT = 10  # seconds


class ApiClient:

    def __init__(self) -> None:
        self._token: Optional[str] = None
        self._user: Optional[dict] = None

    @property
    def token(self) -> Optional[str]:
        return self._token

    @property
    def user(self) -> Optional[dict]:
        return self._user

    @property
    def is_authenticated(self) -> bool:
        return self._token is not None

    def _headers(self) -> dict[str, str]:
        if self._token is None:
            return {}
        return {"Authorization": f"Bearer {self._token}"}

    def _get(self, path: str, params: Optional[dict] = None) -> Any:
        resp = requests.get(f"{BASE_URL}{path}", headers=self._headers(), params=params, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, data: Optional[dict] = None) -> Any:
        resp = requests.post(f"{BASE_URL}{path}", headers=self._headers(), json=data, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def _patch(self, path: str, data: Optional[dict] = None) -> Any:
        resp = requests.patch(f"{BASE_URL}{path}", headers=self._headers(), json=data, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    # ── Auth ──

    def login(self, username: str, password: str) -> dict:
        result = self._post("/auth/login", {"username": username, "password": password})
        self._token = result["token"]
        self._user = result["user"]
        return result

    def logout(self) -> None:
        if self._token:
            self._post("/auth/logout")
        self._token = None
        self._user = None

    # ── Services ──

    def get_services(self) -> list[dict]:
        return self._get("/services/")

    # ── Accounts ──

    def get_accounts(self, service_id: Optional[int] = None) -> list[dict]:
        params = {"service_id": service_id} if service_id else None
        return self._get("/accounts/", params=params)

    def get_account(self, account_id: int) -> dict:
        return self._get(f"/accounts/{account_id}")

    # ── Transactions ──

    def create_deposit(
        self,
        account_id: int,
        amount: float,
        customer_name: str,
        customer_phone: str,
        screenshot_path: Optional[str] = None,
        customer_fee: float = 0.0,
        additional_fee_amount: float = 0.0,
        fee_account_id: Optional[int] = None,
        note: Optional[str] = None,
    ) -> dict:
        return self._post("/transactions/deposit", {
            "account_id": account_id,
            "amount": amount,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "screenshot_path": screenshot_path,
            "customer_fee": customer_fee,
            "additional_fee_amount": additional_fee_amount,
            "fee_account_id": fee_account_id,
            "note": note,
        })

    def create_withdraw(
        self,
        account_id: int,
        amount: float,
        customer_name: str,
        customer_phone: str,
        screenshot_path: Optional[str] = None,
        customer_fee: float = 0.0,
        additional_fee_amount: float = 0.0,
        fee_account_id: Optional[int] = None,
        note: Optional[str] = None,
    ) -> dict:
        return self._post("/transactions/withdraw", {
            "account_id": account_id,
            "amount": amount,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "screenshot_path": screenshot_path,
            "customer_fee": customer_fee,
            "additional_fee_amount": additional_fee_amount,
            "fee_account_id": fee_account_id,
            "note": note,
        })

    def create_transfer(
        self,
        from_account_id: int,
        to_account_id: int,
        amount: float,
        screenshot_path: Optional[str] = None,
        customer_fee: float = 0.0,
        additional_fee_amount: float = 0.0,
        fee_account_id: Optional[int] = None,
        note: Optional[str] = None,
    ) -> dict:
        return self._post("/transactions/transfer", {
            "from_account_id": from_account_id,
            "to_account_id": to_account_id,
            "amount": amount,
            "screenshot_path": screenshot_path,
            "customer_fee": customer_fee,
            "additional_fee_amount": additional_fee_amount,
            "fee_account_id": fee_account_id,
            "note": note,
        })

    def create_exchange(
        self,
        account_id: int,
        amount: float,
        currency: str,
        screenshot_path: Optional[str] = None,
        customer_fee: float = 0.0,
        additional_fee_amount: float = 0.0,
        fee_account_id: Optional[int] = None,
        note: Optional[str] = None,
    ) -> dict:
        return self._post("/transactions/exchange", {
            "account_id": account_id,
            "amount": amount,
            "currency": currency,
            "screenshot_path": screenshot_path,
            "customer_fee": customer_fee,
            "additional_fee_amount": additional_fee_amount,
            "fee_account_id": fee_account_id,
            "note": note,
        })

    def get_recent_transactions(self, limit: int = 20) -> list[dict]:
        return self._get("/transactions/recent", params={"limit": limit})

    # ── Dashboard ──

    def get_dashboard_summary(self) -> dict:
        return self._get("/dashboard/summary")

    def get_dashboard_accounts(self) -> list[dict]:
        return self._get("/dashboard/accounts")

    # ── Users ──

    def get_users(self) -> list[dict]:
        return self._get("/users/")

    def create_user(self, username: str, password: str, full_name: str) -> dict:
        return self._post("/users/", {
            "username": username,
            "password": password,
            "full_name": full_name,
        })

    def toggle_user_active(self, user_id: int, is_active: bool) -> dict:
        return self._patch(f"/users/{user_id}/active", {"is_active": is_active})

    def change_password(self, old_password: str, new_password: str) -> dict:
        return self._post("/users/change-password", {
            "old_password": old_password,
            "new_password": new_password,
        })

    # ── Exchange Rates ──

    def get_exchange_rate(self, pair: str = "MMK/THB") -> dict:
        return self._get("/exchange-rates/latest", params={"pair": pair})

    def update_exchange_rate(self, buy_rate: float, sell_rate: float, pair: str = "MMK/THB") -> dict:
        return self._post("/exchange-rates/", {
            "currency_pair": pair,
            "buy_rate": buy_rate,
            "sell_rate": sell_rate,
        })

    # ── Reports ──

    def get_daily_report(self, date: str) -> dict:
        return self._get("/reports/daily", params={"date": date})

    # ── Commission Tiers ──

    def get_commission_tiers(self, service_type: str, account_type: str) -> list[dict]:
        return self._get("/commission-tiers/", params={
            "service_type": service_type, "account_type": account_type,
        })

    def lookup_tier(self, service_type: str, account_type: str, amount: float) -> dict:
        return self._get("/commission-tiers/lookup", params={
            "service_type": service_type, "account_type": account_type, "amount": amount,
        })

    def create_commission_tier(self, data: dict) -> dict:
        return self._post("/commission-tiers/", data)

    def update_commission_tier(self, tier_id: int, data: dict) -> dict:
        resp = requests.put(
            f"{BASE_URL}/commission-tiers/{tier_id}",
            headers=self._headers(), json=data, timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

    def delete_commission_tier(self, tier_id: int) -> dict:
        resp = requests.delete(
            f"{BASE_URL}/commission-tiers/{tier_id}",
            headers=self._headers(), timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()
