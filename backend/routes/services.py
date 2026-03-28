from dataclasses import asdict

from fastapi import APIRouter, Depends

from backend.auth import get_current_user
from viewmodels.account_viewmodel import AccountViewModel

router = APIRouter(prefix="/services", tags=["services"])

_account_vm = AccountViewModel()


@router.get("/")
def get_services(current_user: dict = Depends(get_current_user)) -> list[dict]:
    from repositories.service_repository import ServiceRepository
    services = ServiceRepository().get_all_active()
    return [asdict(s) for s in services]
