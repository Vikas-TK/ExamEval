from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.academic_master_repository import AcademicMasterRepository
from app.academic_master_schemas import AcademicMasterCreate, AcademicMasterUpdate


def list_records(db: Session, **filters):
    return AcademicMasterRepository(db).list(**filters)


def get_record(db: Session, record_id: int):
    record = AcademicMasterRepository(db).get(record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Academic master record not found")
    return record


def create_record(db: Session, data: AcademicMasterCreate):
    repository = AcademicMasterRepository(db)
    if repository.get_by_subject_code(data.subject_code):
        raise HTTPException(status_code=409, detail="Subject code already exists")
    try:
        return repository.create(data)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Duplicate academic master record") from exc


def update_record(db: Session, record_id: int, data: AcademicMasterUpdate):
    repository = AcademicMasterRepository(db)
    record = get_record(db, record_id)
    if repository.get_by_subject_code(data.subject_code, exclude_id=record_id):
        raise HTTPException(status_code=409, detail="Subject code already exists")
    try:
        return repository.update(record, data)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Duplicate academic master record") from exc


def delete_record(db: Session, record_id: int):
    record = get_record(db, record_id)
    return AcademicMasterRepository(db).soft_delete(record)
