import enum

from sqlalchemy import Column, DateTime, Enum as SAEnum, Index, Integer, String, func

from app.database import Base


class AcademicMasterStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class AcademicMaster(Base):
    __tablename__ = "academic_master"

    id = Column(Integer, primary_key=True, autoincrement=True)
    academic_year = Column(String(20), nullable=False)
    regulation = Column(String(50), nullable=False)
    department = Column(String(100), nullable=False)
    semester = Column(String(20), nullable=False)
    subject_code = Column(String(50), nullable=False, unique=True, index=True)
    subject_name = Column(String(200), nullable=False)
    credits = Column(Integer, nullable=True)
    status = Column(SAEnum(AcademicMasterStatus, name="academicmasterstatus"), nullable=False, default=AcademicMasterStatus.ACTIVE, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    created_by = Column(String(100), nullable=True)

    __table_args__ = (
        Index("ix_academic_master_filters", "academic_year", "regulation", "department", "semester", "status"),
    )
