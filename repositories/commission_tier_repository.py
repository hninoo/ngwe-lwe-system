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
            amount_from=float(row["amount_from"]) if row["amount_from"] is not None else None,
            amount_to=float(row["amount_to"]) if row["amount_to"] is not None else None,
            fee_amount_type=row["fee_amount_type"] or "FIXED",
            fee_amount_deposit=float(row["fee_amount_deposit"]),
            fee_amount_withdraw=float(row["fee_amount_withdraw"]),
            comm_type=row["comm_type"] or "FIXED",
            comm_deposit=float(row["comm_deposit"]),
            comm_withdraw=float(row["comm_withdraw"]),
            additional_fee_type=row["additional_fee_type"] or "FIXED",
            additional_fee_deposit_amount=float(row["additional_fee_deposit_amount"]),
            additional_fee_withdraw_amount=float(row["additional_fee_withdraw_amount"]),
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
                "WHERE service_type = %s AND (account_type = %s OR account_type IS NULL) "
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
                "WHERE service_type = %s AND (account_type = %s OR account_type IS NULL) "
                "AND is_active = TRUE "
                "ORDER BY amount_from ASC",
                (service_type, account_type),
            )
            rows = cursor.fetchall()
        return [self._row_to_model(r) for r in rows]
