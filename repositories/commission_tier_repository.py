from typing import Optional

from backend.database import get_cursor
from models.commission_tier import CommissionTier
from repositories.base_repository import BaseRepository


class CommissionTierRepository(BaseRepository):

    @property
    def table(self) -> str:
        return "commission_tiers"

    def _row_to_model(self, row: dict) -> CommissionTier:
        return CommissionTier(
            id=row["id"],
            service_type=row["service_type"],
            account_type=row["account_type"],
            amount_from=float(row["amount_from"]),
            amount_to=float(row["amount_to"]),
            fee_amount=float(row["fee_amount"]),
            comm_send=float(row["comm_send"]),
            comm_receive=float(row["comm_receive"]),
            is_active=bool(row["is_active"]),
        )

    def get_tier_for_amount(
        self,
        service_type: str,
        account_type: str,
        amount: float,
    ) -> Optional[CommissionTier]:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM commission_tiers "
                "WHERE service_type = %s AND account_type = %s "
                "AND is_active = TRUE "
                "AND amount_from <= %s AND amount_to >= %s "
                "LIMIT 1",
                (service_type, account_type, amount, amount),
            )
            row = cursor.fetchone()
        return self._row_to_model(row) if row else None

    def get_by_service_type(
        self,
        service_type: str,
        account_type: str,
    ) -> list[CommissionTier]:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM commission_tiers "
                "WHERE service_type = %s AND account_type = %s "
                "AND is_active = TRUE "
                "ORDER BY amount_from ASC",
                (service_type, account_type),
            )
            rows = cursor.fetchall()
        return [self._row_to_model(r) for r in rows]
