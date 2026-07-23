"""
Phase 4 – ORM Model: EvaluationContext
Table: evaluation_contexts
Stores rich evaluation context generated per mapped question for Phase 5 AI Evaluation Agents.
"""
from __future__ import annotations

import uuid

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, func, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EvaluationContext(Base):
    """
    Evaluation Context record per question for Phase 5 AI Evaluation Agents.
    Serves as the single source of truth for Accuracy, Completeness, and Depth Agents.
    """
    __tablename__ = "evaluation_contexts"

    context_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    student_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("student_identity.evaluation_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    blueprint_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("exam_blueprints.blueprint_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # Question Identity
    question_id: Mapped[str] = mapped_column(String(255), nullable=False)
    question_number: Mapped[str] = mapped_column(String(50), nullable=False)
    question_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    question_intent: Mapped[str | None] = mapped_column(String(100), nullable=True)
    question_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    maximum_marks: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    expected_answer_depth: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Student Content
    student_answer: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Expected Answer Structure & Coverage Requirements
    expected_answer_characteristics: Mapped[list | dict | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True
    )
    expected_structure: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_coverage: Mapped[str | None] = mapped_column(Text, nullable=True)
    expected_detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Metadata & Concepts
    key_concepts: Mapped[list | dict | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True
    )
    keywords: Mapped[list | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True
    )
    subject_domain: Mapped[str | None] = mapped_column(String(255), nullable=True)
    difficulty_level: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Criteria & Visual Elements
    evaluation_criteria: Mapped[list | dict | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True
    )
    visual_elements: Mapped[list | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True
    )

    # Execution Status
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="READY_FOR_PHASE_5"
    )  # READY_FOR_PHASE_5 | CONTEXT_INCOMPLETE

    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_ec_evaluation_id", "evaluation_id"),
        Index("ix_ec_student_id", "student_id"),
        Index("ix_ec_eval_qno", "evaluation_id", "question_number"),
    )
