"""
Phase 4 – Repository Layer
Handles PostgreSQL persistence for AnswerEvaluation records.
"""
from __future__ import annotations

import logging
import uuid

from sqlalchemy.orm import Session

from app.phase4.models import AnswerEvaluation

logger = logging.getLogger(__name__)


class EvaluationResultRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def upsert(self, record: AnswerEvaluation) -> AnswerEvaluation:
        existing = (
            self._db.query(AnswerEvaluation)
            .filter(
                AnswerEvaluation.evaluation_id == record.evaluation_id,
                AnswerEvaluation.question_id == record.question_id,
            )
            .first()
        )
        if existing:
            existing.scored_marks = record.scored_marks
            existing.ai_feedback = record.ai_feedback
            existing.ai_confidence = record.ai_confidence
            existing.evaluation_status = record.evaluation_status
            existing.answer_key = record.answer_key
            existing.student_answer = record.student_answer
            return existing
        else:
            self._db.add(record)
            return record

    def bulk_upsert(self, records: list[AnswerEvaluation]) -> None:
        for rec in records:
            try:
                self.upsert(rec)
            except Exception as exc:
                logger.error("Failed to upsert eval result for Q%s: %s", rec.question_number, exc)
        self._db.commit()

    def get_by_evaluation(self, evaluation_id: uuid.UUID) -> list[AnswerEvaluation]:
        return (
            self._db.query(AnswerEvaluation)
            .filter(AnswerEvaluation.evaluation_id == evaluation_id)
            .order_by(AnswerEvaluation.question_sequence)
            .all()
        )

    def get_by_blueprint(self, blueprint_id: uuid.UUID) -> list[AnswerEvaluation]:
        """All scored answers for all students for a given blueprint (for matrix)."""
        return (
            self._db.query(AnswerEvaluation)
            .filter(AnswerEvaluation.blueprint_id == blueprint_id)
            .order_by(AnswerEvaluation.evaluation_id, AnswerEvaluation.question_sequence)
            .all()
        )

    def delete_by_evaluation(self, evaluation_id: uuid.UUID) -> int:
        count = (
            self._db.query(AnswerEvaluation)
            .filter(AnswerEvaluation.evaluation_id == evaluation_id)
            .delete()
        )
        self._db.commit()
        return count

    def delete_by_evaluation_excluding_blueprint(
        self, evaluation_id: uuid.UUID, blueprint_id: uuid.UUID
    ) -> int:
        """
        Removes scored-answer rows left over from a PREVIOUS blueprint used
        for this evaluation. Same reasoning as the Phase 3 mapping repo:
        the upsert key is (evaluation_id, question_id), so re-scoring
        against a different blueprint (different question_ids) leaves the
        old blueprint's rows orphaned instead of replacing them, and
        get_by_evaluation() — filtering on evaluation_id only — would
        return both runs mixed together.
        """
        count = (
            self._db.query(AnswerEvaluation)
            .filter(
                AnswerEvaluation.evaluation_id == evaluation_id,
                AnswerEvaluation.blueprint_id != blueprint_id,
            )
            .delete()
        )
        self._db.commit()
        return count
