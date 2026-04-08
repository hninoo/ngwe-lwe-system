from dataclasses import asdict

from fastapi import APIRouter, Depends

from backend.auth import get_current_user
from repositories.service_repository import ServiceRepository

router = APIRouter(prefix="/services", tags=["services"])

_service_repo = ServiceRepository()


@router.get("/")
def get_services(current_user: dict = Depends(get_current_user)) -> list[dict]:
    return [asdict(s) for s in _service_repo.get_all_active()]
