from typing import Optional

from models.cash_float import CashFloat
from models.cash_denomination_log import CashDenominationLog
from repositories.cash_denomination_repository import CashDenominationRepository, DENOMINATIONS
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

    def issue_float(
        self,
        employee_id: int,
        cashier_id: int,
        denominations: dict[int, int],
        note: Optional[str] = None,
    ) -> CashFloat:
        """Issue a float to an employee. Returns the created CashFloat."""
        total = sum(d * q for d, q in denominations.items() if q > 0)
        if total == 0:
            raise ValueError("Float total must be greater than zero")

        employee = self._user_repo.get_by_id(employee_id)
        if employee is None or employee.role != "employee":
            raise ValueError("Employee not found")

        # Max 1 open float check
        existing_pending = self._float_repo.get_pending_float_for_employee(employee_id)
        existing_active = self._float_repo.get_active_float_for_employee(employee_id)
        if existing_pending is not None or existing_active is not None:
            raise ValueError("Employee already has an open float (PENDING or ACTIVE)")

        # Vault sufficiency check
        available = self._denom_repo.get_available_balance()
        for denom, qty in denominations.items():
            if qty > 0 and available.get(denom, 0) < qty:
                raise ValueError(
                    f"Insufficient vault balance for {denom} MMK: "
                    f"requested {qty}, available {available.get(denom, 0)}"
                )

        float_id = self._float_repo.create_float(
            employee_id=employee_id,
            issued_by=cashier_id,
            denominations=denominations,
            total_amount=total,
            note=note,
        )
        return self._float_repo.get_float(float_id)

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

    def receive_float(self, float_id: int, employee_id: int, pin: str) -> CashFloat:
        """Activate float after PIN verification."""
        import bcrypt
        stored_pin_hash = self._user_repo.get_pin_hash(employee_id)
        if stored_pin_hash is None:
            raise ValueError("PIN not set. Please ask your cashier to set your PIN.")
        if not bcrypt.checkpw(pin.encode(), stored_pin_hash.encode()):
            raise ValueError("Invalid PIN")
        return self._float_repo.activate_float(float_id, self._denom_repo)

    def close_float(
        self,
        float_id: int,
        closing_denominations: dict[int, int],
        note: Optional[str] = None,
    ) -> CashFloat:
        """Close a float with denomination return."""
        return self._float_repo.close_float(
            float_id=float_id,
            closing_denominations=closing_denominations,
            denom_repo=self._denom_repo,
            note=note,
        )

    def get_vault_logs(self, limit: int = 100) -> list[CashDenominationLog]:
        """Recent denomination log entries."""
        return self._denom_repo.get_logs(limit=limit)
