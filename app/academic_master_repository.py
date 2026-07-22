from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.academic_master_models import AcademicMaster, AcademicMasterStatus
from app.academic_master_schemas import AcademicMasterCreate, AcademicMasterUpdate


class AcademicMasterRepository:
    def __init__(self, db: Session):
        self.db = db

    def list(self, *, search: Optional[str] = None, academic_year: Optional[str] = None, regulation: Optional[str] = None, department: Optional[str] = None, semester: Optional[str] = None, status: Optional[AcademicMasterStatus] = None, page: int = 1, page_size: int = 25) -> tuple[list[AcademicMaster], int]:
        query = select(AcademicMaster)
        if search:
            term = f"%{search.strip()}%"
            query = query.where(or_(AcademicMaster.subject_code.ilike(term), AcademicMaster.subject_name.ilike(term), AcademicMaster.regulation.ilike(term), AcademicMaster.department.ilike(term), AcademicMaster.semester.ilike(term)))
        for column, value in ((AcademicMaster.academic_year, academic_year), (AcademicMaster.regulation, regulation), (AcademicMaster.department, department), (AcademicMaster.semester, semester), (AcademicMaster.status, status)):
            if value:
                query = query.where(column == value)
        total = self.db.scalar(select(func.count()).select_from(query.subquery())) or 0
        rows = self.db.scalars(query.order_by(AcademicMaster.updated_at.desc(), AcademicMaster.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
        return rows, total

    def get(self, record_id: int) -> Optional[AcademicMaster]:
        return self.db.get(AcademicMaster, record_id)

    def get_by_subject_code(self, subject_code: str, exclude_id: Optional[int] = None) -> Optional[AcademicMaster]:
        query = select(AcademicMaster).where(AcademicMaster.subject_code == subject_code)
        if exclude_id is not None:
            query = query.where(AcademicMaster.id != exclude_id)
        return self.db.scalar(query)

    def create(self, data: AcademicMasterCreate) -> AcademicMaster:
        record = AcademicMaster(**data.model_dump())
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        return record

    def update(self, record: AcademicMaster, data: AcademicMasterUpdate) -> AcademicMaster:
        for key, value in data.model_dump().items():
            setattr(record, key, value)
        self.db.commit()
        self.db.refresh(record)
        return record

    def soft_delete(self, record: AcademicMaster) -> AcademicMaster:
        record.status = AcademicMasterStatus.INACTIVE
        self.db.commit()
        self.db.refresh(record)
        return record
