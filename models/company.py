from dataclasses import dataclass
from typing import Optional


@dataclass
class Company:
    id: Optional[int] = None
    name: Optional[str] = None
    logo_path: Optional[str] = None
    category: Optional[str] = None   # 'Pay' | 'Bank' | 'Both'
    is_active: Optional[bool] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
