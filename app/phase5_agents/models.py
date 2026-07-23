"""
Phase 5 – ORM Models: accuracy_reports, completeness_reports, depth_reports
Independent evaluation reports stored per question per agent.
"""
from __future__ import annotations

import uuid
from sqlalchemy import DateTime, Float, Index, String, Text, func, ForeignKey, JSON
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AccuracyReport(Base):
    """Stores independent technical accuracy evaluation output per question."""
    __tablename__ = "accuracy_reports"

    report_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_identity.evaluation_id", ondelete="CASCADE"), nullable=False, index=True
    )
    blueprint_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    question_id: Mapped[str] = mapped_column(String(255), nullable=False)
    question_number: Mapped[str] = mapped_column(String(50), nullable=False)

    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    percentage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    correct_concepts: Mapped[list | None] = mapped_column(JSONB().with_variant(JSON, "sqlite"), nullable=True)
    incorrect_concepts: Mapped[list | None] = mapped_column(JSONB().with_variant(JSON, "sqlite"), nullable=True)
    technical_errors: Mapped[list | None] = mapped_column(JSONB().with_variant(JSON, "sqlite"), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="COMPLETED")  # COMPLETED | FAILED

    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_acc_eval_qno", "evaluation_id", "question_number"),
    )


class CompletenessReport(Base):
    """Stores independent coverage and completeness evaluation output per question."""
    __tablename__ = "completeness_reports"

    report_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_identity.evaluation_id", ondelete="CASCADE"), nullable=False, index=True
    )
    blueprint_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    question_id: Mapped[str] = mapped_column(String(255), nullable=False)
    question_number: Mapped[str] = mapped_column(String(50), nullable=False)

    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    percentage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    covered_points: Mapped[list | None] = mapped_column(JSONB().with_variant(JSON, "sqlite"), nullable=True)
    missing_points: Mapped[list | None] = mapped_column(JSONB().with_variant(JSON, "sqlite"), nullable=True)
    missing_keywords: Mapped[list | None] = mapped_column(JSONB().with_variant(JSON, "sqlite"), nullable=True)
    missing_concepts: Mapped[list | None] = mapped_column(JSONB().with_variant(JSON, "sqlite"), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="COMPLETED")  # COMPLETED | FAILED

    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_cmp_eval_qno", "evaluation_id", "question_number"),
    )


class DepthReport(Base):
    """Stores independent depth and reasoning evaluation output per question."""
    __tablename__ = "depth_reports"

    report_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    evaluation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("student_identity.evaluation_id", ondelete="CASCADE"), nullable=False, index=True
    )
    blueprint_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    question_id: Mapped[str] = mapped_column(String(255), nullable=False)
    question_number: Mapped[str] = mapped_column(String(50), nullable=False)

    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    percentage: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    strong_sections: Mapped[list | None] = mapped_column(JSONB().with_variant(JSON, "sqlite"), nullable=True)
    weak_sections: Mapped[list | None] = mapped_column(JSONB().with_variant(JSON, "sqlite"), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="COMPLETED")  # COMPLETED | FAILED

    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_dph_eval_qno", "evaluation_id", "question_number"),
    )
