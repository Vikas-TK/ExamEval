import enum
import uuid

from sqlalchemy import Column, String, Float, Boolean, DateTime, Enum as SAEnum, func, Index, ForeignKey, JSON, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.db.base import Base


class EvaluationStatus(str, enum.Enum):
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    FAILED = "FAILED"


class StudentIdentity(Base):
    """
    ZERO-TRUST BOUNDARY.
    This is the ONLY table that stores the keyed student identity hash.
    In production, lock this table down with a dedicated DB role that
    the pipeline/OCR/worker processes are NOT granted (least privilege) —
    only the ingestion endpoint and an audited admin role should read it.
    """
    __tablename__ = "student_identity"

    evaluation_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    student_hash = Column(String(64), nullable=False, index=True)
    regulation = Column(String, nullable=False)
    semester = Column(String, nullable=False)
    subject_id = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class EvaluationRecord(Base):
    """
    Everything downstream of ingestion (queue, OpenCV, OCR, storage) reads
    and writes ONLY this table. No register_number or student PII column
    exists here, by design — not just by convention.
    """
    __tablename__ = "evaluation_records"

    evaluation_id = Column(UUID(as_uuid=True), ForeignKey("student_identity.evaluation_id"), primary_key=True)
    subject_id = Column(String, nullable=False)
    status = Column(SAEnum(EvaluationStatus, name="evaluationstatus"), nullable=False,
                    default=EvaluationStatus.PROCESSING, index=True)

    # QualityReport, flattened
    blur_score = Column(Float, nullable=True)
    brightness_score = Column(Float, nullable=True)
    contrast_score = Column(Float, nullable=True)
    skew_angle = Column(Float, nullable=True)
    is_skewed = Column(Boolean, nullable=True)
    quality_passed = Column(Boolean, nullable=True)
    width = Column(Float, nullable=True)
    height = Column(Float, nullable=True)
    noise_score = Column(Float, nullable=True)
    resolution_passed = Column(Boolean, nullable=True)

    # OCR output — kept as JSONB to match the required nested pages/
    # visual_elements structure without over-normalizing for Phase 1.
    ocr_data = Column(JSONB().with_variant(JSON, "sqlite"), nullable=True)

    needs_manual_review = Column(Boolean, nullable=False, default=False)
    overall_confidence = Column(Float, nullable=True)

    raw_s3_url = Column(String, nullable=True)
    enhanced_s3_url = Column(String, nullable=True)
    transcript_s3_url = Column(String, nullable=True)

    error_message = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_evaluation_records_status_created_at", "status", "created_at"),
    )
