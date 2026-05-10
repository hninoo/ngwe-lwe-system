from typing import Optional

from services.api_client import ApiClient


class VaultRepository:
    """Employee-facing API wrapper for the current user's cash vault/float."""

    def __init__(self, api: ApiClient) -> None:
        self._api = api

    @property
    def api(self) -> ApiClient:
        return self._api

    def get_my_floats(self) -> list[dict]:
        user_id = (self._api.user or {}).get("id") or (self._api.user or {}).get("user_id")
        floats = self._api.get_floats()
        if user_id is None:
            return []
        return [f for f in floats if f.get("employee_id") == user_id]

    def get_cash_affecting_transactions(self, limit: int = 100) -> list[dict]:
        user_id = (self._api.user or {}).get("id") or (self._api.user or {}).get("user_id")
        txns = self._api.get_recent_transactions(limit=limit)
        cash_types = {"cash_in", "cash_out", "transfer", "exchange"}
        results = []
        for txn in txns:
            txn_type = (txn.get("transaction_type") or txn.get("txn_type") or txn.get("type") or "").lower()
            created_by = txn.get("created_by")
            if txn_type not in cash_types:
                continue
            if user_id is not None and created_by not in (None, user_id):
                continue
            results.append(txn)
        return results

    def fetch_vault_history(self, limit: int = 100) -> dict:
        """Return the synchronized data needed by the employee vault table."""
        floats = self.get_my_floats()
        return {
            "floats": floats,
            "transactions": self.get_cash_affecting_transactions(limit=limit),
        }

    def get_active_float(self) -> Optional[dict]:
        active = [f for f in self.get_my_floats() if f.get("status") == "ACTIVE"]
        if not active:
            return None
        return max(active, key=lambda f: f.get("received_at") or f.get("created_at") or "")

    def get_pending_float(self) -> Optional[dict]:
        pending = [f for f in self.get_my_floats() if f.get("status") == "PENDING_RECEIPT"]
        if not pending:
            return None
        return max(pending, key=lambda f: f.get("created_at") or "")

    def get_pending_reconciliation_float(self) -> Optional[dict]:
        pending = [f for f in self.get_my_floats() if f.get("status") == "PENDING_RECONCILIATION"]
        if not pending:
            return None
        return max(pending, key=lambda f: f.get("received_at") or f.get("created_at") or "")

    def get_float_balance(self, float_id: int) -> dict:
        return self._api.get_float_denomination_balance(float_id)

    def receive_float(
        self,
        float_id: int,
        pin: str,
        denominations: Optional[dict[str, int]] = None,
    ) -> dict:
        """Confirm a pending float receipt through the backend PIN flow."""
        if denominations is None:
            cash_float = self._api.get_float(float_id)
            denominations = {
                str(d["denomination"]): int(d["quantity"])
                for d in cash_float.get("denominations", [])
                if int(d.get("quantity", 0)) > 0
            }
        return self._api.receive_float(float_id, pin, denominations)

    def confirm_float_reception(self, pin: str, float_id: int) -> dict:
        return self.receive_float(float_id, pin)

    def confirm_receipt(self, float_id: int, pin: str) -> dict:
        return self.receive_float(float_id, pin)

    def return_float(
        self,
        float_id: int,
        pin: str,
        denominations: dict[str, int],
        note: str | None = None,
    ) -> dict:
        return self._api.initiate_float_return(float_id, denominations, note=note, pin=pin)

    def return_cash(
        self,
        float_id: int,
        pin: str,
        denominations: dict[str, int],
        note: str | None = None,
    ) -> dict:
        """Request cash return; backend verifies PIN and moves status to PENDING_RECONCILIATION."""
        return self.return_float(float_id, pin, denominations, note=note)

    def request_cash_return(
        self,
        pin: str,
        denominations: dict[str, int],
        note: str | None = None,
        float_id: Optional[int] = None,
    ) -> dict:
        active_float = {"id": float_id} if float_id is not None else self.get_active_float()
        if not active_float:
            raise ValueError("No active vault cash to return.")
        return self.return_cash(active_float["id"], pin, denominations, note=note)
