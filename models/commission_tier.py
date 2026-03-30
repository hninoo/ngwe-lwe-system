from dataclasses import dataclass
from typing import Optional


@dataclass
class CommissionTier:
    id: Optional[int] = None
    service_type: Optional[str] = None  # 'KPAY' | 'WAVE'
    account_type: Optional[str] = None  # 'personal' | 'agent'
    amount_from: Optional[float] = None
    amount_to: Optional[float] = None
    fee_amount: Optional[float] = None
    comm_send: Optional[float] = None
    comm_receive: Optional[float] = None
    is_active: Optional[bool] = None
