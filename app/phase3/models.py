"""
Phase 3 – PostgreSQL ORM Model: QuestionAnswerMapping
Stores the validated structured Q&A records for each student evaluation.
"""
from __future__ import annotations

import enum
import uuid

from sqlalchemy import Column, DateTime, Float, Index, Integer, String, Text, func, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class MappingStatus(str, enum.Enum):
    MAPPED = "MAPPED"
    UNMAPPED = "UNMAPPED"
    SKIPPED = "SKIPPED"


class ValidationStatus(str, enum.Enum):
    VALID = "VALID"
    INVALID = "INVALID"
    WARNING = "WARNING"


class QuestionAnswerMapping(Base):
    """
    Stores one record per question per student evaluation.
    Contains the student's segmented answer, question metadata from the blueprint,
    and mapping/validation status — ready for Phase 4 (Evaluation Context Builder).
    No student PII is stored here; only evaluation_id (UUID) links back to StudentIdentity.
    """
    __tablename__ = "question_answer_mappings"

    mapping_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("student_identity.evaluation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    blueprint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exam_blueprints.blueprint_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Blueprint question reference
    question_id: Mapped[str] = mapped_column(String(255), nullable=False)
    question_number: Mapped[str] = mapped_column(String(50), nullable=False)
    question_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    maximum_marks: Mapped[float | None] = mapped_column(Float, nullable=True)
    question_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    section_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Student answer
    student_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    answer_length: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    visual_elements: Mapped[list | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True
    )

    # Anchor detection metadata
    anchor_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    anchor_text: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Mapping & validation
    mapping_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=MappingStatus.MAPPED
    )
    validation_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default=ValidationStatus.VALID
    )
    validation_warnings: Mapped[list | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True
    )
    validation_errors: Mapped[list | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True
    )

    # Sequencing
    question_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_qa_mapping_evaluation_id", "evaluation_id"),
        Index("ix_qa_mapping_blueprint_id", "blueprint_id"),
        Index("ix_qa_mapping_eval_qno", "evaluation_id", "question_number"),
    )
