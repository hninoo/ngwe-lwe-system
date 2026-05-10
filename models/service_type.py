from dataclasses import dataclass
from typing import Optional


@dataclass
class ServiceType:
    id: Optional[int] = None
    company_id: Optional[int] = None
    name: Optional[str] = None       # 'WST' | 'Pay_To_Pay' | 'Transfer' | 'Exchange'
    operation: Optional[str] = None  # 'CashIn'|'CashOut'|'Transfer'|'Exchange'|'All'
    is_active: Optional[bool] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
