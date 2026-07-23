"""
Phase 4 – Database Repository for EvaluationContext
Encapsulates all PostgreSQL database operations using the Repository Pattern.
"""
from __future__ import annotations

import uuid
import logging
from typing import List, Optional

from sqlalchemy.orm import Session
from app.phase4_context.models import EvaluationContext
from app.phase4_context.schemas import EvaluationContextOut

logger = logging.getLogger(__name__)


class EvaluationContextRepository:
    """Repository for CRUD operations on evaluation_contexts table."""

    def __init__(self, db: Session):
        self.db = db

    def save_evaluation_contexts(self, contexts: List[EvaluationContextOut]) -> List[EvaluationContext]:
        """Saves or updates evaluation context records in PostgreSQL database."""
        if not contexts:
            return []

        saved_records: list[EvaluationContext] = []

        for ctx in contexts:
            # Check existing record for this evaluation and question
            existing = self.db.query(EvaluationContext).filter_by(
                evaluation_id=ctx.evaluation_id,
                question_id=ctx.question_id,
            ).first()

            if existing:
                existing.student_id = ctx.student_id
                existing.blueprint_id = ctx.blueprint_id
                existing.question_number = ctx.question_number
                existing.question_text = ctx.question_text
                existing.question_intent = ctx.question_intent
                existing.question_type = ctx.question_type
                existing.maximum_marks = ctx.maximum_marks
                existing.expected_answer_depth = ctx.expected_answer_depth
                existing.student_answer = ctx.student_answer
                existing.expected_answer_characteristics = ctx.expected_answer_characteristics
                existing.expected_structure = ctx.expected_structure
                existing.expected_coverage = ctx.expected_coverage
                existing.expected_detail = ctx.expected_detail
                existing.key_concepts = ctx.key_concepts
                existing.keywords = ctx.keywords
                existing.subject_domain = ctx.subject_domain
                existing.difficulty_level = ctx.difficulty_level
                existing.evaluation_criteria = ctx.evaluation_criteria
                existing.visual_elements = ctx.visual_elements
                existing.status = ctx.status
                record = existing
            else:
                record = EvaluationContext(
                    context_id=ctx.context_id,
                    student_id=ctx.student_id,
                    evaluation_id=ctx.evaluation_id,
                    blueprint_id=ctx.blueprint_id,
                    question_id=ctx.question_id,
                    question_number=ctx.question_number,
                    question_text=ctx.question_text,
                    question_intent=ctx.question_intent,
                    question_type=ctx.question_type,
                    maximum_marks=ctx.maximum_marks,
                    expected_answer_depth=ctx.expected_answer_depth,
                    student_answer=ctx.student_answer,
                    expected_answer_characteristics=ctx.expected_answer_characteristics,
                    expected_structure=ctx.expected_structure,
                    expected_coverage=ctx.expected_coverage,
                    expected_detail=ctx.expected_detail,
                    key_concepts=ctx.key_concepts,
                    keywords=ctx.keywords,
                    subject_domain=ctx.subject_domain,
                    difficulty_level=ctx.difficulty_level,
                    evaluation_criteria=ctx.evaluation_criteria,
                    visual_elements=ctx.visual_elements,
                    status=ctx.status,
                )
                self.db.add(record)

            saved_records.append(record)

        try:
            self.db.commit()
            for r in saved_records:
                self.db.refresh(r)
        except Exception:
            self.db.rollback()
            raise

        return saved_records

    def get_contexts_by_evaluation_id(self, evaluation_id: uuid.UUID) -> List[EvaluationContext]:
        """Retrieves all evaluation context records for an evaluation."""
        return (
            self.db.query(EvaluationContext)
            .filter_by(evaluation_id=evaluation_id)
            .order_by(EvaluationContext.question_number)
            .all()
        )

    def get_context_by_question_id(
        self, evaluation_id: uuid.UUID, question_id: str
    ) -> Optional[EvaluationContext]:
        """Retrieves context for a single question."""
        return (
            self.db.query(EvaluationContext)
            .filter_by(evaluation_id=evaluation_id, question_id=question_id)
            .first()
        )

    def delete_contexts_by_evaluation_id(self, evaluation_id: uuid.UUID) -> int:
        """Deletes all contexts for an evaluation."""
        count = (
            self.db.query(EvaluationContext)
            .filter_by(evaluation_id=evaluation_id)
            .delete()
        )
        self.db.commit()
        return count
