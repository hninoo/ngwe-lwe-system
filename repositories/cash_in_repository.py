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
            account, amount, "deposit", customer_fee, additional_fee_amount
        )
        from_company_id = self._get_company_id(account.service_type_id)

        with self.atomic():
            self._account_repo.increment_balance(account_id, -amount)
            if employee_id is not None:
                self._float_repo.add_float_balance(employee_id, amount)
            self._update_fee_account(fee_account_id, customer_fee)
            txn_id = self._txn_repo.create({
                "transaction_type": "deposit",
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
            })
            self._log(created_by, "transaction_created", txn_id, {
                "type": "deposit",
                "account_id": account_id,
                "amount": amount,
                "balance_delta": -amount,
            })
        return self._txn_repo.get_by_id(txn_id)
