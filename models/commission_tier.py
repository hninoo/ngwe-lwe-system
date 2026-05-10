from dataclasses import dataclass
from typing import Optional


@dataclass
class CommissionTier:
    id: Optional[int] = None
    service_type_id: Optional[int] = None   # FK → service_types (replaces service_type TEXT + account_type TEXT)
    amount_from: Optional[float] = None
    amount_to: Optional[float] = None
    fee_amount_type: str = "FIXED"
    fee_amount_cash_in: Optional[float] = None
    fee_amount_cash_out: Optional[float] = None
    comm_type: str = "FIXED"
    comm_cash_in: Optional[float] = None
    comm_cash_out: Optional[float] = None
    additional_fee_type: str = "FIXED"
    additional_fee_cash_in_amount: Optional[float] = None
    additional_fee_cash_out_amount: Optional[float] = None
    is_active: Optional[bool] = None
