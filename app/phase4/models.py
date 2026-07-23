"""
Phase 4 – ORM Model: AnswerEvaluation
One row per question per student evaluation — stores AI-scored marks.
"""
from __future__ import annotations

import uuid

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, func, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AnswerEvaluation(Base):
    """
    AI-scored answer per question per evaluation.
    Feeds the Faculty Marks Matrix and student transcript downloads.
    No student PII here — evaluation_id links to StudentIdentity.
    """
    __tablename__ = "answer_evaluations"

    eval_result_id: Mapped[uuid.UUID] = mapped_column(
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

    # Question identity (from blueprint)
    question_id: Mapped[str] = mapped_column(String(255), nullable=False)
    question_number: Mapped[str] = mapped_column(String(50), nullable=False)
    question_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    section_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    question_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    maximum_marks: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    question_type: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Student answer (copied from Q&A mapping)
    student_answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    visual_elements: Mapped[list | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=True
    )

    # Optional answer key provided by faculty
    answer_key: Mapped[str | None] = mapped_column(Text, nullable=True)

    # AI evaluation output
    scored_marks: Mapped[float | None] = mapped_column(Float, nullable=True)
    ai_feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    evaluation_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="PENDING"
    )  # SCORED | SKIPPED | ERROR | PENDING

    created_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[object] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("ix_ae_evaluation_id", "evaluation_id"),
        Index("ix_ae_blueprint_id", "blueprint_id"),
        Index("ix_ae_eval_qno", "evaluation_id", "question_number"),
    )
