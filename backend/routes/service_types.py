from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.auth import get_current_user
from viewmodels.service_type_viewmodel import ServiceTypeViewModel

router = APIRouter(prefix="/service-types", tags=["service_types"])

_service_type_vm = ServiceTypeViewModel()


class ServiceTypeUpdate(BaseModel):
    name: Optional[str] = None
    operation: Optional[str] = None
    is_active: Optional[bool] = None


# ── PATCH /service-types/{service_type_id} ───────────────────────────────────

@router.patch("/{service_type_id}")
def update_service_type(
    service_type_id: int,
    body: ServiceTypeUpdate,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    _service_type_vm.update_service_type(service_type_id, data)
    return {"message": "ServiceType updated"}


# ── DELETE /service-types/{service_type_id} (deactivate) ─────────────────────

@router.delete("/{service_type_id}")
def deactivate_service_type(
    service_type_id: int,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    result = _service_type_vm.deactivate(service_type_id)
    if not result:
        raise HTTPException(status_code=404, detail="ServiceType not found")
    return {"message": "ServiceType deactivated"}
