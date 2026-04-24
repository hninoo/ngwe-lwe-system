from typing import Optional

from models.service_type import ServiceType
from repositories.service_type_repository import ServiceTypeRepository


class ServiceTypeViewModel:

    def __init__(
        self,
        service_type_repo: Optional[ServiceTypeRepository] = None,
    ) -> None:
        self._repo = service_type_repo or ServiceTypeRepository()

    def get_by_company(self, company_id: int) -> list[ServiceType]:
        return self._repo.get_by_company(company_id)

    def create_service_type(self, company_id: int, name: str, operation: str) -> ServiceType:
        new_id = self._repo.create({
            "company_id": company_id,
            "name": name,
            "operation": operation,
            "is_active": 1,
        })
        return self._repo.get_by_id(new_id)

    def update_service_type(self, service_type_id: int, data: dict) -> bool:
        return self._repo.update(service_type_id, data)

    def deactivate(self, service_type_id: int) -> bool:
        return self._repo.deactivate(service_type_id)
