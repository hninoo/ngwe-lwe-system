from typing import Optional

from models.transaction import Transaction
from repositories.transaction_operation_base import TransactionOperationRepository


class TransferRepository(TransactionOperationRepository):
    """Business logic for bank-to-bank account movement."""

    def create(
        self,
        from_account_id: int,
        to_account_id: int,
        amount: float,
        created_by: int,
        screenshot_path: Optional[str] = None,
        customer_fee: float = 0.0,
        additional_fee_amount: float = 0.0,
        fee_account_id: Optional[int] = None,
        note: Optional[str] = None,
        employee_id: Optional[int] = None,
        denominations: Optional[dict] = None,
    ) -> Transaction:
        self._validate_amount(amount)
        if from_account_id == to_account_id:
            raise ValueError("Source and target accounts must be different.")
        from_account = self._get_account(from_account_id)
        to_account = self._get_account(to_account_id)
        active_float = self._validate_employee_float(employee_id, amount, denominations)
        commission = self._calc_commission(from_account, amount, "send")
        customer_fee, additional_fee_amount = self._resolve_fee_values(
            from_account, amount, "deposit", customer_fee, additional_fee_amount
        )
        from_company_id = self._get_company_id(from_account.service_type_id)
        to_company_id = self._get_company_id(to_account.service_type_id)

        with self.atomic():
            self._account_repo.increment_balance(from_account_id, -amount)
            self._account_repo.increment_balance(to_account_id, amount)
            txn_id = self._txn_repo.create({
                "transaction_type": "transfer",
                "account_id": from_account_id,
                "to_account_id": to_account_id,
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
                "to_company_id": to_company_id,
            })
            self._process_employee_withdrawal(
                employee_id, amount, denominations, active_float, txn_id
            )
            self._update_fee_account(fee_account_id, customer_fee)
            self._log(created_by, "transaction_created", txn_id, {
                "type": "transfer",
                "from_account_id": from_account_id,
                "to_account_id": to_account_id,
                "amount": amount,
                "from_balance_delta": -amount,
                "to_balance_delta": amount,
            })
        return self._txn_repo.get_by_id(txn_id)
