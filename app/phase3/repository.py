"""
Phase 3 – Repository Layer

Handles all PostgreSQL persistence for QuestionAnswerMapping records.
Uses repository pattern with SQLAlchemy session.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.phase3.models import QuestionAnswerMapping
from app.phase3.schemas import MappedQA, ValidationReport

logger = logging.getLogger(__name__)


class QAMappingRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    # ─── Write ────────────────────────────────────────────────────────────────

    def upsert_mapping(
        self,
        mqa: MappedQA,
        validation_status: str,
        validation_warnings: list[str] | None,
        validation_errors: list[str] | None,
    ) -> QuestionAnswerMapping:
        """
        Insert or update a QuestionAnswerMapping row.
        Upsert key: (evaluation_id, question_id).
        """
        existing: QuestionAnswerMapping | None = (
            self._db.query(QuestionAnswerMapping)
            .filter(
                QuestionAnswerMapping.evaluation_id == mqa.evaluation_id,
                QuestionAnswerMapping.question_id == mqa.question_id,
            )
            .first()
        )

        if existing:
            existing.question_number = mqa.question_number
            existing.question_text = mqa.question_text
            existing.maximum_marks = mqa.maximum_marks
            existing.question_type = mqa.question_type
            existing.section_name = mqa.section_name
            existing.student_answer = mqa.student_answer
            existing.answer_length = mqa.answer_length
            existing.visual_elements = mqa.visual_elements or []
            existing.anchor_text = mqa.anchor_text
            existing.anchor_confidence = mqa.anchor_confidence
            existing.mapping_status = mqa.mapping_status
            existing.validation_status = validation_status
            existing.validation_warnings = validation_warnings or []
            existing.validation_errors = validation_errors or []
            existing.question_sequence = mqa.question_sequence
            record = existing
        else:
            record = QuestionAnswerMapping(
                mapping_id=mqa.mapping_id,
                evaluation_id=mqa.evaluation_id,
                blueprint_id=mqa.blueprint_id,
                question_id=mqa.question_id,
                question_number=mqa.question_number,
                question_text=mqa.question_text,
                maximum_marks=mqa.maximum_marks,
                question_type=mqa.question_type,
                section_name=mqa.section_name,
                student_answer=mqa.student_answer,
                answer_length=mqa.answer_length,
                visual_elements=mqa.visual_elements or [],
                anchor_text=mqa.anchor_text,
                anchor_confidence=mqa.anchor_confidence,
                mapping_status=mqa.mapping_status,
                validation_status=validation_status,
                validation_warnings=validation_warnings or [],
                validation_errors=validation_errors or [],
                question_sequence=mqa.question_sequence,
            )
            self._db.add(record)

        return record

    def bulk_upsert(
        self,
        mapped_qas: list[MappedQA],
        report: ValidationReport,
        per_question_validations: dict[str, tuple[str, list[str], list[str]]],
    ) -> list[QuestionAnswerMapping]:
        """
        Upsert all Q&A records in a single transaction.
        per_question_validations: question_id → (status, warnings, errors)
        """
        records: list[QuestionAnswerMapping] = []
        for mqa in mapped_qas:
            try:
                v_status, v_warns, v_errors = per_question_validations.get(
                    mqa.question_id, (mqa.mapping_status, [], [])
                )
                rec = self.upsert_mapping(mqa, v_status, v_warns, v_errors)
                records.append(rec)
            except Exception as exc:
                logger.error("Failed to upsert Q%s: %s — continuing.", mqa.question_number, exc)
                self._db.rollback()
                # Retry with minimal record
                try:
                    minimal = MappedQA(
                        mapping_id=mqa.mapping_id,
                        evaluation_id=mqa.evaluation_id,
                        blueprint_id=mqa.blueprint_id,
                        question_id=mqa.question_id,
                        question_number=mqa.question_number,
                        question_text=None,
                        maximum_marks=0.0,
                        question_type="Unknown",
                        section_name="Unknown",
                        student_answer=None,
                        answer_length=0,
                        visual_elements=[],
                        anchor_text=None,
                        anchor_confidence=0.0,
                        mapping_status="UNMAPPED",
                        question_sequence=mqa.question_sequence,
                    )
                    rec = self.upsert_mapping(minimal, "INVALID", [], [str(exc)])
                    records.append(rec)
                except Exception as inner_exc:
                    logger.error("Fatal: could not store even minimal record for Q%s: %s",
                                 mqa.question_number, inner_exc)

        self._db.commit()
        return records

    # ─── Read ─────────────────────────────────────────────────────────────────

    def get_by_evaluation(self, evaluation_id: uuid.UUID) -> list[QuestionAnswerMapping]:
        return (
            self._db.query(QuestionAnswerMapping)
            .filter(QuestionAnswerMapping.evaluation_id == evaluation_id)
            .order_by(QuestionAnswerMapping.question_sequence)
            .all()
        )

    def delete_by_evaluation(self, evaluation_id: uuid.UUID) -> int:
        count = (
            self._db.query(QuestionAnswerMapping)
            .filter(QuestionAnswerMapping.evaluation_id == evaluation_id)
            .delete()
        )
        self._db.commit()
        return count
