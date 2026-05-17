from decimal import Decimal
from typing import Any, Optional

from models.transaction import Transaction
from repositories.cash_denomination_repository import DENOMINATIONS
from repositories.transaction_operation_base import TransactionOperationBase


class CashInRepository(TransactionOperationBase):
    """Business logic for Cash In: receive digital value and pay physical cash."""

    @staticmethod
    def _normalize_breakdown(raw: Any, field_name: str) -> dict[int, int]:
        if raw is None:
            return {}
        items: list[tuple[Any, Any]]
        if isinstance(raw, dict):
            items = list(raw.items())
        elif isinstance(raw, list):
            items = []
            for entry in raw:
                if not isinstance(entry, dict):
                    raise ValueError(f"{field_name} entries must be objects.")
                denom = entry.get("denomination_id", entry.get("denomination"))
                qty = entry.get("quantity", entry.get("qty"))
                items.append((denom, qty))
        else:
            raise ValueError(f"{field_name} must be a denomination map or list.")

        result: dict[int, int] = {}
        for denom_raw, qty_raw in items:
            try:
                denom = int(denom_raw)
                qty = int(qty_raw)
            except (TypeError, ValueError):
                raise ValueError(f"{field_name} contains an invalid denomination entry.")
            if denom not in DENOMINATIONS:
                raise ValueError(f"Invalid denomination in {field_name}: {denom}.")
            if qty < 0:
                raise ValueError(f"{field_name} quantity for {denom} cannot be negative.")
            if qty > 0:
                result[denom] = result.get(denom, 0) + qty
        return result

    @staticmethod
    def _breakdown_total(denominations: dict[int, int]) -> Decimal:
        return sum(
            Decimal(denom) * Decimal(qty)
            for denom, qty in denominations.items()
        )

    def create(
        self,
        account_id: int,
        amount: float,
        customer_name: str,
        customer_phone: str,
        created_by: int,
        screenshot_path: Optional[str] = None,
        customer_fee: float = 0.0,
        additional_fee_amount: float = 0.0,
        fee_account_id: Optional[int] = None,
        note: Optional[str] = None,
        employee_id: Optional[int] = None,
        amount_received: Optional[float] = None,
        received_breakdown: Any = None,
        change_breakdown: Any = None,
    ) -> Transaction:
        self._validate_amount(amount)
        amount_decimal = Decimal(str(amount))
        received_decimal = (
            Decimal(str(amount_received))
            if amount_received is not None
            else amount_decimal
        )
        if received_decimal < amount_decimal:
            raise ValueError("amount_received must be greater than or equal to amount.")

        change_denoms = self._normalize_breakdown(change_breakdown, "change_breakdown")
        change_due = received_decimal - amount_decimal

        if change_due > 0:
            if self._breakdown_total(change_denoms) != change_due:
                raise ValueError("change_breakdown total must equal amount_received minus amount.")
            if employee_id is None:
                raise ValueError("Employee float is required to give Cash In overpayment change.")
            active_float = self._validate_employee_float(
                employee_id,
                float(change_due),
                change_denoms,
            )
        elif change_denoms:
            raise ValueError("change_breakdown is only allowed when amount_received exceeds amount.")
        else:
            active_float = None

        account = self._get_account(account_id)
        commission = self._calc_commission(account, float(amount_decimal), "send")
        customer_fee, additional_fee_amount = self._resolve_fee_values(
            account, float(amount_decimal), "cash_in", customer_fee, additional_fee_amount
        )
        from_company_id = self._get_company_id(account.service_type_id)

        with self.atomic():
            if not self._account_repo.decrement_balance(account_id, amount_decimal):
                raise RuntimeError(
                    f"Unable to deduct Cash In balance for active account #{account_id}."
                )
            txn_id = self._txn_repo.create({
                "transaction_type": "cash_in",
                "account_id": account_id,
                "customer_name": customer_name,
                "customer_phone": customer_phone,
                "amount": float(amount_decimal),
                "commission_amount": commission,
                "customer_fee": customer_fee,
                "additional_fee_amount": additional_fee_amount,
                "balance_change": float(-amount_decimal),
                "currency": "MMK",
                "fee_account_id": fee_account_id,
                "screenshot_path": screenshot_path,
                "note": note,
                "created_by": created_by,
                "from_company_id": from_company_id,
                "status": "PENDING_CASHIER_CONFIRM",
                "vault_impact": "none",
            })
            self._log(created_by, "transaction_created", txn_id, {
                "type": "cash_in",
                "account_id": account_id,
                "amount": float(amount_decimal),
                "balance_delta": float(-amount_decimal),
                "status": "PENDING_CASHIER_CONFIRM",
                "vault_impact": "none",
                "message": (
                    "Digital balance deducted immediately. "
                    "Awaiting cashier confirmation for physical cash handover."
                ),
            })
            if change_due > 0:
                self._process_employee_cash_out(
                    employee_id,
                    float(change_due),
                    change_denoms,
                    active_float,
                    transaction_id=txn_id,
                )
                self._log(created_by, "cash_in_overpayment_change_given", txn_id, {
                    "type": "cash_in",
                    "account_id": account_id,
                    "amount": float(amount_decimal),
                    "amount_received": float(received_decimal),
                    "change_due": float(change_due),
                    "change_breakdown": {str(k): v for k, v in change_denoms.items()},
                    "message": (
                        "Employee exchanged customer notes and returned overpayment "
                        "change from their float. Cashier must receive the exact Cash In amount."
                    ),
                })
        return self._txn_repo.get_by_id(txn_id)

    def cancel_pending_cash_in(
        self,
        txn_id: int,
        cashier_id: int,
        note: Optional[str] = None,
    ) -> Optional[Transaction]:
        txn = self._txn_repo.get_by_id(txn_id)
        if txn is None:
            return None
        if txn.transaction_type != "cash_in":
            raise ValueError("Only Cash In transactions can be cancelled here.")
        if txn.status != "PENDING_CASHIER_CONFIRM":
            return None

        reversal_amount = Decimal(str(txn.amount or 0))
        with self.atomic():
            if not self._account_repo.increment_balance(txn.account_id, reversal_amount):
                raise RuntimeError(
                    f"Unable to reverse Cash In balance for active account #{txn.account_id}."
                )
            updated = self._txn_repo.cancel_pending_cash_in(txn_id, cashier_id, note)
            if updated is None:
                raise RuntimeError(
                    f"Transaction #{txn_id} is no longer pending confirmation. "
                    "Auto-reversal was rolled back."
                )
            self._log(cashier_id, "cash_in_auto_reversed", txn_id, {
                "type": "cash_in",
                "account_id": txn.account_id,
                "amount": txn.amount,
                "balance_delta": float(reversal_amount),
                "status": "CANCELLED",
                "message": "Auto-reversal credited digital balance back after cashier cancellation.",
            })
        return updated
