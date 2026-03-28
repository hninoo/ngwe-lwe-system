import os
from typing import Any, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = os.getenv("API_BASE_URL", "http://localhost:8000")


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
        resp = requests.get(f"{BASE_URL}{path}", headers=self._headers(), params=params)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, data: Optional[dict] = None) -> Any:
        resp = requests.post(f"{BASE_URL}{path}", headers=self._headers(), json=data)
        resp.raise_for_status()
        return resp.json()

    def _patch(self, path: str, data: Optional[dict] = None) -> Any:
        resp = requests.patch(f"{BASE_URL}{path}", headers=self._headers(), json=data)
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
        screenshot_path: str,
        note: Optional[str] = None,
    ) -> dict:
        return self._post("/transactions/deposit", {
            "account_id": account_id,
            "amount": amount,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "screenshot_path": screenshot_path,
            "note": note,
        })

    def create_withdraw(
        self,
        account_id: int,
        amount: float,
        customer_name: str,
        customer_phone: str,
        screenshot_path: str,
        note: Optional[str] = None,
    ) -> dict:
        return self._post("/transactions/withdraw", {
            "account_id": account_id,
            "amount": amount,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "screenshot_path": screenshot_path,
            "note": note,
        })

    def create_transfer(
        self,
        from_account_id: int,
        to_account_id: int,
        amount: float,
        screenshot_path: str,
        note: Optional[str] = None,
    ) -> dict:
        return self._post("/transactions/transfer", {
            "from_account_id": from_account_id,
            "to_account_id": to_account_id,
            "amount": amount,
            "screenshot_path": screenshot_path,
            "note": note,
        })

    def create_exchange(
        self,
        account_id: int,
        amount: float,
        currency: str,
        screenshot_path: str,
        note: Optional[str] = None,
    ) -> dict:
        return self._post("/transactions/exchange", {
            "account_id": account_id,
            "amount": amount,
            "currency": currency,
            "screenshot_path": screenshot_path,
            "note": note,
        })

    def get_recent_transactions(self, limit: int = 20) -> list[dict]:
        return self._get("/transactions/recent", params={"limit": limit})

    # ── Dashboard ──

    def get_dashboard_summary(self) -> dict:
        return self._get("/dashboard/summary")

    def get_dashboard_accounts(self) -> list[dict]:
        return self._get("/dashboard/accounts")
