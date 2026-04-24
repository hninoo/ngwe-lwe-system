from typing import Optional

from models.company import Company
from models.service_type import ServiceType
from repositories.company_repository import CompanyRepository
from repositories.service_type_repository import ServiceTypeRepository


class CompanyViewModel:

    def __init__(
        self,
        company_repo: Optional[CompanyRepository] = None,
        service_type_repo: Optional[ServiceTypeRepository] = None,
    ) -> None:
        self._company_repo = company_repo or CompanyRepository()
        self._service_type_repo = service_type_repo or ServiceTypeRepository()

    def get_all_active(self) -> list[Company]:
        return self._company_repo.get_all_active()

    def get_service_types(self, company_id: int) -> list[ServiceType]:
        return self._service_type_repo.get_by_company(company_id)

    def create_company(self, name: str, category: str) -> Company:
        new_id = self._company_repo.create({
            "name": name,
            "category": category,
            "is_active": 1,
        })
        return self._company_repo.get_by_id(new_id)

    def update_company(self, company_id: int, data: dict) -> bool:
        return self._company_repo.update(company_id, data)

    def deactivate_company(self, company_id: int) -> bool:
        return self._company_repo.deactivate(company_id)

    def upload_logo_path(self, company_id: int, logo_path: str) -> bool:
        return self._company_repo.update(company_id, {"logo_path": logo_path})
