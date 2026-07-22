from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.academic_master_models import AcademicMasterStatus


class AcademicMasterBase(BaseModel):
    academic_year: str = Field(min_length=1, max_length=20)
    regulation: str = Field(min_length=1, max_length=50)
    department: str = Field(min_length=1, max_length=100)
    semester: str = Field(min_length=1, max_length=20)
    subject_code: str = Field(min_length=1, max_length=50)
    subject_name: str = Field(min_length=1, max_length=200)
    credits: Optional[int] = Field(default=None, ge=0, le=20)
    status: AcademicMasterStatus = AcademicMasterStatus.ACTIVE

    @field_validator("academic_year", "regulation", "department", "semester", "subject_code", "subject_name")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("This field cannot be empty")
        return value

    @field_validator("semester")
    @classmethod
    def validate_semester(cls, value: str) -> str:
        normalized = value.strip().upper()
        valid = {f"SEM-{index:02d}" for index in range(1, 13)} | {str(index) for index in range(1, 13)}
        if normalized not in valid:
            raise ValueError("Semester must be a valid value such as SEM-01 or 1")
        return normalized if normalized.startswith("SEM-") else f"SEM-{int(normalized):02d}"


class AcademicMasterCreate(AcademicMasterBase):
    created_by: Optional[str] = Field(default=None, max_length=100)


class AcademicMasterUpdate(AcademicMasterBase):
    pass


class AcademicMasterOut(AcademicMasterBase):
    id: int
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    model_config = ConfigDict(from_attributes=True)


class AcademicMasterListResponse(BaseModel):
    items: list[AcademicMasterOut]
    total: int
    page: int
    page_size: int
