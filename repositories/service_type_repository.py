from typing import Optional

from backend.database import get_cursor
from models.service_type import ServiceType
from repositories.base_repository import BaseRepository


class ServiceTypeRepository(BaseRepository):

    @property
    def table(self) -> str:
        return "service_types"

    def _row_to_model(self, row: dict) -> ServiceType:
        return ServiceType(
            id=row["id"],
            company_id=row["company_id"],
            name=row["name"],
            operation=row["operation"],
            is_active=bool(row["is_active"]),
            created_at=row.get("created_at"),
            updated_at=row.get("updated_at"),
        )

    def get_by_company(self, company_id: int) -> list[ServiceType]:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM service_types WHERE company_id = ? AND is_active = 1",
                (company_id,),
            )
            rows = cursor.fetchall()
        return [self._row_to_model(r) for r in rows]

    def get_all_active(self) -> list[ServiceType]:
        with get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM service_types WHERE is_active = 1"
            )
            rows = cursor.fetchall()
        return [self._row_to_model(r) for r in rows]

    def deactivate(self, service_type_id: int) -> bool:
        with get_cursor(commit=True) as cursor:
            cursor.execute(
                "UPDATE service_types SET is_active = 0 WHERE id = ?",
                (service_type_id,),
            )
            return cursor.rowcount > 0
