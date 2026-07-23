"""
Phase 6 – Database Repository for Consolidated Evaluations
Encapsulates all PostgreSQL operations for consolidated_evaluations table.
"""
from __future__ import annotations

import uuid
import logging
from typing import List, Optional
from sqlalchemy.orm import Session

from app.phase6_consensus.models import ConsolidatedEvaluation

logger = logging.getLogger(__name__)


class ConsolidatedEvaluationRepository:
    def __init__(self, db: Session):
        self.db = db

    def save_consolidated_evaluations(
        self, records: List[ConsolidatedEvaluation]
    ) -> List[ConsolidatedEvaluation]:
        """Saves or updates consolidated evaluation records."""
        if not records:
            return []

        for rec in records:
            existing = self.db.query(ConsolidatedEvaluation).filter_by(
                evaluation_id=rec.evaluation_id,
                question_id=rec.question_id,
            ).first()

            if existing:
                existing.student_id = rec.student_id
                existing.blueprint_id = rec.blueprint_id
                existing.question_number = rec.question_number
                existing.maximum_marks = rec.maximum_marks
                existing.accuracy_score = rec.accuracy_score
                existing.completeness_score = rec.completeness_score
                existing.depth_score = rec.depth_score
                existing.weighted_score = rec.weighted_score
                existing.final_marks = rec.final_marks
                existing.percentage = rec.percentage
                existing.agreement_level = rec.agreement_level
                existing.evaluation_confidence = rec.evaluation_confidence
                existing.evaluation_status = rec.evaluation_status
                existing.strengths = rec.strengths
                existing.weaknesses = rec.weaknesses
                existing.missing_concepts = rec.missing_concepts
                existing.improvement_suggestions = rec.improvement_suggestions
                existing.final_remarks = rec.final_remarks
            else:
                self.db.add(rec)

        try:
            self.db.commit()
            for r in records:
                self.db.refresh(r)
        except Exception:
            self.db.rollback()
            raise

        return records

    def get_consolidated_by_evaluation(
        self, evaluation_id: uuid.UUID
    ) -> List[ConsolidatedEvaluation]:
        """Retrieves all consolidated evaluations for an evaluation_id."""
        return (
            self.db.query(ConsolidatedEvaluation)
            .filter_by(evaluation_id=evaluation_id)
            .order_by(ConsolidatedEvaluation.question_number)
            .all()
        )

    def get_consolidated_by_question(
        self, evaluation_id: uuid.UUID, question_id: str
    ) -> Optional[ConsolidatedEvaluation]:
        """Retrieves consolidated evaluation for a single question."""
        return (
            self.db.query(ConsolidatedEvaluation)
            .filter_by(evaluation_id=evaluation_id, question_id=question_id)
            .first()
        )
