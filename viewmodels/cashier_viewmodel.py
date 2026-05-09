from typing import Optional

from models.cash_float import CashFloat
from models.cash_denomination_log import CashDenominationLog
from repositories.cash_denomination_repository import CashDenominationRepository
from repositories.cash_float_repository import CashFloatRepository
from repositories.user_repository import UserRepository


class CashierViewModel:

    def __init__(
        self,
        float_repo: Optional[CashFloatRepository] = None,
        denom_repo: Optional[CashDenominationRepository] = None,
        user_repo: Optional[UserRepository] = None,
    ) -> None:
        self._float_repo = float_repo or CashFloatRepository()
        self._denom_repo = denom_repo or CashDenominationRepository()
        self._user_repo = user_repo or UserRepository()

    def get_vault_state(self) -> dict:
        """Returns {balance: {denom: qty}, total: float}."""
        balance = self._denom_repo.get_vault_balance()
        total = sum(d * q for d, q in balance.items())
        return {"balance": balance, "total": total}

    def get_available_balance(self) -> dict[int, int]:
        """Returns available balance (vault minus pending reserved)."""
        return self._denom_repo.get_available_balance()

    def record_vault_entry(
        self,
        denominations: dict[int, int],
        entry_type: str,
        cashier_id: int,
        note: Optional[str] = None,
    ) -> None:
        """Record a vault_in or adjustment entry."""
        allowed = ("vault_in", "adjustment")
        if entry_type not in allowed:
            raise ValueError(f"entry_type must be one of {allowed}")
        total = sum(d * q for d, q in denominations.items() if q > 0)
        if total == 0:
            raise ValueError("Total denomination amount must be greater than zero")
        self._denom_repo.record_bulk_entry(
            entry_type=entry_type,
            denominations=denominations,
            created_by=cashier_id,
            note=note,
        )

    def issue_float(self, *args, **kwargs) -> None:
        raise NotImplementedError(
            "issue_float() is removed. Use VaultService.issue_float() via the "
            "/cashier/floats/issue HTTP route."
        )

    def get_all_floats(
        self,
        employee_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> list[CashFloat]:
        """List floats, optionally filtered."""
        return self._float_repo.list_floats(employee_id=employee_id, status=status)

    def get_employees(self) -> list:
        """Return users with role=employee."""
        return self._user_repo.get_employees()

    def receive_float(self, *args, **kwargs) -> None:
        raise NotImplementedError(
            "receive_float() is removed. Use VaultService.receive_float() via the "
            "/cashier/floats/{id}/receive HTTP route."
        )

    def close_float(self, *args, **kwargs) -> None:
        raise NotImplementedError(
            "close_float() is removed. Use VaultService.confirm_return() "
            "(employee initiate-return → cashier confirm-return with PIN)."
        )

    def get_vault_logs(self, limit: int = 100) -> list[CashDenominationLog]:
        """Recent denomination log entries."""
        return self._denom_repo.get_logs(limit=limit)
