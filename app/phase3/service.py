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
from app.phase3.anchor_detector import _normalize_label, detect_anchors
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
        if not record or record.status != "Approved":
            from app.blueprint_manager import get_active_approved_blueprint
            subj_code = record.subject_code if record else "GENERAL"
            approved_bp = get_active_approved_blueprint(self._db, subj_code)
            if approved_bp:
                record = approved_bp

        if not record:
            raise ValueError(f"No approved ExamBlueprint found for blueprint_id={blueprint_id}")

        blueprint_json: dict[str, Any] = {
            "blueprint_id": str(record.blueprint_id),
            "exam_name": record.exam_name,
            "subject": record.subject,
            "subject_code": record.subject_code,
            "regulation": record.regulation,
            "semester": record.semester,
            "department": record.department,
            "duration_minutes": record.duration_minutes,
            "maximum_marks": record.maximum_marks,
            "sections": record.sections,
            "faculty_answer_key": record.faculty_answer_key or [],
            "status": record.status,
            "blueprint_type": record.blueprint_type,
        }
        return blueprint_json

    def _get_student_id(self, evaluation_id: uuid.UUID) -> str | None:
        identity: StudentIdentity | None = (
            self._db.query(StudentIdentity)
            .filter(StudentIdentity.evaluation_id == evaluation_id)
            .first()
        )
        if identity:
            return identity.register_number
        return None

    def run(self, evaluation_id: uuid.UUID, blueprint_id: uuid.UUID) -> Phase3Response:
        logger.info("Phase 3 started | evaluation_id=%s blueprint_id=%s",
                    evaluation_id, blueprint_id)

        # Step 1: Retrieve
        ocr_json = self._get_ocr_json(evaluation_id)
        blueprint_json = self._get_blueprint_json(blueprint_id)
        student_id = self._get_student_id(evaluation_id)

        # Real blueprint question numbers, normalized the same way anchors
        # are — lets the guard recognize a genuine out-of-order question
        # (e.g. 16 answered after 18 within one "answer any two" Part)
        # instead of only ever accepting strictly-increasing numbers.
        blueprint_question_numbers = {
            _normalize_label(bq.question_number)
            for bq in _extract_blueprint_questions(blueprint_json)
        }

        # Step 2: Detect Anchors
        flat_text, page_map, anchors = detect_anchors(ocr_json, blueprint_question_numbers)
        logger.info("Anchors detected: %d", len(anchors))

        # Step 3: Segment Answer Blocks
        blocks = segment_answers(flat_text, anchors, ocr_json, page_map, blueprint_question_numbers)
        logger.info("Answer blocks segmented: %d", len(blocks))

        # Step 4 & 5: Map to Blueprint
        mapping_stats: dict[str, Any] = {}
        mapped_qas: list[MappedQA] = map_answers_to_blueprint(
            blocks, blueprint_json, evaluation_id, blueprint_id, stats=mapping_stats
        )

        # Step 6: Validate
        bp_questions = _extract_blueprint_questions(blueprint_json)
        annotated_qas, report = validate_mapping(mapped_qas, bp_questions)

        # Build per-question validation lookup
        per_q_val: dict[str, tuple[str, list[str], list[str]]] = {}
        for mqa in annotated_qas:
            per_q_val[mqa.question_id] = (mqa.validation_status, [], [])

        # Step 7: Store
        # Re-mapping the same evaluation against a different blueprint (e.g.
        # a corrected re-extraction) must REPLACE the old mapping, not add
        # to it — the upsert key is (evaluation_id, question_id), and a
        # different blueprint produces different question_ids, so without
        # this the old blueprint's rows become orphaned and get returned
        # alongside the new ones by get_by_evaluation() (which only filters
        # on evaluation_id), interleaving two runs' worth of questions.
        self._repo.delete_by_evaluation_excluding_blueprint(evaluation_id, blueprint_id)
        self._repo.bulk_upsert(annotated_qas, report, per_q_val)

        # Flag for manual review on either of two independent signals:
        #
        # 1. The mapper's Pass-4 safety net had to glue orphaned content
        #    onto a neighboring question — content that WAS segmented into
        #    its own block but couldn't be matched to a question by number,
        #    content, or position.
        # 2. A genuine anchor-count shortfall against the blueprint's own
        #    question count. This catches a DIFFERENT failure shape Pass 4
        #    never sees: a question with no anchor at all doesn't produce a
        #    separate orphaned block — its content just becomes part of
        #    whatever anchor precedes it during segmentation, from the
        #    start, before Pass 4 ever runs (e.g. a missing "19." meant
        #    Q19's whole answer was already inside Q18's block, not glued
        #    on after the fact).
        #
        # A single missing anchor is common and NOT alarming on its own — a
        # student skipping exactly one question is normal, not a mapping
        # failure — so the shortfall threshold is deliberately > 1, not
        # > 0: it tolerates one genuine blank while still catching cases
        # like this one (one genuine blank + one truly-unrecovered anchor).
        real_anchor_count = sum(
            1 for a in anchors if not (a.normalized or "").upper().startswith(("PART", "SECTION"))
        )
        unique_question_ids = {bq.question_id for bq in bp_questions}
        anchor_shortfall = len(unique_question_ids) - real_anchor_count

        needs_manual_review = (
            mapping_stats.get("orphaned_fragments_reattached", 0) > 0
            or anchor_shortfall > 1
        )
        if needs_manual_review:
            eval_record = (
                self._db.query(EvaluationRecord)
                .filter(EvaluationRecord.evaluation_id == evaluation_id)
                .first()
            )
            if eval_record is not None:
                eval_record.needs_manual_review = True
                self._db.commit()
                logger.warning(
                    "Evaluation %s flagged NEEDS_MANUAL_REVIEW: %d answer fragment(s) "
                    "reattached to a neighboring question by the Pass-4 safety net, "
                    "%d anchor(s) short of the blueprint's %d expected questions.",
                    evaluation_id,
                    mapping_stats.get("orphaned_fragments_reattached", 0),
                    max(anchor_shortfall, 0),
                    len(unique_question_ids),
                )

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
            needs_manual_review=needs_manual_review,
        )
