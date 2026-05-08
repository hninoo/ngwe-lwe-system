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

    def _get_raw(self, path: str) -> bytes:
        """Return raw response bytes (for logo/binary endpoints)."""
        resp = requests.get(f"{BASE_URL}{path}", headers=self._headers(), timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.content

    def _post(self, path: str, data: Optional[dict] = None) -> Any:
        resp = requests.post(f"{BASE_URL}{path}", headers=self._headers(), json=data, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.json()

    def _post_multipart(self, path: str, file_bytes: bytes, mime_type: str, field: str = "file") -> Any:
        """Upload a binary file via multipart/form-data."""
        resp = requests.post(
            f"{BASE_URL}{path}",
            headers=self._headers(),
            files={field: ("logo", file_bytes, mime_type)},
            timeout=REQUEST_TIMEOUT,
        )
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

    # ── Companies ──

    def get_companies(self) -> list[dict]:
        """GET /companies/ — list all active companies."""
        return self._get("/companies/")

    def get_company(self, company_id: int) -> dict:
        """GET /companies/{id} — single company detail."""
        return self._get(f"/companies/{company_id}")

    def create_company(self, name: str, category: str) -> dict:
        """POST /companies/ — create a new company (owner only)."""
        return self._post("/companies/", {"name": name, "category": category})

    def update_company(self, company_id: int, data: dict) -> dict:
        """PATCH /companies/{id} — update company fields (owner only)."""
        return self._patch(f"/companies/{company_id}", data)

    # ── Company Logos ──

    def get_logo(self, company_id: int) -> bytes:
        """GET /companies/{id}/logo — returns raw image bytes."""
        return self._get_raw(f"/companies/{company_id}/logo")

    def upload_logo(self, company_id: int, file_bytes: bytes, mime_type: str) -> dict:
        """POST /companies/{id}/logo — upload logo file (owner only)."""
        return self._post_multipart(f"/companies/{company_id}/logo", file_bytes, mime_type)

    # ── ServiceTypes ──

    def get_service_types(self, company_id: int) -> list[dict]:
        """GET /companies/{id}/service-types — list service types for a company."""
        return self._get(f"/companies/{company_id}/service-types")

    def create_service_type(self, company_id: int, name: str, operation: str) -> dict:
        """POST /companies/{id}/service-types — create service type (owner only)."""
        return self._post(f"/companies/{company_id}/service-types", {"name": name, "operation": operation})

    def update_service_type(self, service_type_id: int, data: dict) -> dict:
        """PATCH /service-types/{id} — update service type (owner only)."""
        return self._patch(f"/service-types/{service_type_id}", data)

    # ── Accounts ──

    def get_accounts(
        self,
        company_id: Optional[int] = None,
        service_type_id: Optional[int] = None,
    ) -> list[dict]:
        """GET /accounts/ with optional company_id and/or service_type_id filters."""
        params: dict = {}
        if company_id is not None:
            params["company_id"] = company_id
        if service_type_id is not None:
            params["service_type_id"] = service_type_id
        return self._get("/accounts/", params=params or None)

    def get_accounts_by_company(self, company_id: int) -> list[dict]:
        """GET /accounts/?company_id=<id>"""
        return self._get("/accounts/", params={"company_id": company_id})

    def get_account(self, account_id: int) -> dict:
        return self._get(f"/accounts/{account_id}")

    def create_account(
        self,
        service_type_id: int,
        account_name: str,
        phone_number: str,
        balance: float = 0.0,
        is_fee_account: bool = False,
    ) -> dict:
        return self._post("/accounts/", {
            "service_type_id": service_type_id,
            "account_name": account_name,
            "phone_number": phone_number,
            "balance": balance,
            "is_fee_account": is_fee_account,
        })

    def update_account(self, account_id: int, data: dict) -> dict:
        return self._patch(f"/accounts/{account_id}", data)

    def adjust_account_balance(self, account_id: int, amount: float, remark: str) -> dict:
        return self._post(f"/accounts/{account_id}/balance-adjust", {
            "amount": amount,
            "remark": remark,
        })

    def delete_account(self, account_id: int) -> dict:
        resp = requests.delete(
            f"{BASE_URL}/accounts/{account_id}",
            headers=self._headers(), timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

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

    def get_all_transactions(
        self,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        txn_type: Optional[str] = None,
        account_id: Optional[int] = None,
        limit: int = 200,
    ) -> list[dict]:
        params: dict = {"limit": limit}
        if date_from:
            params["date_from"] = date_from
        if date_to:
            params["date_to"] = date_to
        if txn_type:
            params["txn_type"] = txn_type
        if account_id is not None:
            params["account_id"] = account_id
        return self._get("/transactions/", params=params)

    def delete_transaction(self, txn_id: int) -> dict:
        resp = requests.delete(
            f"{BASE_URL}/transactions/{txn_id}",
            headers=self._headers(), timeout=REQUEST_TIMEOUT,
        )
        resp.raise_for_status()
        return resp.json()

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

    def update_user(self, user_id: int, data: dict) -> dict:
        return self._patch(f"/users/{user_id}", data)

    def toggle_user_active(self, user_id: int, is_active: bool) -> dict:
        return self._patch(f"/users/{user_id}/active", {"is_active": is_active})

    def reset_user_password(self, user_id: int, new_password: str) -> dict:
        return self._post(f"/users/{user_id}/reset-password", {"new_password": new_password})

    def change_password(self, old_password: str, new_password: str) -> dict:
        return self._post("/users/change-password", {
            "old_password": old_password,
            "new_password": new_password,
        })

    def set_user_pin(self, user_id: int, pin: str) -> dict:
        return self._post(f"/users/{user_id}/pin", {"pin": pin})

    # ── Activity Logs ──

    def get_activity_logs(
        self,
        user_id: Optional[int] = None,
        entity_type: Optional[str] = None,
        action: Optional[str] = None,
        date: Optional[str] = None,
        limit: int = 200,
    ) -> list[dict]:
        params: dict = {"limit": limit}
        if user_id is not None:
            params["user_id"] = user_id
        if entity_type:
            params["entity_type"] = entity_type
        if action:
            params["action"] = action
        if date:
            params["date"] = date
        return self._get("/activity-logs/", params=params)

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

    # ── Reconciliation ──

    def get_reconciliation_snapshot(self) -> dict:
        """GET /reconciliation/current — live today's snapshot."""
        return self._get("/reconciliation/current")

    def close_day(self, notes: Optional[str] = None) -> dict:
        """POST /reconciliation/close-day — snapshot + close all active floats."""
        return self._post("/reconciliation/close-day", {"notes": notes})

    def get_reconciliation_history(self, limit: int = 30) -> list[dict]:
        """GET /reconciliation/history — recent daily reconciliation records."""
        return self._get("/reconciliation/history", params={"limit": limit})

    # ── Commission Tiers ──

    def get_commission_tiers(self, service_type_id: int) -> list[dict]:
        """GET /commission-tiers/?service_type_id=<id>"""
        return self._get("/commission-tiers/", params={"service_type_id": service_type_id})

    def lookup_tier(self, service_type_id: int, amount: float) -> dict:
        """GET /commission-tiers/lookup?service_type_id=<id>&amount=<amount>"""
        return self._get("/commission-tiers/lookup", params={
            "service_type_id": service_type_id, "amount": amount,
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
