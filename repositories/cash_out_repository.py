from decimal import Decimal
from typing import Optional

from models.transaction import Transaction
from repositories.transaction_operation_base import TransactionOperationBase


class CashOutRepository(TransactionOperationBase):
    """Business logic for Cash Out: receive physical cash and send digital value."""

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
        denominations: Optional[dict] = None,
    ) -> Transaction:
        self._validate_amount(amount)
        amount_decimal = Decimal(str(amount))
        account = self._get_account(account_id)
        commission = self._calc_commission(account, float(amount_decimal), "receive")
        customer_fee, additional_fee_amount = self._resolve_fee_values(
            account, float(amount_decimal), "cash_out", customer_fee, additional_fee_amount
        )
        from_company_id = self._get_company_id(account.service_type_id)

        with self.atomic():
            active_float = self._validate_employee_float(
                employee_id, float(amount_decimal), denominations
            )
            if not self._account_repo.increment_balance(account_id, amount_decimal):
                raise RuntimeError(
                    f"Unable to credit Cash Out balance for active account #{account_id}."
                )
            txn_id = self._txn_repo.create({
                "transaction_type": "cash_out",
                "account_id": account_id,
                "customer_name": customer_name,
                "customer_phone": customer_phone,
                "amount": float(amount_decimal),
                "commission_amount": commission,
                "customer_fee": customer_fee,
                "additional_fee_amount": additional_fee_amount,
                "balance_change": float(amount_decimal),
                "currency": "MMK",
                "fee_account_id": fee_account_id,
                "screenshot_path": screenshot_path,
                "note": note,
                "created_by": created_by,
                "from_company_id": from_company_id,
            })
            self._process_employee_cash_out(
                employee_id, float(amount_decimal), denominations, active_float, txn_id
            )
            self._update_fee_account(fee_account_id, customer_fee)
            self._log(created_by, "transaction_created", txn_id, {
                "type": "cash_out",
                "account_id": account_id,
                "amount": float(amount_decimal),
                "balance_delta": float(amount_decimal),
            })
        return self._txn_repo.get_by_id(txn_id)
