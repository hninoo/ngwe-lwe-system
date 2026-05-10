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
            service_type_id=row["service_type_id"],
            amount_from=float(row["amount_from"]) if row["amount_from"] is not None else None,
            amount_to=float(row["amount_to"]) if row["amount_to"] is not None else None,
            fee_amount_type=row["fee_amount_type"] or "FIXED",
            fee_amount_cash_in=float(row["fee_amount_cash_in"]),
            fee_amount_cash_out=float(row["fee_amount_cash_out"]),
            comm_type=row["comm_type"] or "FIXED",
            comm_cash_in=float(row["comm_cash_in"]),
            comm_cash_out=float(row["comm_cash_out"]),
            additional_fee_type=row["additional_fee_type"] or "FIXED",
            additional_fee_cash_in_amount=float(row["additional_fee_cash_in_amount"]),
            additional_fee_cash_out_amount=float(row["additional_fee_cash_out_amount"]),
            is_active=bool(row["is_active"]),
        )

    def get_tier_for_amount(
        self,
        service_type_id: int,
        amount: float,
    ) -> Optional[CommissionTier]:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM commission_tiers "
                "WHERE service_type_id = ? AND is_active = 1 "
                "AND (amount_from IS NULL OR amount_from <= ?) "
                "AND (amount_to IS NULL OR amount_to >= ?) "
                "LIMIT 1",
                (service_type_id, amount, amount),
            )
            row = cursor.fetchone()
        return self._row_to_model(row) if row else None

    def check_overlap(
        self,
        service_type_id: int,
        amount_from: Optional[float],
        amount_to: Optional[float],
        exclude_id: Optional[int] = None,
    ) -> Optional[str]:
        """Validate range rules. Returns an error string on failure, None on success."""
        if amount_from is None or amount_from == 0:
            return "From amount must not be null or zero."
        if amount_to is None or amount_to == 0:
            return "To amount must not be null or zero."
        if amount_to <= amount_from:
            return "To amount must be greater than From amount."

        query = (
            "SELECT id, amount_from, amount_to FROM commission_tiers "
            "WHERE service_type_id = ? AND is_active = 1"
        )
        params: list = [service_type_id]
        if exclude_id is not None:
            query += " AND id != ?"
            params.append(exclude_id)

        with get_cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()

        for row in rows:
            ef = float(row["amount_from"]) if row["amount_from"] is not None else None
            et = float(row["amount_to"])   if row["amount_to"]   is not None else None
            if ef is None or et is None:
                continue
            # Standard interval overlap: [af, at) overlaps [ef, et) when af < et AND at > ef
            if amount_from < et and amount_to > ef:
                return (
                    f"Range {amount_from:,.0f}–{amount_to:,.0f} overlaps with "
                    f"existing tier {ef:,.0f}–{et:,.0f}."
                )
        return None

    def get_by_service_type(
        self,
        service_type_id: int,
    ) -> list[CommissionTier]:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM commission_tiers "
                "WHERE service_type_id = ? AND is_active = 1 "
                "ORDER BY amount_from ASC",
                (service_type_id,),
            )
            rows = cursor.fetchall()
        return [self._row_to_model(r) for r in rows]
