from typing import Optional

from backend.database import get_cursor
from models.cash_float import CashFloat, CashFloatDenomination
from repositories.cash_denomination_repository import CashDenominationRepository


class CashFloatRepository:

    def _row_to_float(self, row: dict) -> CashFloat:
        return CashFloat(
            id=row["id"],
            employee_id=row["employee_id"],
            employee_name=row.get("employee_name"),
            issued_by=row["issued_by"],
            issued_by_name=row.get("issued_by_name"),
            status=row["status"],
            total_amount=row["total_amount"],
            received_at=row.get("received_at"),
            closed_at=row.get("closed_at"),
            closing_total=row.get("closing_total"),
            note=row.get("note"),
            created_at=row["created_at"],
            denominations=[],
        )

    def _attach_denominations(self, cash_float: CashFloat) -> CashFloat:
        cash_float.denominations = self.get_float_denominations(cash_float.id)
        return cash_float

    def create_float(
        self,
        employee_id: int,
        issued_by: int,
        denominations: dict[int, int],
        total_amount: float,
        note: Optional[str] = None,
    ) -> int:
        """Insert cash_float_assignments (PENDING) + cash_float_denominations. Returns float_id."""
        with get_cursor(commit=True) as cursor:
            cursor.execute(
                """INSERT INTO cash_float_assignments
                   (employee_id, issued_by, status, total_amount, note)
                   VALUES (?, ?, 'PENDING', ?, ?)""",
                (employee_id, issued_by, total_amount, note),
            )
            float_id = cursor.lastrowid
            rows = [
                (float_id, denom, qty)
                for denom, qty in denominations.items()
                if qty > 0
            ]
            if rows:
                cursor.executemany(
                    """INSERT INTO cash_float_denominations (float_id, denomination, quantity)
                       VALUES (?, ?, ?)""",
                    rows,
                )
        return float_id

    def get_float(self, float_id: int) -> Optional[CashFloat]:
        """Get float with denominations list populated."""
        with get_cursor() as cursor:
            cursor.execute(
                """SELECT cfa.*,
                          e.full_name  AS employee_name,
                          i.full_name  AS issued_by_name
                   FROM cash_float_assignments cfa
                   JOIN users e ON e.id = cfa.employee_id
                   JOIN users i ON i.id = cfa.issued_by
                   WHERE cfa.id = ?""",
                (float_id,),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return self._attach_denominations(self._row_to_float(row))

    def list_floats(
        self,
        employee_id: Optional[int] = None,
        status: Optional[str] = None,
    ) -> list[CashFloat]:
        """List floats, optionally filtered. Joins users for employee_name and issued_by_name."""
        conditions = []
        params: list = []
        if employee_id is not None:
            conditions.append("cfa.employee_id = ?")
            params.append(employee_id)
        if status is not None:
            conditions.append("cfa.status = ?")
            params.append(status)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        with get_cursor() as cursor:
            cursor.execute(
                f"""SELECT cfa.*,
                           e.full_name AS employee_name,
                           i.full_name AS issued_by_name
                    FROM cash_float_assignments cfa
                    JOIN users e ON e.id = cfa.employee_id
                    JOIN users i ON i.id = cfa.issued_by
                    {where}
                    ORDER BY cfa.created_at DESC""",
                params,
            )
            rows = cursor.fetchall()

        floats = [self._row_to_float(r) for r in rows]
        for f in floats:
            self._attach_denominations(f)
        return floats

    def get_active_float_for_employee(self, employee_id: int) -> Optional[CashFloat]:
        with get_cursor() as cursor:
            cursor.execute(
                """SELECT cfa.*,
                          e.full_name AS employee_name,
                          i.full_name AS issued_by_name
                   FROM cash_float_assignments cfa
                   JOIN users e ON e.id = cfa.employee_id
                   JOIN users i ON i.id = cfa.issued_by
                   WHERE cfa.employee_id = ? AND cfa.status = 'ACTIVE'
                   ORDER BY cfa.created_at DESC LIMIT 1""",
                (employee_id,),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return self._attach_denominations(self._row_to_float(row))

    def get_pending_float_for_employee(self, employee_id: int) -> Optional[CashFloat]:
        with get_cursor() as cursor:
            cursor.execute(
                """SELECT cfa.*,
                          e.full_name AS employee_name,
                          i.full_name AS issued_by_name
                   FROM cash_float_assignments cfa
                   JOIN users e ON e.id = cfa.employee_id
                   JOIN users i ON i.id = cfa.issued_by
                   WHERE cfa.employee_id = ? AND cfa.status = 'PENDING'
                   ORDER BY cfa.created_at DESC LIMIT 1""",
                (employee_id,),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return self._attach_denominations(self._row_to_float(row))

    def activate_float(
        self,
        float_id: int,
        denom_repo: CashDenominationRepository,
    ) -> CashFloat:
        """Set status=ACTIVE, received_at=now, record vault_out in denomination logs."""
        cash_float = self.get_float(float_id)
        if cash_float is None:
            raise ValueError(f"Float {float_id} not found")
        if cash_float.status != "PENDING":
            raise ValueError(f"Float {float_id} is not PENDING (status={cash_float.status})")

        # Build denomination dict from float denominations
        denom_dict: dict[int, int] = {
            d.denomination: d.quantity
            for d in cash_float.denominations
            if d.quantity and d.quantity > 0
        }

        with get_cursor(commit=True) as cursor:
            cursor.execute(
                """UPDATE cash_float_assignments
                   SET status = 'ACTIVE', received_at = datetime('now')
                   WHERE id = ?""",
                (float_id,),
            )

        # Record vault_out for each denomination
        if denom_dict:
            denom_repo.record_bulk_entry(
                entry_type="vault_out",
                denominations=denom_dict,
                created_by=cash_float.issued_by,
                float_id=float_id,
                note=f"Float #{float_id} activated",
            )

        return self.get_float(float_id)

    def close_float(
        self,
        float_id: int,
        closing_denominations: dict[int, int],
        denom_repo: CashDenominationRepository,
        note: Optional[str] = None,
    ) -> CashFloat:
        """Set status=CLOSED, closed_at=now, closing_total=sum, record float_returned."""
        cash_float = self.get_float(float_id)
        if cash_float is None:
            raise ValueError(f"Float {float_id} not found")
        if cash_float.status not in ("ACTIVE", "PENDING"):
            raise ValueError(f"Float {float_id} cannot be closed (status={cash_float.status})")

        closing_total = sum(
            denom * qty for denom, qty in closing_denominations.items() if qty > 0
        )

        with get_cursor(commit=True) as cursor:
            cursor.execute(
                """UPDATE cash_float_assignments
                   SET status = 'CLOSED',
                       closed_at = datetime('now'),
                       closing_total = ?,
                       note = COALESCE(?, note)
                   WHERE id = ?""",
                (closing_total, note, float_id),
            )

        # Record float_returned for denominations being returned
        returned = {d: q for d, q in closing_denominations.items() if q > 0}
        if returned:
            denom_repo.record_bulk_entry(
                entry_type="float_returned",
                denominations=returned,
                created_by=cash_float.employee_id,
                float_id=float_id,
                note=note or f"Float #{float_id} closed",
            )

        return self.get_float(float_id)

    # ── Convenience wrappers called by the cashier route ─────────────────────

    def get_all_floats(self) -> list[CashFloat]:
        return self.list_floats()

    def get_floats_for_employee(self, employee_id: int) -> list[CashFloat]:
        return self.list_floats(employee_id=employee_id)

    def issue_float(
        self,
        employee_id: int,
        issued_by: int,
        denominations: dict[int, int],
        denom_repo: CashDenominationRepository,
        note: Optional[str] = None,
    ) -> CashFloat:
        """Create a PENDING float and return the full CashFloat object."""
        total = sum(d * q for d, q in denominations.items() if q > 0)
        float_id = self.create_float(
            employee_id=employee_id,
            issued_by=issued_by,
            denominations=denominations,
            total_amount=total,
            note=note,
        )
        return self.get_float(float_id)

    # ─────────────────────────────────────────────────────────────────────────

    def get_float_denominations(self, float_id: int) -> list[CashFloatDenomination]:
        with get_cursor() as cursor:
            cursor.execute(
                """SELECT * FROM cash_float_denominations
                   WHERE float_id = ?
                   ORDER BY denomination""",
                (float_id,),
            )
            rows = cursor.fetchall()
        return [
            CashFloatDenomination(
                id=row["id"],
                float_id=row["float_id"],
                denomination=row["denomination"],
                quantity=row["quantity"],
            )
            for row in rows
        ]
