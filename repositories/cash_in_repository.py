from typing import Optional

from models.transaction import Transaction
from repositories.transaction_operation_base import TransactionOperationBase


class CashInRepository(TransactionOperationBase):
    """Business logic for Cash In: receive digital value and pay physical cash."""

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
    ) -> Transaction:
        self._validate_amount(amount)
        account = self._get_account(account_id)
        commission = self._calc_commission(account, amount, "send")
        customer_fee, additional_fee_amount = self._resolve_fee_values(
            account, amount, "cash_in", customer_fee, additional_fee_amount
        )
        from_company_id = self._get_company_id(account.service_type_id)

        with self.atomic():
            self._account_repo.increment_balance(account_id, -amount)
            txn_id = self._txn_repo.create({
                "transaction_type": "cash_in",
                "account_id": account_id,
                "customer_name": customer_name,
                "customer_phone": customer_phone,
                "amount": amount,
                "commission_amount": commission,
                "customer_fee": customer_fee,
                "additional_fee_amount": additional_fee_amount,
                "balance_change": -amount,
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
                "amount": amount,
                "balance_delta": -amount,
                "status": "PENDING_CASHIER_CONFIRM",
                "vault_impact": "none",
                "message": (
                    "Digital balance deducted immediately. "
                    "Awaiting cashier confirmation for physical cash handover."
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

        reversal_amount = float(txn.amount or 0)
        with self.atomic():
            self._account_repo.increment_balance(txn.account_id, reversal_amount)
            updated = self._txn_repo.cancel_pending_cash_in(txn_id, cashier_id, note)
            self._log(cashier_id, "cash_in_auto_reversed", txn_id, {
                "type": "cash_in",
                "account_id": txn.account_id,
                "amount": txn.amount,
                "balance_delta": reversal_amount,
                "status": "CANCELLED",
                "message": "Auto-reversal credited digital balance back after cashier cancellation.",
            })
        return updated
