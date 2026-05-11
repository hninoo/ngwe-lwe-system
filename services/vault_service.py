"""
services/vault_service.py

VaultService — central orchestrator for all vault/float operations.

Float lifecycle:
    Cashier issues    →  PENDING_RECEIPT         (main vault debited immediately)
    Employee confirms →  ACTIVE                  (PIN + denomination verification)
    Employee cash_outs → float denominations decremented per transaction
    Employee returns  →  PENDING_RECONCILIATION  (cashier must count & confirm)
    Cashier confirms  →  CLOSED                  (main vault credited)
"""

import json
from typing import Optional

import bcrypt

from backend.database import atomic, get_cursor
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

    @staticmethod
    def calculate_change_from_balance(
        change_amount: int,
        available_denominations: dict[int, int],
    ) -> dict[int, int]:
        if change_amount < 0:
            raise ValueError("Change amount cannot be negative.")
        remaining = int(change_amount)
        result: dict[int, int] = {}
        for denom in sorted(DENOMINATIONS, reverse=True):
            available = int(available_denominations.get(denom, 0) or 0)
            if remaining <= 0 or available <= 0:
                continue
            qty = min(remaining // denom, available)
            if qty > 0:
                result[denom] = qty
                remaining -= denom * qty
        if remaining != 0:
            raise InsufficientDenominationError(
                denomination=remaining,
                available=0,
                requested=1,
            )
        return result

    def calculate_change(self, change_amount: int) -> dict[int, int]:
        return self.calculate_change_from_balance(
            int(change_amount),
            self._denom_repo.get_vault_balance(),
        )

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

        with atomic():
            updated = self._float_repo.activate_float_v2(float_id)
            self._vault_txn_repo.record_bulk(
                txn_type="float_receipt",
                float_id=float_id,
                denominations=v_denoms,
                performed_by=employee_id,
                note=f"Float #{float_id} receipt completed",
            )

        return updated

    # ── 3. CashOut — deduct denominations from employee float ──────────────

    def process_cash_out(
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
                f"Float #{float_id} must be ACTIVE for cash_out (status={cash_float.status})."
            )
        if cash_float.employee_id != employee_id:
            raise ValueError("Float does not belong to this employee.")

        denoms = self.parse_denominations(denominations)
        if not denoms:
            raise ValueError("Denomination breakdown is required for cash_outs.")

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
            txn_type="cash_out",
            float_id=float_id,
            denominations=denoms,
            performed_by=employee_id,
            transaction_id=transaction_id,
            note=f"CashOut txn #{transaction_id}" if transaction_id else "CashOut",
        )

        return self._float_repo.get_denomination_balance(float_id)

    def exchange_denomination(
        self,
        float_id: int,
        employee_id: int,
        from_denominations: dict,
        to_denominations: dict,
        performed_by: int,
        exchange_type: str = "BREAK_DOWN",
        note: Optional[str] = None,
    ) -> dict:
        exchange_type = (exchange_type or "BREAK_DOWN").upper()
        if exchange_type not in {"BREAK_DOWN", "COMBINE", "CHANGE"}:
            raise ValueError("exchange_type must be BREAK_DOWN, COMBINE, or CHANGE.")
        cash_float = self._float_repo.get_float(float_id)
        if cash_float is None:
            raise ValueError(f"Float #{float_id} not found.")
        if cash_float.status != "ACTIVE":
            raise FloatStateError(
                f"Float #{float_id} must be ACTIVE for denomination exchange."
            )
        if cash_float.employee_id != employee_id:
            raise ValueError("Float does not belong to this employee.")

        from_denoms = self.parse_denominations(from_denominations)
        to_denoms = self.parse_denominations(to_denominations)
        if not from_denoms or not to_denoms:
            raise ValueError("Both from and to denomination breakdowns are required.")
        from_total = int(self._total(from_denoms))
        to_total = int(self._total(to_denoms))
        if from_total != to_total:
            raise DenominationMismatchError(
                f"Exchange totals must match. From={from_total:,}, To={to_total:,}."
            )
        if len(from_denoms) != 1:
            raise ValueError("Exchange request must contain exactly one given denomination.")
        given_denom, given_quantity = next(iter(from_denoms.items()))

        current = self._float_repo.get_denomination_balance(float_id)
        for denom, qty in from_denoms.items():
            available = current.get(denom, 0)
            if qty > available:
                raise InsufficientDenominationError(denom, available, qty)
        vault_balance = self._denom_repo.get_vault_balance()
        for denom, qty in to_denoms.items():
            available = vault_balance.get(denom, 0)
            if qty > available:
                raise InsufficientDenominationError(denom, available, qty)

        with atomic():
            # Employee gives from_denoms to cashier/main vault, then receives to_denoms.
            self._float_repo.deduct_denominations(float_id, from_denoms)
            self._float_repo.add_denominations(float_id, to_denoms)
            self._denom_repo.record_bulk_entry(
                entry_type="vault_in",
                denominations=from_denoms,
                created_by=performed_by,
                float_id=float_id,
                note=note or f"Denomination exchange received from float #{float_id}",
            )
            self._denom_repo.record_bulk_entry(
                entry_type="vault_out",
                denominations=to_denoms,
                created_by=performed_by,
                float_id=float_id,
                note=note or f"Denomination exchange paid to float #{float_id}",
            )
            self._vault_txn_repo.record_bulk(
                txn_type="adjustment",
                float_id=float_id,
                denominations=to_denoms,
                performed_by=performed_by,
                note=note or (
                    f"Denomination exchange on float #{float_id}: "
                    f"{json.dumps(from_denoms)} -> {json.dumps(to_denoms)}"
                ),
            )
            with get_cursor(commit=True) as cur:
                received_breakdown = json.dumps([
                    {"denom": denom, "qty": qty}
                    for denom, qty in sorted(to_denoms.items(), reverse=True)
                ])
                cur.execute(
                    "INSERT INTO denomination_exchanges "
                    "(cashier_id, employee_id, float_id, exchange_type, given_denom, "
                    "given_quantity, received_breakdown, total_amount, note) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        performed_by,
                        employee_id,
                        float_id,
                        exchange_type,
                        given_denom,
                        given_quantity,
                        received_breakdown,
                        from_total,
                        note,
                    ),
                )
                exchange_id = cur.lastrowid
                cur.execute(
                    "INSERT INTO activity_logs "
                    "(user_id, action, entity_type, entity_id, details) "
                    "VALUES (?, 'denomination_exchange', 'cash_float', ?, ?)",
                    (
                        performed_by,
                        float_id,
                        json.dumps({
                            "employee_id": employee_id,
                            "exchange_id": exchange_id,
                            "exchange_type": exchange_type,
                            "from": from_denoms,
                            "to": to_denoms,
                            "total": from_total,
                            "note": note,
                        }),
                    ),
                )

        return {
            "success": True,
            "exchange_id": exchange_id,
            "float_id": float_id,
            "employee_id": employee_id,
            "exchange_type": exchange_type,
            "from_denominations": {str(k): v for k, v in from_denoms.items()},
            "to_denominations": {str(k): v for k, v in to_denoms.items()},
            "given": {"denom": given_denom, "qty": given_quantity},
            "received": [
                {"denom": denom, "qty": qty}
                for denom, qty in sorted(to_denoms.items(), reverse=True)
            ],
            "total": from_total,
            "float_balance": {
                str(k): v for k, v in self._float_repo.get_denomination_balance(float_id).items()
            },
            "vault_balance_updated": {
                str(k): v for k, v in self._denom_repo.get_vault_balance().items()
            },
        }

    def record_transaction_payment(
        self,
        transaction_id: int,
        cashier_id: int,
        fee_amount: int,
        received_denominations: dict,
        change_denominations: Optional[dict] = None,
        note: Optional[str] = None,
    ) -> dict:
        fee = int(fee_amount)
        if fee < 0:
            raise ValueError("Fee amount cannot be negative.")
        received = self.parse_denominations(received_denominations)
        received_total = int(self._total(received))
        if received_total < fee:
            raise ValueError("Received amount is less than the fee.")

        change_due = received_total - fee
        available = self._denom_repo.get_vault_balance()
        available_after_received = {
            denom: available.get(denom, 0) + received.get(denom, 0)
            for denom in DENOMINATIONS
        }
        if change_denominations is None:
            change = self.calculate_change_from_balance(change_due, available_after_received)
        else:
            change = self.parse_denominations(change_denominations)
            change_total = int(self._total(change))
            if change_total != change_due:
                raise ValueError(
                    f"Change denominations total {change_total:,} does not match "
                    f"change due {change_due:,}."
                )
            for denom, qty in change.items():
                if qty > available_after_received.get(denom, 0):
                    raise InsufficientDenominationError(
                        denom, available_after_received.get(denom, 0), qty
                    )

        with atomic():
            if received:
                self._denom_repo.record_bulk_entry(
                    entry_type="vault_in",
                    denominations=received,
                    created_by=cashier_id,
                    note=note or f"Fee payment received for transaction #{transaction_id}",
                )
            if change:
                self._denom_repo.record_bulk_entry(
                    entry_type="vault_out",
                    denominations=change,
                    created_by=cashier_id,
                    note=note or f"Change given for transaction #{transaction_id}",
                )
            self._denom_repo.record_transaction_payment_denominations(
                transaction_id=transaction_id,
                paid_denominations=received,
                change_denominations=change,
            )
            with get_cursor(commit=True) as cur:
                change_json = json.dumps({str(k): v for k, v in change.items()})
                cur.execute(
                    "UPDATE transactions "
                    "SET change_given = ?, change_denominations = ? "
                    "WHERE id = ?",
                    (change_due, change_json, transaction_id),
                )
                if cur.rowcount == 0:
                    raise ValueError(f"Transaction #{transaction_id} not found.")
                cur.execute(
                    "INSERT INTO activity_logs "
                    "(user_id, action, entity_type, entity_id, details) "
                    "VALUES (?, 'transaction_payment_recorded', 'transaction', ?, ?)",
                    (
                        cashier_id,
                        transaction_id,
                        json.dumps({
                            "fee_amount": fee,
                            "received_total": received_total,
                            "change_due": change_due,
                            "received_denominations": received,
                            "change_denominations": change,
                            "note": note,
                        }),
                    ),
                )

        return {
            "transaction_id": transaction_id,
            "fee_amount": fee,
            "received_total": received_total,
            "change_due": change_due,
            "received_denominations": {str(k): v for k, v in received.items()},
            "change_denominations": {str(k): v for k, v in change.items()},
            "vault": {
                str(k): v for k, v in self._denom_repo.get_vault_balance().items()
            },
        }

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

        with atomic():
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
        PIN verification and pre-validation run before the atomic block to
        avoid holding the write lock for I/O-bound checks.
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

        with atomic():
            # Close the float first — rowcount=0 means a concurrent request
            # already closed it; the atomic() rollback prevents double-crediting.
            self._float_repo.close_after_return(
                float_id=float_id,
                closing_total=closing_total,
                verified_by=cashier_id,
            )
            # Credit main vault inside the same transaction
            self._denom_repo.record_bulk_entry(
                entry_type="float_returned",
                denominations=return_denoms,
                created_by=cashier_id,
                float_id=float_id,
                note=f"Float #{float_id} return completed by cashier",
            )
            self._vault_txn_repo.record_bulk(
                txn_type="return_confirm",
                float_id=float_id,
                denominations=return_denoms,
                performed_by=cashier_id,
                verified_by=cashier_id,
                note=f"Float #{float_id} return completed",
            )

        return self._float_repo.get_float(float_id)

    # ── Pre-validation (read-only, no writes) ─────────────────────────────────

    def validate_cash_out(
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
                f"Float #{float_id} must be ACTIVE for a cash_out (status={cash_float.status})."
            )
        if cash_float.employee_id != employee_id:
            raise ValueError("Float does not belong to this employee.")

        denoms = self.parse_denominations(denominations)
        if not denoms:
            raise ValueError("Denomination breakdown is required for cash_outs.")

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
                f"cash_out amount {amount:,.0f}."
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

        active_floats = self._float_repo.get_open_employee_float_summaries()
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
