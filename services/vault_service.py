"""
services/vault_service.py

VaultService — central orchestrator for all vault/float operations.

Float lifecycle:
    Cashier issues    →  PENDING_RECEIPT         (main vault debited immediately)
    Employee confirms →  ACTIVE                  (PIN + denomination verification)
    Employee withdraws → float denominations decremented per transaction
    Employee returns  →  PENDING_RECONCILIATION  (cashier must count & confirm)
    Cashier confirms  →  CLOSED                  (main vault credited)
"""

import json
from typing import Optional

import bcrypt

from backend.database import atomic
from models.cash_float import CashFloat
from repositories.cash_denomination_repository import CashDenominationRepository, DENOMINATIONS
from repositories.cash_float_repository import CashFloatRepository, InsufficientFloatError
from repositories.user_repository import UserRepository
from repositories.vault_transaction_repository import VaultTransactionRepository


# ── Custom exceptions ──────────────────────────────────────────────────────────

class InsufficientDenominationError(Exception):
    def __init__(self, denomination: int, available: int, requested: int) -> None:
        self.denomination = denomination
        self.available = available
        self.requested = requested
        super().__init__(
            f"Insufficient {denomination:,} MMK notes. "
            f"Available: {available}, Requested: {requested}"
        )


class DenominationMismatchError(Exception):
    """Raised when the employee's verified count differs from what was issued."""


class FloatStateError(Exception):
    """Raised when a state transition is invalid."""


# ── Service ────────────────────────────────────────────────────────────────────

class VaultService:

    def __init__(
        self,
        float_repo: Optional[CashFloatRepository] = None,
        denom_repo: Optional[CashDenominationRepository] = None,
        vault_txn_repo: Optional[VaultTransactionRepository] = None,
        user_repo: Optional[UserRepository] = None,
    ) -> None:
        self._float_repo = float_repo or CashFloatRepository()
        self._denom_repo = denom_repo or CashDenominationRepository()
        self._vault_txn_repo = vault_txn_repo or VaultTransactionRepository()
        self._user_repo = user_repo or UserRepository()

    # ── Private helpers ────────────────────────────────────────────────────────

    def _verify_pin(self, user_id: int, pin: str) -> None:
        user = self._user_repo.get_by_id(user_id)
        if user is None or not user.pin_hash:
            raise ValueError("No PIN set. Please set your PIN first.")
        if not bcrypt.checkpw(pin.encode(), user.pin_hash.encode()):
            raise ValueError("Incorrect PIN.")

    @staticmethod
    def parse_denominations(raw: dict) -> dict[int, int]:
        result: dict[int, int] = {}
        for k, v in raw.items():
            denom = int(k)
            if denom not in DENOMINATIONS:
                raise ValueError(f"Invalid denomination: {denom}")
            qty = int(v)
            if qty < 0:
                raise ValueError(f"Quantity for {denom} must be >= 0")
            if qty > 0:
                result[denom] = qty
        return result

    @staticmethod
    def _total(denominations: dict[int, int]) -> float:
        return float(sum(d * q for d, q in denominations.items()))

    # ── 1. Issue float — Cashier → Employee ───────────────────────────────────

    def issue_float(
        self,
        cashier_id: int,
        employee_id: int,
        denominations: dict,
        note: Optional[str] = None,
    ) -> CashFloat:
        """
        Create a PENDING_RECEIPT float and immediately debit the main vault.
        Denomination tracking starts at issuance, not at employee receipt.
        """
        denoms = self.parse_denominations(denominations)
        if not denoms:
            raise ValueError("Denomination breakdown must not be empty.")
        total = self._total(denoms)

        with atomic():
            available = self._denom_repo.get_vault_balance()
            for denom, qty in denoms.items():
                if qty > available.get(denom, 0):
                    raise InsufficientDenominationError(denom, available.get(denom, 0), qty)

            float_id = self._float_repo.create_float(
                employee_id=employee_id,
                issued_by=cashier_id,
                denominations=denoms,
                total_amount=total,
                note=note,
            )

            # Main vault debited immediately at issuance
            self._denom_repo.record_bulk_entry(
                entry_type="vault_out",
                denominations=denoms,
                created_by=cashier_id,
                float_id=float_id,
                note=note or f"Float #{float_id} issued to employee #{employee_id}",
            )

            self._vault_txn_repo.record_bulk(
                txn_type="float_issue",
                float_id=float_id,
                denominations=denoms,
                performed_by=cashier_id,
                note=note,
            )

        return self._float_repo.get_float(float_id)

    # ── 2. Employee confirms receipt — PIN + denomination verification ─────────

    def confirm_receipt(
        self,
        float_id: int,
        employee_id: int,
        employee_pin: str,
        verified_denominations: dict,
    ) -> CashFloat:
        """
        Employee counts physical cash, verifies denominations match what was issued,
        then enters their PIN to activate the float.
        Status: PENDING_RECEIPT → ACTIVE.
        """
        cash_float = self._float_repo.get_float(float_id)
        if cash_float is None:
            raise ValueError(f"Float #{float_id} not found.")
        if cash_float.employee_id != employee_id:
            raise ValueError("This float is not assigned to you.")
        if cash_float.status != "PENDING_RECEIPT":
            raise FloatStateError(
                f"Float is not pending receipt (status={cash_float.status})."
            )

        self._verify_pin(employee_id, employee_pin)

        v_denoms = self.parse_denominations(verified_denominations)
        issued = {d.denomination: d.quantity for d in cash_float.denominations}

        # Strict denomination count match
        for denom in DENOMINATIONS:
            issued_qty = issued.get(denom, 0)
            verified_qty = v_denoms.get(denom, 0)
            if issued_qty != verified_qty:
                raise DenominationMismatchError(
                    f"Denomination {denom:,} MMK — Issued: {issued_qty}, You counted: {verified_qty}. "
                    "Please recount and try again or contact the cashier."
                )

        updated = self._float_repo.activate_float_v2(float_id)

        self._vault_txn_repo.record_bulk(
            txn_type="float_receipt",
            float_id=float_id,
            denominations=v_denoms,
            performed_by=employee_id,
            note=f"Float #{float_id} receipt confirmed",
        )

        return updated

    # ── 3. Withdrawal — deduct denominations from employee float ──────────────

    def process_withdrawal(
        self,
        float_id: int,
        employee_id: int,
        denominations: dict,
        transaction_id: Optional[int] = None,
    ) -> dict[int, int]:
        """
        Validate and deduct denomination breakdown from the employee's float.
        Raises InsufficientDenominationError if any denomination is short.
        Returns the new denomination balance.
        """
        # State guard — must be checked before any writes
        cash_float = self._float_repo.get_float(float_id)
        if cash_float is None:
            raise ValueError(f"Float #{float_id} not found.")
        if cash_float.status != "ACTIVE":
            raise FloatStateError(
                f"Float #{float_id} must be ACTIVE for withdrawal (status={cash_float.status})."
            )
        if cash_float.employee_id != employee_id:
            raise ValueError("Float does not belong to this employee.")

        denoms = self.parse_denominations(denominations)
        if not denoms:
            raise ValueError("Denomination breakdown is required for withdrawals.")

        current_balance = self._float_repo.get_denomination_balance(float_id)
        for denom, qty in denoms.items():
            available = current_balance.get(denom, 0)
            if qty > available:
                raise InsufficientDenominationError(
                    denomination=denom,
                    available=available,
                    requested=qty,
                )

        total = self._total(denoms)
        self._float_repo.deduct_denominations(float_id, denoms)
        self._float_repo.deduct_float_balance(employee_id, total)

        self._vault_txn_repo.record_bulk(
            txn_type="withdrawal",
            float_id=float_id,
            denominations=denoms,
            performed_by=employee_id,
            transaction_id=transaction_id,
            note=f"Withdrawal txn #{transaction_id}" if transaction_id else "Withdrawal",
        )

        return self._float_repo.get_denomination_balance(float_id)

    # ── 4. Initiate return — Employee → PENDING_RECONCILIATION ────────────────

    def initiate_return(
        self,
        float_id: int,
        employee_id: int,
        return_denominations: dict,
        note: Optional[str] = None,
    ) -> CashFloat:
        """
        Employee declares remaining cash to return.
        Validates against float denomination balance.
        Status: ACTIVE → PENDING_RECONCILIATION.
        """
        cash_float = self._float_repo.get_float(float_id)
        if cash_float is None:
            raise ValueError(f"Float #{float_id} not found.")
        if cash_float.employee_id != employee_id:
            raise ValueError("This float is not assigned to you.")
        if cash_float.status != "ACTIVE":
            raise FloatStateError(
                f"Float must be ACTIVE to initiate a return (status={cash_float.status})."
            )

        denoms = self.parse_denominations(return_denominations)
        if not denoms:
            raise ValueError(
                "Return denomination breakdown cannot be empty. "
                "Provide at least one note denomination to return."
            )
        total = self._total(denoms)

        current = float(cash_float.current_balance or 0)
        if total > current:
            raise ValueError(
                f"Return total {total:,.0f} exceeds float balance {current:,.0f}."
            )

        denom_balance = self._float_repo.get_denomination_balance(float_id)
        for denom, qty in denoms.items():
            available = denom_balance.get(denom, 0)
            if qty > available:
                raise InsufficientDenominationError(denom, available, qty)

        self._float_repo.set_pending_reconciliation(
            float_id=float_id,
            return_denominations_json=json.dumps(
                {str(d): q for d, q in denoms.items()}
            ),
        )

        self._vault_txn_repo.record_bulk(
            txn_type="return_initiate",
            float_id=float_id,
            denominations=denoms,
            performed_by=employee_id,
            note=note or f"Return initiated for float #{float_id}",
        )

        return self._float_repo.get_float(float_id)

    # ── 5. Confirm return — Cashier PIN → CLOSED ──────────────────────────────

    def confirm_return(
        self,
        float_id: int,
        cashier_id: int,
        cashier_pin: str,
    ) -> CashFloat:
        """
        Cashier counts physical cash received, enters their PIN.
        Main vault is credited.  Status: PENDING_RECONCILIATION → CLOSED.
        """
        cash_float = self._float_repo.get_float(float_id)
        if cash_float is None:
            raise ValueError(f"Float #{float_id} not found.")
        if cash_float.status != "PENDING_RECONCILIATION":
            raise FloatStateError(
                f"Float is not pending reconciliation (status={cash_float.status})."
            )

        self._verify_pin(cashier_id, cashier_pin)

        raw_json = self._float_repo.get_return_denominations_json(float_id)
        if not raw_json:
            raise ValueError("No return denominations stored. Employee must initiate return first.")

        return_denoms: dict[int, int] = {
            int(k): int(v)
            for k, v in json.loads(raw_json).items()
            if int(v) > 0
        }
        if not return_denoms:
            raise ValueError("Return denomination breakdown is empty.")

        closing_total = self._total(return_denoms)

        # Credit main vault
        self._denom_repo.record_bulk_entry(
            entry_type="float_returned",
            denominations=return_denoms,
            created_by=cashier_id,
            float_id=float_id,
            note=f"Float #{float_id} return confirmed by cashier",
        )

        self._float_repo.close_after_return(
            float_id=float_id,
            closing_total=closing_total,
            verified_by=cashier_id,
        )

        self._vault_txn_repo.record_bulk(
            txn_type="return_confirm",
            float_id=float_id,
            denominations=return_denoms,
            performed_by=cashier_id,
            verified_by=cashier_id,
            note=f"Float #{float_id} return confirmed",
        )

        return self._float_repo.get_float(float_id)

    # ── Pre-validation (read-only, no writes) ─────────────────────────────────

    def validate_withdrawal(
        self,
        float_id: int,
        employee_id: int,
        denominations: dict,
        amount: float,
    ) -> None:
        """Pure validation — raises before any writes occur.
        Call this BEFORE updating account balances or creating transaction records
        so that no DB state is corrupted if validation fails."""
        cash_float = self._float_repo.get_float(float_id)
        if cash_float is None:
            raise ValueError(f"Float #{float_id} not found.")
        if cash_float.status != "ACTIVE":
            raise FloatStateError(
                f"Float #{float_id} must be ACTIVE for a withdrawal (status={cash_float.status})."
            )
        if cash_float.employee_id != employee_id:
            raise ValueError("Float does not belong to this employee.")

        denoms = self.parse_denominations(denominations)
        if not denoms:
            raise ValueError("Denomination breakdown is required for withdrawals.")

        # Denomination-level check
        current_balance = self._float_repo.get_denomination_balance(float_id)
        for denom, qty in denoms.items():
            available = current_balance.get(denom, 0)
            if qty > available:
                raise InsufficientDenominationError(
                    denomination=denom, available=available, requested=qty
                )

        # Overall balance check
        denom_total = self._total(denoms)
        if abs(denom_total - amount) > 1:
            raise ValueError(
                f"Denomination total {denom_total:,.0f} does not match "
                f"withdrawal amount {amount:,.0f}."
            )

        float_balance = float(cash_float.current_balance or 0)
        if denom_total > float_balance:
            raise InsufficientFloatError(available=float_balance, required=denom_total)

    # ── Queries ────────────────────────────────────────────────────────────────

    def get_float_denomination_balance(self, float_id: int) -> dict[int, int]:
        return self._float_repo.get_denomination_balance(float_id)

    def get_denomination_inventory(self) -> dict:
        """
        Full denomination inventory across main vault and all active employee floats.
        Used by the Daily Closing dashboard.
        """
        main_vault = self._denom_repo.get_vault_balance()
        vault_total = self._total(main_vault)

        active_floats = self._float_repo.get_active_employee_float_summaries()
        employee_inventory = []
        for f in active_floats:
            denom_balance = self._float_repo.get_denomination_balance(f["float_id"])
            denom_total = self._total(denom_balance)
            employee_inventory.append({
                **f,
                "denomination_balance": {
                    str(d): denom_balance.get(d, 0) for d in DENOMINATIONS
                },
                "denom_total": denom_total,
            })

        total_employee_cash = sum(e["denom_total"] for e in employee_inventory)

        return {
            "main_vault": {str(d): main_vault.get(d, 0) for d in DENOMINATIONS},
            "main_vault_total": vault_total,
            "employee_floats": employee_inventory,
            "total_employee_cash": total_employee_cash,
            "grand_physical_total": vault_total + total_employee_cash,
        }
