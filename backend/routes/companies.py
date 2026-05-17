import os
from dataclasses import asdict
from pathlib import Path
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from sqlite3 import IntegrityError

from backend.auth import get_current_user
from viewmodels.company_viewmodel import CompanyViewModel
from viewmodels.service_type_viewmodel import ServiceTypeViewModel

router = APIRouter(prefix="/companies", tags=["companies"])

_company_vm = CompanyViewModel()
_service_type_vm = ServiceTypeViewModel()

ALLOWED_MIME_TYPES = {"image/png", "image/jpeg"}
MAX_LOGO_SIZE_BYTES = 200 * 1024  # 200 KB
LOGO_DIR = Path("assets/logos")


class CompanyCreate(BaseModel):
    name: str = Field(min_length=1)
    category: Literal["Pay", "Bank", "Both"]

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Company name is required.")
        return value


class CompanyUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[Literal["Pay", "Bank", "Both"]] = None
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def optional_name_not_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Company name is required.")
        return value


class ServiceTypeCreate(BaseModel):
    name: str = Field(min_length=1)
    operation: Literal["CashIn", "CashOut", "Transfer", "Exchange", "All"]

    @field_validator("name")
    @classmethod
    def service_name_not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Service type name is required.")
        return value


# ── GET /companies/ ──────────────────────────────────────────────────────────

@router.get("/")
def get_companies(
    current_user: dict = Depends(get_current_user),
) -> list[dict]:
    companies = _company_vm.get_all_active()
    return [asdict(c) for c in companies]


# ── POST /companies/ ─────────────────────────────────────────────────────────

@router.post("/")
def create_company(
    body: CompanyCreate,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    try:
        company = _company_vm.create_company(body.name, body.category)
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Company already exists") from exc
    return {"id": company.id, "message": "Company created"}


# ── GET /companies/{company_id} ───────────────────────────────────────────────

@router.get("/{company_id}")
def get_company(
    company_id: int,
    current_user: dict = Depends(get_current_user),
) -> dict:
    from repositories.company_repository import CompanyRepository
    repo = CompanyRepository()
    company = repo.get_by_id(company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    return asdict(company)


# ── PATCH /companies/{company_id} ────────────────────────────────────────────

@router.patch("/{company_id}")
def update_company(
    company_id: int,
    body: CompanyUpdate,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    data = body.model_dump(exclude_none=True)
    if not data:
        raise HTTPException(status_code=400, detail="No fields to update")
    # If deactivating, use cascade deactivate
    if data.get("is_active") is False or data.get("is_active") == 0:
        if not _company_vm.deactivate_company(company_id):
            raise HTTPException(status_code=404, detail="Company not found")
        return {"message": "Company deactivated"}
    try:
        updated = _company_vm.update_company(company_id, data)
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="Company already exists") from exc
    if not updated:
        raise HTTPException(status_code=404, detail="Company not found")
    return {"message": "Company updated"}


# ── POST /companies/{company_id}/logo ─────────────────────────────────────────

@router.post("/{company_id}/logo")
async def upload_logo(
    company_id: int,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    from repositories.company_repository import CompanyRepository
    if CompanyRepository().get_by_id(company_id) is None:
        raise HTTPException(status_code=404, detail="Company not found")

    # Validate MIME type
    content_type = file.content_type or ""
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid file type '{content_type}'. Allowed: png, jpeg",
        )

    # Read all bytes and validate size
    file_bytes = await file.read()
    if len(file_bytes) > MAX_LOGO_SIZE_BYTES:
        raise HTTPException(
            status_code=422,
            detail=f"File too large ({len(file_bytes)} bytes). Max: {MAX_LOGO_SIZE_BYTES} bytes",
        )

    # Determine extension
    ext_map = {
        "image/png": "png",
        "image/jpeg": "jpg",
    }
    ext = ext_map.get(content_type, "png")

    # Write file
    LOGO_DIR.mkdir(parents=True, exist_ok=True)
    logo_filename = f"{company_id}.{ext}"
    logo_path = LOGO_DIR / logo_filename
    logo_path.write_bytes(file_bytes)

    # Update DB
    relative_path = str(logo_path)
    if not _company_vm.upload_logo_path(company_id, relative_path):
        raise HTTPException(status_code=404, detail="Company not found")

    return {"message": "Logo uploaded", "logo_path": relative_path}


# ── GET /companies/{company_id}/logo ─────────────────────────────────────────

@router.get("/{company_id}/logo")
def get_logo(
    company_id: int,
    current_user: dict = Depends(get_current_user),
) -> FileResponse:
    from repositories.company_repository import CompanyRepository
    repo = CompanyRepository()
    company = repo.get_by_id(company_id)
    if company is None:
        raise HTTPException(status_code=404, detail="Company not found")
    if not company.logo_path:
        raise HTTPException(status_code=404, detail="No logo set for this company")
    logo_root = LOGO_DIR.resolve()
    logo_file = Path(company.logo_path).resolve()
    try:
        logo_file.relative_to(logo_root)
    except ValueError:
        raise HTTPException(status_code=404, detail="Logo file not found on disk")
    if not logo_file.exists() or not logo_file.is_file():
        raise HTTPException(status_code=404, detail="Logo file not found on disk")

    # Determine MIME type from extension
    suffix = logo_file.suffix.lower()
    mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
    media_type = mime_map.get(suffix, "application/octet-stream")
    return FileResponse(str(logo_file), media_type=media_type)


# ── GET /companies/{company_id}/service-types ─────────────────────────────────

@router.get("/{company_id}/service-types")
def get_service_types(
    company_id: int,
    current_user: dict = Depends(get_current_user),
) -> list[dict]:
    from repositories.company_repository import CompanyRepository
    if CompanyRepository().get_by_id(company_id) is None:
        raise HTTPException(status_code=404, detail="Company not found")
    sts = _company_vm.get_service_types(company_id)
    return [asdict(st) for st in sts]


# ── POST /companies/{company_id}/service-types ────────────────────────────────

@router.post("/{company_id}/service-types", status_code=201)
def create_service_type(
    company_id: int,
    body: ServiceTypeCreate,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    from repositories.company_repository import CompanyRepository
    if CompanyRepository().get_by_id(company_id) is None:
        raise HTTPException(status_code=404, detail="Company not found")
    try:
        st = _service_type_vm.create_service_type(company_id, body.name, body.operation)
    except IntegrityError as exc:
        raise HTTPException(status_code=409, detail="ServiceType already exists") from exc
    return {"id": st.id, "message": "ServiceType created"}


@router.delete("/{company_id}")
def delete_company(
    company_id: int,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if current_user["role"] != "owner":
        raise HTTPException(status_code=403, detail="Owner only")
    if not _company_vm.deactivate_company(company_id):
        raise HTTPException(status_code=404, detail="Company not found")
    return {"message": "Company deactivated"}
