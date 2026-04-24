from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Transaction:
    id: Optional[int] = None
    transaction_type: Optional[str] = None  # 'deposit' | 'withdraw' | 'transfer' | 'exchange'
    account_id: Optional[int] = None
    to_account_id: Optional[int] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    amount: Optional[float] = None
    commission_amount: Optional[float] = None
    customer_fee: Optional[float] = None
    additional_fee_amount: Optional[float] = None
    balance_change: Optional[float] = None
    currency: Optional[str] = None
    exchange_rate: Optional[float] = None
    fee_account_id: Optional[int] = None
    screenshot_path: Optional[str] = None
    note: Optional[str] = None
    created_by: Optional[int] = None
    created_at: Optional[datetime] = None
    cash_approved_by: Optional[int] = None
    cash_approved_at: Optional[str] = None
    from_company_id: Optional[int] = None   # FK → companies (set for all transaction types)
    to_company_id: Optional[int] = None     # FK → companies (set for transfer/exchange)
