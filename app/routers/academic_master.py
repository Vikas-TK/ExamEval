from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.academic_master_models import AcademicMasterStatus
from app.academic_master_schemas import AcademicMasterCreate, AcademicMasterListResponse, AcademicMasterOut, AcademicMasterUpdate
from app.academic_master_service import create_record, delete_record, get_record, list_records, update_record
from app.database import get_db
from app.security import require_api_key

router = APIRouter(prefix="/api/academic-master", tags=["academic-master"])


@router.get("", response_model=AcademicMasterListResponse)
def list_academic_master(
    search: Optional[str] = Query(default=None, max_length=100),
    academic_year: Optional[str] = None,
    regulation: Optional[str] = None,
    department: Optional[str] = None,
    semester: Optional[str] = None,
    status: Optional[AcademicMasterStatus] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    _auth: None = Depends(require_api_key),
):
    items, total = list_records(db, search=search, academic_year=academic_year, regulation=regulation, department=department, semester=semester, status=status, page=page, page_size=page_size)
    return AcademicMasterListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/search", response_model=AcademicMasterListResponse)
def search_academic_master(
    search: Optional[str] = Query(default=None, max_length=100),
    academic_year: Optional[str] = None,
    regulation: Optional[str] = None,
    department: Optional[str] = None,
    semester: Optional[str] = None,
    status: Optional[AcademicMasterStatus] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    db: Session = Depends(get_db),
    _auth: None = Depends(require_api_key),
):
    return list_academic_master(search, academic_year, regulation, department, semester, status, page, page_size, db, _auth)


@router.get("/{record_id}", response_model=AcademicMasterOut)
def get_academic_master(record_id: int, db: Session = Depends(get_db), _auth: None = Depends(require_api_key)):
    return get_record(db, record_id)


@router.post("", response_model=AcademicMasterOut, status_code=201)
def create_academic_master(data: AcademicMasterCreate, db: Session = Depends(get_db), _auth: None = Depends(require_api_key)):
    return create_record(db, data)


@router.put("/{record_id}", response_model=AcademicMasterOut)
def update_academic_master(record_id: int, data: AcademicMasterUpdate, db: Session = Depends(get_db), _auth: None = Depends(require_api_key)):
    return update_record(db, record_id, data)


@router.delete("/{record_id}", response_model=AcademicMasterOut)
def delete_academic_master(record_id: int, db: Session = Depends(get_db), _auth: None = Depends(require_api_key)):
    return delete_record(db, record_id)
