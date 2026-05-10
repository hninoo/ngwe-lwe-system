from typing import Optional

from models.transaction import Transaction
from repositories.transaction_operation_base import TransactionOperationRepository


class ExchangeRepository(TransactionOperationRepository):
    """Business logic for currency conversion transactions."""

    def create(
        self,
        account_id: int,
        amount: float,
        currency: str,
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
        account = self._get_account(account_id)
        active_float = self._validate_employee_float(employee_id, amount, denominations)
        rate = self._rate_repo.get_latest("THB", "MMK")
        if rate is None:
            raise ValueError("Exchange rate not set for THB/MMK")

        base_amount = rate.base_amount or 1.0
        exchange_rate = (
            rate.sell_rate / base_amount
            if currency == "MMK"
            else rate.buy_rate / base_amount
        )
        commission = self._calc_commission(account, amount, "send")
        customer_fee, additional_fee_amount = self._resolve_fee_values(
            account, amount, "deposit", customer_fee, additional_fee_amount
        )
        from_company_id = self._get_company_id(account.service_type_id)

        with self.atomic():
            self._account_repo.increment_balance(account_id, amount)
            txn_id = self._txn_repo.create({
                "transaction_type": "exchange",
                "account_id": account_id,
                "amount": amount,
                "commission_amount": commission,
                "customer_fee": customer_fee,
                "additional_fee_amount": additional_fee_amount,
                "balance_change": amount,
                "currency": currency,
                "exchange_rate": exchange_rate,
                "fee_account_id": fee_account_id,
                "screenshot_path": screenshot_path,
                "note": note,
                "created_by": created_by,
                "from_company_id": from_company_id,
            })
            self._process_employee_withdrawal(
                employee_id, amount, denominations, active_float, txn_id
            )
            self._update_fee_account(fee_account_id, customer_fee)
            self._log(created_by, "transaction_created", txn_id, {
                "type": "exchange",
                "account_id": account_id,
                "amount": amount,
                "currency": currency,
                "balance_delta": amount,
            })
        return self._txn_repo.get_by_id(txn_id)
