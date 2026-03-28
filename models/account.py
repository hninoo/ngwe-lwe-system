from dataclasses import dataclass
from typing import Optional


@dataclass
class Account:
    id: Optional[int] = None
    service_id: Optional[int] = None
    account_name: Optional[str] = None
    account_type: Optional[str] = None  # 'personal' | 'agent'
    phone_number: Optional[str] = None
    balance: Optional[float] = None
    commission_rate: Optional[float] = None
    is_active: Optional[bool] = None
