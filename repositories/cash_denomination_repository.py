from typing import Optional

from backend.database import get_cursor
from models.cash_denomination_log import CashDenominationLog

DENOMINATIONS = [50, 100, 200, 500, 1000, 5000, 10000]


class CashDenominationRepository:

    def get_vault_balance(self) -> dict[int, int]:
        """Returns {denomination: net_quantity} for vault (vault_in + float_returned - vault_out)."""
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT denomination,
                  SUM(CASE WHEN entry_type IN ('vault_in','float_returned') THEN quantity
                           WHEN entry_type = 'vault_out' THEN -quantity
                           ELSE quantity END) as net_qty
                FROM cash_denomination_logs
                GROUP BY denomination
            """)
            rows = cursor.fetchall()
        result: dict[int, int] = {d: 0 for d in DENOMINATIONS}
        for row in rows:
            denom = row["denomination"]
            if denom in result:
                result[denom] = int(row["net_qty"] or 0)
        return result

    def get_pending_reserved(self) -> dict[int, int]:
        """Returns {denomination: qty} reserved in PENDING floats (not yet vault_out'd)."""
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT cfd.denomination, SUM(cfd.quantity) as total_qty
                FROM cash_float_denominations cfd
                JOIN cash_float_assignments cfa ON cfa.id = cfd.float_id
                WHERE cfa.status = 'PENDING'
                GROUP BY cfd.denomination
            """)
            rows = cursor.fetchall()
        result: dict[int, int] = {d: 0 for d in DENOMINATIONS}
        for row in rows:
            denom = row["denomination"]
            if denom in result:
                result[denom] = int(row["total_qty"] or 0)
        return result

    def get_available_balance(self) -> dict[int, int]:
        """vault_balance - pending_reserved for each denomination."""
        vault = self.get_vault_balance()
        pending = self.get_pending_reserved()
        return {d: max(0, vault[d] - pending.get(d, 0)) for d in DENOMINATIONS}

    def record_bulk_entry(
        self,
        entry_type: str,
        denominations: dict[int, int],
        created_by: int,
        float_id: Optional[int] = None,
        note: Optional[str] = None,
    ) -> None:
        """Insert one log row per denomination (skip qty=0)."""
        rows_to_insert = [
            (entry_type, denom, qty, float_id, created_by, note)
            for denom, qty in denominations.items()
            if qty > 0
        ]
        if not rows_to_insert:
            return
        with get_cursor(commit=True) as cursor:
            cursor.executemany(
                """INSERT INTO cash_denomination_logs
                   (entry_type, denomination, quantity, float_id, created_by, note)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                rows_to_insert,
            )

    def get_logs(self, limit: int = 100) -> list[CashDenominationLog]:
        """Recent denomination log entries."""
        with get_cursor() as cursor:
            cursor.execute(
                """SELECT * FROM cash_denomination_logs
                   ORDER BY created_at DESC LIMIT ?""",
                (limit,),
            )
            rows = cursor.fetchall()
        return [
            CashDenominationLog(
                id=row["id"],
                entry_type=row["entry_type"],
                denomination=row["denomination"],
                quantity=row["quantity"],
                float_id=row["float_id"],
                created_by=row["created_by"],
                note=row["note"],
                created_at=row["created_at"],
            )
            for row in rows
        ]
