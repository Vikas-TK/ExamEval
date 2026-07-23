"""
Phase 4 – Evaluation Context Builder Service Layer
Orchestrates Phase 4 pipeline execution: validates Phase 3 Q&A JSON, builds Evaluation Context,
stores records in PostgreSQL, and generates execution summary & validation reports.
"""
from __future__ import annotations

import time
import uuid
import logging
from typing import List, Dict, Any

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.phase3.repository import QAMappingRepository
from app.blueprint_models import ExamBlueprint
from app.models import StudentIdentity
from app.phase4_context.builder import build_single_question_context
from app.phase4_context.repository import EvaluationContextRepository
from app.phase4_context.schemas import (
    EvaluationContextOut,
    EvaluationContextBuildResponse,
    ProcessingSummary,
    ValidationReport,
)

logger = logging.getLogger(__name__)


def build_evaluation_context_service(
    db: Session,
    evaluation_id: uuid.UUID,
    blueprint_id: uuid.UUID,
) -> EvaluationContextBuildResponse:
    """
    Main Phase 4 Service Entry Point.

    1. Retrieves Phase 3 Validated Structured Q&A JSON.
    2. Validates Student ID, Evaluation ID, Blueprint ID, Question IDs.
    3. Builds rich Evaluation Context for every mapped question.
    4. Persists records to PostgreSQL database table 'evaluation_contexts'.
    5. Returns structured JSON + Processing Summary + Validation Report.
    """
    start_time = time.time()

    # Step 1: Validate Student Identity & Evaluation ID
    student_record = db.query(StudentIdentity).filter_by(evaluation_id=evaluation_id).first()
    if not student_record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Evaluation ID '{evaluation_id}' not found in database.",
        )
    student_id = student_record.hashed_register_number or f"STU-{str(evaluation_id)[:8]}"

    # Step 2: Validate Exam Blueprint ID
    blueprint = db.query(ExamBlueprint).filter_by(blueprint_id=blueprint_id).first()
    if not blueprint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Blueprint ID '{blueprint_id}' not found in database.",
        )

    # Step 3: Retrieve Phase 3 Q&A Mappings
    repo_p3 = QAMappingRepository(db)
    mapped_qas = repo_p3.get_mappings_by_evaluation(evaluation_id)

    validation_report = ValidationReport(
        is_valid=True,
        student_id_valid=bool(student_id),
        evaluation_id_valid=bool(evaluation_id),
        blueprint_id_valid=bool(blueprint_id),
        question_ids_valid=len(mapped_qas) > 0,
        missing_fields=[],
        warnings=[],
    )

    if not mapped_qas:
        validation_report.is_valid = False
        validation_report.warnings.append("No Phase 3 Q&A mappings found for this evaluation_id.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Phase 3 Question-Answer mappings missing for evaluation_id '{evaluation_id}'. Run Phase 3 processing first.",
        )

    # Convert Phase 3 mapped QA records into list of dicts
    qa_dicts: List[Dict[str, Any]] = [
        {
            "question_id": str(m.question_id),
            "question_number": str(m.question_number),
            "question_text": str(m.question_text or ""),
            "student_answer": str(m.student_answer or ""),
            "question_type": str(m.question_type or "Descriptive"),
            "maximum_marks": float(m.maximum_marks or 5.0),
            "visual_elements": m.visual_elements or [],
        }
        for m in mapped_qas
    ]

    # Step 4: Build Evaluation Context per question with fault tolerance
    built_contexts: List[EvaluationContextOut] = []
    incomplete_count = 0

    for qa_dict in qa_dicts:
        context = build_single_question_context(
            mapped_qa=qa_dict,
            student_id=student_id,
            evaluation_id=evaluation_id,
            blueprint_id=blueprint_id,
        )
        if context.status == "CONTEXT_INCOMPLETE":
            incomplete_count += 1
        built_contexts.append(context)

    # Step 5: Save Contexts to PostgreSQL database
    repo_p4 = EvaluationContextRepository(db)
    repo_p4.save_evaluation_contexts(built_contexts)

    elapsed = round(time.time() - start_time, 3)

    summary = ProcessingSummary(
        total_questions=len(built_contexts),
        successfully_built=len(built_contexts) - incomplete_count,
        incomplete_questions=incomplete_count,
        status="COMPLETED" if incomplete_count == 0 else "COMPLETED_WITH_WARNINGS",
        execution_time_seconds=elapsed,
    )

    return EvaluationContextBuildResponse(
        evaluation_contexts=built_contexts,
        processing_summary=summary,
        validation_report=validation_report,
        storage_status="STORED_IN_POSTGRESQL",
    )
