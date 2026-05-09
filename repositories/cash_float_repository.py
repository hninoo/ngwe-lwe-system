from typing import Optional

from backend.database import get_cursor
from models.cash_float import CashFloat, CashFloatDenomination
from repositories.cash_denomination_repository import CashDenominationRepository


class InsufficientFloatError(Exception):
    def __init__(self, available: float, required: float) -> None:
        self.available = available
        self.required = required
        super().__init__(
            f"Insufficient cash in float. "
            f"Available: {available:,.0f}, Required: {required:,.0f}"
        )


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
            current_balance=row.get("current_balance"),
            return_denominations_json=row.get("return_denominations_json"),
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
        """Insert cash_float_assignments (PENDING_RECEIPT) + cash_float_denominations. Returns float_id."""
        with get_cursor(commit=True) as cursor:
            cursor.execute(
                """INSERT INTO cash_float_assignments
                   (employee_id, issued_by, status, total_amount, note)
                   VALUES (?, ?, 'PENDING_RECEIPT', ?, ?)""",
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
                   WHERE cfa.employee_id = ? AND cfa.status = 'PENDING_RECEIPT'
                   ORDER BY cfa.created_at DESC LIMIT 1""",
                (employee_id,),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return self._attach_denominations(self._row_to_float(row))

    def activate_float_v2(self, float_id: int) -> CashFloat:
        """PENDING_RECEIPT → ACTIVE without logging vault_out (vault was debited at issuance).
        The WHERE clause includes the expected status so concurrent duplicate calls fail safely."""
        cash_float = self.get_float(float_id)
        if cash_float is None:
            raise ValueError(f"Float {float_id} not found")
        if cash_float.status != "PENDING_RECEIPT":
            raise ValueError(f"Float {float_id} is not PENDING_RECEIPT (status={cash_float.status})")
        with get_cursor(commit=True) as cursor:
            cursor.execute(
                """UPDATE cash_float_assignments
                   SET status = 'ACTIVE', received_at = datetime('now'),
                       current_balance = total_amount
                   WHERE id = ? AND status = 'PENDING_RECEIPT'""",
                (float_id,),
            )
            if cursor.rowcount == 0:
                raise ValueError(
                    f"Float {float_id} was already activated by a concurrent request."
                )
        return self.get_float(float_id)

    def deduct_denominations(self, float_id: int, denominations: dict[int, int]) -> None:
        """Atomically deduct denomination quantities from cash_float_denominations.
        Uses AND quantity >= ? in the WHERE clause so concurrent deductions cannot
        produce negative counts.  Raises RuntimeError if any denomination is exhausted
        (triggers full rollback via the get_cursor exception handler)."""
        with get_cursor(commit=True) as cursor:
            for denom, qty in denominations.items():
                if qty > 0:
                    cursor.execute(
                        """UPDATE cash_float_denominations
                           SET quantity = quantity - ?
                           WHERE float_id = ? AND denomination = ? AND quantity >= ?""",
                        (qty, float_id, denom, qty),
                    )
                    if cursor.rowcount == 0:
                        raise RuntimeError(
                            f"Denomination {denom:,} MMK depleted by a concurrent request "
                            f"(float #{float_id}). Please retry."
                        )

    def get_denomination_balance(self, float_id: int) -> dict[int, int]:
        """Return current per-denomination quantities for a float."""
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT denomination, quantity FROM cash_float_denominations WHERE float_id = ?",
                (float_id,),
            )
            return {row["denomination"]: row["quantity"] for row in cursor.fetchall()}

    def set_pending_reconciliation(
        self, float_id: int, return_denominations_json: str
    ) -> None:
        """ACTIVE → PENDING_RECONCILIATION; store return denomination JSON.
        WHERE clause guards against duplicate concurrent transitions."""
        with get_cursor(commit=True) as cursor:
            cursor.execute(
                """UPDATE cash_float_assignments
                   SET status = 'PENDING_RECONCILIATION',
                       return_denominations_json = ?
                   WHERE id = ? AND status = 'ACTIVE'""",
                (return_denominations_json, float_id),
            )
            if cursor.rowcount == 0:
                raise ValueError(
                    f"Float {float_id} is no longer ACTIVE (concurrent state change)."
                )

    def get_return_denominations_json(self, float_id: int) -> Optional[str]:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT return_denominations_json FROM cash_float_assignments WHERE id = ?",
                (float_id,),
            )
            row = cursor.fetchone()
        return row["return_denominations_json"] if row else None

    def close_after_return(
        self, float_id: int, closing_total: float, verified_by: int
    ) -> None:
        """PENDING_RECONCILIATION → CLOSED.
        WHERE clause guards against closing an already-closed float."""
        with get_cursor(commit=True) as cursor:
            cursor.execute(
                """UPDATE cash_float_assignments
                   SET status = 'CLOSED',
                       closed_at = datetime('now'),
                       closing_total = ?,
                       current_balance = 0
                   WHERE id = ? AND status = 'PENDING_RECONCILIATION'""",
                (closing_total, float_id),
            )
            if cursor.rowcount == 0:
                raise ValueError(
                    f"Float {float_id} is no longer PENDING_RECONCILIATION (concurrent state change)."
                )

    def activate_float(
        self,
        float_id: int,
        denom_repo: CashDenominationRepository,
    ) -> CashFloat:
        """Set status=ACTIVE, received_at=now, record vault_out in denomination logs."""
        cash_float = self.get_float(float_id)
        if cash_float is None:
            raise ValueError(f"Float {float_id} not found")
        if cash_float.status not in ("PENDING", "PENDING_RECEIPT"):
            raise ValueError(f"Float {float_id} is not pending (status={cash_float.status})")

        # Build denomination dict from float denominations
        denom_dict: dict[int, int] = {
            d.denomination: d.quantity
            for d in cash_float.denominations
            if d.quantity and d.quantity > 0
        }

        with get_cursor(commit=True) as cursor:
            cursor.execute(
                """UPDATE cash_float_assignments
                   SET status = 'ACTIVE', received_at = datetime('now'),
                       current_balance = total_amount
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

    def close_float(self, *args, **kwargs) -> None:
        raise NotImplementedError(
            "close_float() is removed. Use VaultService.confirm_return() "
            "(employee initiate-return → cashier confirm-return with PIN)."
        )

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

    def deduct_float_balance(self, employee_id: int, amount: float) -> float:
        """Atomically deduct amount from employee's active float. Raises InsufficientFloatError if too low."""
        with get_cursor(commit=True) as cursor:
            cursor.execute(
                """UPDATE cash_float_assignments
                   SET current_balance = current_balance - ?
                   WHERE employee_id = ? AND status = 'ACTIVE' AND current_balance >= ?""",
                (amount, employee_id, amount),
            )
            if cursor.rowcount == 0:
                cursor.execute(
                    """SELECT current_balance FROM cash_float_assignments
                       WHERE employee_id = ? AND status = 'ACTIVE'
                       ORDER BY created_at DESC LIMIT 1""",
                    (employee_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise ValueError("No active float found for employee")
                raise InsufficientFloatError(
                    available=float(row["current_balance"] or 0), required=amount
                )
            cursor.execute(
                """SELECT current_balance FROM cash_float_assignments
                   WHERE employee_id = ? AND status = 'ACTIVE'
                   ORDER BY created_at DESC LIMIT 1""",
                (employee_id,),
            )
            row = cursor.fetchone()
        return float(row["current_balance"] or 0) if row else 0.0

    def get_open_employee_float_summaries(self) -> list[dict]:
        """Return all floats whose cash has not yet returned to the main vault.
        PENDING_RECEIPT: issued but not yet received by employee (vault already debited).
        ACTIVE: live float in use.
        PENDING_RECONCILIATION: employee initiated return, awaiting cashier confirmation."""
        with get_cursor() as cursor:
            cursor.execute(
                """SELECT cfa.id AS float_id, cfa.employee_id,
                          u.full_name AS employee_name,
                          cfa.current_balance, cfa.total_amount, cfa.created_at,
                          cfa.status
                   FROM cash_float_assignments cfa
                   JOIN users u ON u.id = cfa.employee_id
                   WHERE cfa.status IN ('PENDING_RECEIPT','ACTIVE','PENDING_RECONCILIATION')
                   ORDER BY u.full_name""",
            )
            rows = cursor.fetchall()
        return [dict(r) for r in rows]

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
