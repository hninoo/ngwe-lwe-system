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

    def get_transactions_by_date(self, date: str) -> list[dict]:
        """Return all transactions for a given date (YYYY-MM-DD)."""
        return self._get("/transactions/by-date", params={"date": date})

    def approve_transaction(self, txn_id: int, denominations: dict, note: str | None = None) -> dict:
        return self._post(f"/cashier/transactions/{txn_id}/approve", {
            "denominations": denominations,
            "note": note,
        })

    # ── Dashboard ──

    def get_dashboard_summary(self) -> dict:
        return self._get("/dashboard/summary")

    def get_dashboard_accounts(self) -> list[dict]:
        return self._get("/dashboard/accounts")

    # ── Users ──

    def get_users(self) -> list[dict]:
        return self._get("/users/")

    def create_user(
        self,
        username: str,
        password: str,
        full_name: str,
        role: str = "employee",
    ) -> dict:
        return self._post("/users/", {
            "username": username,
            "password": password,
            "full_name": full_name,
            "role": role,
        })

    def toggle_user_active(self, user_id: int, is_active: bool) -> dict:
        return self._patch(f"/users/{user_id}/active", {"is_active": is_active})

    def change_password(self, old_password: str, new_password: str) -> dict:
        return self._post("/users/change-password", {
            "old_password": old_password,
            "new_password": new_password,
        })

    def set_user_pin(self, user_id: int, pin: str) -> dict:
        return self._post(f"/users/{user_id}/pin", {"pin": pin})

    # ── Exchange Rates ──

    def get_exchange_rate(self, base: str = "THB", quote: str = "MMK") -> dict:
        return self._get("/exchange-rates/latest", params={"base": base, "quote": quote})

    def update_exchange_rate(
        self,
        buy_rate: float,
        sell_rate: float,
        base_amount: float = 1.0,
        base: str = "THB",
        quote: str = "MMK",
    ) -> dict:
        return self._post("/exchange-rates/", {
            "base_currency": base,
            "quote_currency": quote,
            "base_amount": base_amount,
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

    # ── Cashier ──

    def get_vault(self) -> dict:
        """Get current vault balance (cashier only)."""
        return self._get("/cashier/vault")

    def record_vault_entry(
        self,
        entry_type: str,
        denominations: dict[str, int],
        note: Optional[str] = None,
    ) -> dict:
        """Record a vault_in or adjustment entry."""
        return self._post("/cashier/vault/entry", {
            "entry_type": entry_type,
            "denominations": denominations,
            "note": note,
        })

    def get_vault_logs(self) -> list[dict]:
        """Get recent vault denomination logs."""
        return self._get("/cashier/vault/logs")

    def get_floats(self) -> list[dict]:
        """Get float assignments (cashier sees all, employee sees own)."""
        return self._get("/cashier/floats")

    def issue_float(
        self,
        employee_id: int,
        denominations: dict[str, int],
        note: Optional[str] = None,
    ) -> dict:
        """Issue a float to an employee (cashier only)."""
        return self._post("/cashier/floats", {
            "employee_id": employee_id,
            "denominations": denominations,
            "note": note,
        })

    def get_my_pending_float(self) -> Optional[dict]:
        """Get the current employee's pending float. Returns None if not found."""
        try:
            return self._get("/cashier/floats/my-pending")
        except requests.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return None
            raise

    def get_float(self, float_id: int) -> dict:
        """Get a specific float by ID."""
        return self._get(f"/cashier/floats/{float_id}")

    def receive_float(self, float_id: int, pin: str) -> dict:
        """Employee confirms receipt of float with PIN."""
        return self._post(f"/cashier/floats/{float_id}/receive", {"pin": pin})

    def close_float(
        self,
        float_id: int,
        closing_denominations: dict[str, int],
        note: Optional[str] = None,
    ) -> dict:
        """Close a float with denomination return."""
        return self._post(f"/cashier/floats/{float_id}/close", {
            "closing_denominations": closing_denominations,
            "note": note,
        })
