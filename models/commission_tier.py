from dataclasses import dataclass
from typing import Optional


@dataclass
class CommissionTier:
    id: Optional[int] = None
    service_type: Optional[str] = None
    account_type: Optional[str] = None  # 'personal' | 'agent' | None
    amount_from: Optional[float] = None
    amount_to: Optional[float] = None
    fee_amount_type: str = "FIXED"
    fee_amount_deposit: Optional[float] = None
    fee_amount_withdraw: Optional[float] = None
    comm_type: str = "FIXED"
    comm_deposit: Optional[float] = None
    comm_withdraw: Optional[float] = None
    additional_fee_type: str = "FIXED"
    additional_fee_deposit_amount: Optional[float] = None
    additional_fee_withdraw_amount: Optional[float] = None
    is_active: Optional[bool] = None
