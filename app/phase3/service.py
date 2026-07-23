"""
Phase 3 – Service Layer

Orchestrates Steps 1–7 of the Q&A Mapping Engine.
Fault-tolerant: one failing question never terminates the pipeline.
"""
from __future__ import annotations

import json
import logging
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.blueprint_models import ExamBlueprint
from app.models.evaluation import EvaluationRecord, StudentIdentity
from app.phase3.anchor_detector import detect_anchors
from app.phase3.mapper import _extract_blueprint_questions, map_answers_to_blueprint
from app.phase3.repository import QAMappingRepository
from app.phase3.schemas import MappedQA, Phase3Response, ValidationReport
from app.phase3.segmenter import segment_answers
from app.phase3.validator import validate_mapping

logger = logging.getLogger(__name__)


class Phase3Service:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = QAMappingRepository(db)

    def _get_ocr_json(self, evaluation_id: uuid.UUID) -> dict[str, Any]:
        record: EvaluationRecord | None = (
            self._db.query(EvaluationRecord)
            .filter(EvaluationRecord.evaluation_id == evaluation_id)
            .first()
        )
        if not record:
            raise ValueError(f"EvaluationRecord not found for evaluation_id={evaluation_id}")
        ocr_json = record.ocr_data  # field is ocr_data in the model
        if not ocr_json:
            raise ValueError(f"OCR result is empty for evaluation_id={evaluation_id}")
        if isinstance(ocr_json, str):
            ocr_json = json.loads(ocr_json)
        return ocr_json

    def _get_blueprint_json(self, blueprint_id: uuid.UUID) -> dict[str, Any]:
        record: ExamBlueprint | None = (
            self._db.query(ExamBlueprint)
            .filter(ExamBlueprint.blueprint_id == blueprint_id)
            .first()
        )
        if not record:
            raise ValueError(f"ExamBlueprint not found for blueprint_id={blueprint_id}")
        # Reconstruct blueprint dict from ORM fields
        blueprint_json: dict[str, Any] = {
            "exam_name": record.exam_name,
            "subject": record.subject,
            "subject_code": record.subject_code,
            "regulation": record.regulation,
            "semester": record.semester,
            "department": record.department,
            "duration_minutes": record.duration_minutes,
            "maximum_marks": record.maximum_marks,
            "sections": record.sections if isinstance(record.sections, list) else [],
        }
        return blueprint_json

    def _get_student_id(self, evaluation_id: uuid.UUID) -> str | None:
        identity: StudentIdentity | None = (
            self._db.query(StudentIdentity)
            .filter(StudentIdentity.evaluation_id == evaluation_id)
            .first()
        )
        # StudentIdentity only stores student_hash (hashed PII)
        if identity:
            return identity.student_hash[:8] + "..."
        return None

    def run(self, evaluation_id: uuid.UUID, blueprint_id: uuid.UUID) -> Phase3Response:
        logger.info("Phase 3 started | evaluation_id=%s blueprint_id=%s",
                    evaluation_id, blueprint_id)

        # Step 1: Retrieve
        ocr_json = self._get_ocr_json(evaluation_id)
        blueprint_json = self._get_blueprint_json(blueprint_id)
        student_id = self._get_student_id(evaluation_id)

        # Step 2: Detect Anchors
        flat_text, page_map, anchors = detect_anchors(ocr_json)
        logger.info("Anchors detected: %d", len(anchors))

        # Step 3: Segment Answer Blocks
        blocks = segment_answers(flat_text, anchors, ocr_json, page_map)
        logger.info("Answer blocks segmented: %d", len(blocks))

        # Step 4 & 5: Map to Blueprint
        mapped_qas: list[MappedQA] = map_answers_to_blueprint(
            blocks, blueprint_json, evaluation_id, blueprint_id
        )

        # Step 6: Validate
        bp_questions = _extract_blueprint_questions(blueprint_json)
        annotated_qas, report = validate_mapping(mapped_qas, bp_questions)

        # Build per-question validation lookup
        per_q_val: dict[str, tuple[str, list[str], list[str]]] = {}
        for mqa in annotated_qas:
            per_q_val[mqa.question_id] = (mqa.validation_status, [], [])

        # Step 7: Store
        self._repo.bulk_upsert(annotated_qas, report, per_q_val)

        return Phase3Response(
            status="SUCCESS",
            student_id=student_id,
            evaluation_id=str(evaluation_id),
            blueprint_id=str(blueprint_id),
            questions_processed=len(bp_questions),
            mapped_questions=report.mapped_count,
            unmapped_questions=report.unmapped_count,
            skipped_questions=report.skipped_count,
            validation_status=report.validation_status,
            output="Structured Question-Answer JSON stored successfully.",
            validation_report=report,
        )
