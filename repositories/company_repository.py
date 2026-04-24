from typing import Optional

from backend.database import get_cursor
from models.company import Company
from repositories.base_repository import BaseRepository


class CompanyRepository(BaseRepository):

    @property
    def table(self) -> str:
        return "companies"

    def _row_to_model(self, row: dict) -> Company:
        return Company(
            id=row["id"],
            name=row["name"],
            logo_path=row.get("logo_path"),
            category=row.get("category"),
            is_active=bool(row["is_active"]),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

    def get_all_active(self) -> list[Company]:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM companies WHERE is_active = 1 ORDER BY name"
            )
            rows = cursor.fetchall()
        return [self._row_to_model(r) for r in rows]

    def deactivate(self, company_id: int) -> bool:
        """Set is_active = 0 for the company and cascade to all its service_types."""
        with get_cursor(commit=True) as cursor:
            cursor.execute(
                "UPDATE companies SET is_active = 0 WHERE id = ?",
                (company_id,),
            )
            affected = cursor.rowcount > 0
            cursor.execute(
                "UPDATE service_types SET is_active = 0 WHERE company_id = ?",
                (company_id,),
            )
        return affected
