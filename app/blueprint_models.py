from __future__ import annotations

import uuid

from sqlalchemy import DateTime, Index, Integer, String, UniqueConstraint, func, JSON
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class ExamBlueprint(Base):
    """Reusable exam-level document; deliberately contains no student identity."""

    __tablename__ = "exam_blueprints"

    blueprint_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True,
                                                     default=uuid.uuid4)
    exam_name: Mapped[str] = mapped_column(String(255), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    subject_code: Mapped[str] = mapped_column(String(100), nullable=False)
    regulation: Mapped[str] = mapped_column(String(100), nullable=False)
    semester: Mapped[str] = mapped_column(String(100), nullable=False)
    department: Mapped[str] = mapped_column(String(255), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    maximum_marks: Mapped[float] = mapped_column(nullable=False)
    sections: Mapped[list] = mapped_column(JSONB().with_variant(JSON, "sqlite"), nullable=False)
    source_ocr: Mapped[dict] = mapped_column(JSONB().with_variant(JSON, "sqlite"), nullable=False)
    faculty_answer_key: Mapped[list | None] = mapped_column(JSONB().with_variant(JSON, "sqlite"), nullable=True)
    blueprint_s3_url: Mapped[str | None] = mapped_column(String, nullable=True)
    faculty_answer_key_s3_url: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                               onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("exam_name", "subject_code", "regulation", "semester",
                         name="uq_exam_blueprint_identity"),
        Index("ix_exam_blueprints_subject_code", "subject_code"),
    )


class AnswerKeyVersion(Base):
    """Answer key version management supporting PDF, DOCX, Handwritten, Manual, and AI modes."""
    __tablename__ = "answer_key_versions"

    version_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    blueprint_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    author: Mapped[str] = mapped_column(String(255), nullable=False, default="Faculty Admin")
    format_type: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")  # pdf | docx | handwritten | manual | ai_generated
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="Approved")     # Draft | Approved | Archived
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True)
    answer_key_data: Mapped[list | dict] = mapped_column(JSONB().with_variant(JSON, "sqlite"), nullable=False)
    s3_url: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class AuditLog(Base):
    """Audit trail logging manual changes to OCR, Blueprints, Q&A Mappings, and Evaluation Contexts."""
    __tablename__ = "audit_logs"

    log_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)  # ocr | blueprint | qa_mapping | context | evaluation
    entity_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False)       # create | edit | approve | retrigger
    performed_by: Mapped[str] = mapped_column(String(255), nullable=False, default="Faculty Admin")
    previous_state: Mapped[dict | list | None] = mapped_column(JSONB().with_variant(JSON, "sqlite"), nullable=True)
    new_state: Mapped[dict | list | None] = mapped_column(JSONB().with_variant(JSON, "sqlite"), nullable=True)
    remarks: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())