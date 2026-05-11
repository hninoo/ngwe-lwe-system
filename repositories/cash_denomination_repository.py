import sqlite3
from typing import Optional

from backend.database import get_cursor
from models.cash_denomination_log import CashDenominationLog

DENOMINATIONS = [50, 100, 200, 500, 1000, 5000, 10000, 20000]


class CashDenominationRepository:
    def get_note_denominations(self) -> list[dict]:
        with get_cursor() as cursor:
            try:
                cursor.execute(
                    "SELECT id, value, label_mm, label_en, is_active "
                    "FROM note_denominations WHERE is_active = 1 ORDER BY value DESC"
                )
                return [dict(row) for row in cursor.fetchall()]
            except sqlite3.OperationalError as exc:
                if "no such table: note_denominations" not in str(exc):
                    raise
        return [
            {
                "id": denom,
                "value": denom,
                "label_mm": f"{denom:,} Kyats",
                "label_en": f"{denom:,} Kyats",
                "is_active": 1,
            }
            for denom in sorted(DENOMINATIONS, reverse=True)
        ]

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
        """Returns {denomination: qty} reserved in PENDING_RECEIPT floats.
        NOTE: In the new flow vault_out is logged at issuance so PENDING_RECEIPT
        amounts are already reflected in get_vault_balance(). This method exists
        for backward-compatibility but should return 0 for all denoms in normal
        operation (vault_balance already accounts for them via vault_out entries)."""
        with get_cursor() as cursor:
            cursor.execute("""
                SELECT cfd.denomination, SUM(cfd.quantity) as total_qty
                FROM cash_float_denominations cfd
                JOIN cash_float_assignments cfa ON cfa.id = cfd.float_id
                WHERE cfa.status = 'PENDING_RECEIPT'
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
        transaction_id: Optional[int] = None,
        note: Optional[str] = None,
    ) -> None:
        """Insert one log row per denomination (skip qty=0)."""
        rows_to_insert = [
            (entry_type, denom, qty, float_id, transaction_id, created_by, note)
            for denom, qty in denominations.items()
            if qty > 0
        ]
        if not rows_to_insert:
            return
        with get_cursor(commit=True) as cursor:
            cursor.executemany(
                """INSERT INTO cash_denomination_logs
                   (entry_type, denomination, quantity, float_id, transaction_id, created_by, note)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                rows_to_insert,
            )
            try:
                for _entry_type, denom, qty, *_rest in rows_to_insert:
                    delta = qty if _entry_type in ("vault_in", "float_returned", "adjustment") else -qty
                    cursor.execute(
                        """INSERT OR IGNORE INTO vault_denomination_balances
                           (denomination_id, quantity, total_value)
                           VALUES (?, 0, 0)""",
                        (denom,),
                    )
                    cursor.execute(
                        """UPDATE vault_denomination_balances
                           SET quantity = quantity + ?,
                               total_value = (quantity + ?) * denomination_id,
                               last_updated = datetime('now')
                           WHERE denomination_id = ? AND quantity + ? >= 0""",
                        (delta, delta, denom, delta),
                    )
                    if cursor.rowcount == 0:
                        raise RuntimeError(
                            f"Insufficient main vault denomination {denom:,} MMK."
                        )
            except sqlite3.OperationalError as exc:
                if "no such table: vault_denomination_balances" not in str(exc):
                    raise

    def record_transaction_payment_denominations(
        self,
        transaction_id: int,
        paid_denominations: dict[int, int],
        change_denominations: dict[int, int],
    ) -> None:
        rows = []
        for denom in DENOMINATIONS:
            paid_qty = int(paid_denominations.get(denom, 0) or 0)
            change_qty = int(change_denominations.get(denom, 0) or 0)
            if paid_qty > 0 or change_qty > 0:
                rows.append((transaction_id, denom, paid_qty, change_qty))
        if not rows:
            return
        with get_cursor(commit=True) as cursor:
            cursor.executemany(
                """INSERT INTO transaction_payment_denominations
                   (transaction_id, denomination_id, quantity_paid, quantity_returned)
                   VALUES (?, ?, ?, ?)""",
                rows,
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
