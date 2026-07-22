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