"""
Phase 6 – Multi-Agent Consensus Engine Service Layer
Consumes Phase 5 reports without re-evaluating answers, calculates weighted final marks,
evaluates agent agreement, consolidates feedback, and persists final marks in PostgreSQL.
"""
from __future__ import annotations

import time
import uuid
import logging
from typing import List, Dict

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.models import StudentIdentity
from app.phase4_context.repository import EvaluationContextRepository
from app.phase5_agents.repository import AgentReportsRepository
from app.phase6_consensus.agreement import calculate_agreement_and_confidence
from app.phase6_consensus.rules import calculate_weighted_marks_and_status
from app.phase6_consensus.feedback import consolidate_agent_feedback
from app.phase6_consensus.models import ConsolidatedEvaluation
from app.phase6_consensus.repository import ConsolidatedEvaluationRepository
from app.phase6_consensus.schemas import (
    ConsolidatedEvaluationOut,
    ConsensusResponse,
)

logger = logging.getLogger(__name__)


def run_phase6_consensus_service(
    db: Session, evaluation_id: uuid.UUID
) -> ConsensusResponse:
    """
    Main Phase 6 Consensus Service Entry Point.

    1. Loads Phase 5 Accuracy, Completeness, and Depth reports from DB.
    2. Performs Agreement Analysis (High, Medium, Low Agreement).
    3. Calculates Weighted Final Marks (Accuracy 50%, Completeness 30%, Depth 20%).
    4. Synthesizes Consolidated Feedback (strengths, weaknesses, missing concepts).
    5. Saves final consolidated records in PostgreSQL table 'consolidated_evaluations'.
    6. Returns complete ConsensusResponse.
    """
    start_time = time.time()

    # Step 1: Validate Student Record
    student_record = db.query(StudentIdentity).filter_by(evaluation_id=evaluation_id).first()
    student_id = student_record.register_number if student_record else f"STU-{str(evaluation_id)[:8]}"

    # Step 2: Load Phase 4 Contexts for Question Metadata & Maximum Marks
    repo_ctx = EvaluationContextRepository(db)
    contexts = repo_ctx.get_contexts_by_evaluation_id(evaluation_id)
    if not contexts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Phase 4 Evaluation Contexts missing for evaluation_id '{evaluation_id}'. Run Phase 4 first.",
        )

    # Step 3: Load Phase 5 Reports
    repo_p5 = AgentReportsRepository(db)
    acc_reports, cmp_reports, dph_reports = repo_p5.get_reports_by_evaluation(evaluation_id)

    if not acc_reports and not cmp_reports and not dph_reports:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No Phase 5 Agent Reports found for evaluation_id '{evaluation_id}'. Run Phase 5 first.",
        )

    # Maps per question_id
    acc_map = {r.question_id: r for r in acc_reports}
    cmp_map = {r.question_id: r for r in cmp_reports}
    dph_map = {r.question_id: r for r in dph_reports}

    blueprint_id = contexts[0].blueprint_id if contexts else None
    consolidated_records: List[ConsolidatedEvaluation] = []

    # Step 4: Process Consensus per question
    for ctx in contexts:
        q_id = ctx.question_id
        q_num = ctx.question_number
        max_m = float(ctx.maximum_marks or 5.0)

        acc_r = acc_map.get(q_id)
        cmp_r = cmp_map.get(q_id)
        dph_r = dph_map.get(q_id)

        acc_score = acc_r.score if acc_r else 0.0
        acc_status = acc_r.status if acc_r else "FAILED"
        acc_pct = acc_r.percentage if acc_r else 0.0
        acc_conf = acc_r.confidence if acc_r else 0.0

        cmp_score = cmp_r.score if cmp_r else 0.0
        cmp_status = cmp_r.status if cmp_r else "FAILED"
        cmp_pct = cmp_r.percentage if cmp_r else 0.0
        cmp_conf = cmp_r.confidence if cmp_r else 0.0

        dph_score = dph_r.score if dph_r else 0.0
        dph_status = dph_r.status if dph_r else "FAILED"
        dph_pct = dph_r.percentage if dph_r else 0.0
        dph_conf = dph_r.confidence if dph_r else 0.0

        # Active percentages & confidences for Agreement Analysis
        pcts: list[float] = []
        confs: list[float] = []
        if acc_status == "COMPLETED":
            pcts.append(acc_pct)
            confs.append(acc_conf)
        if cmp_status == "COMPLETED":
            pcts.append(cmp_pct)
            confs.append(cmp_conf)
        if dph_status == "COMPLETED":
            pcts.append(dph_pct)
            confs.append(dph_conf)

        agreement_lbl, eval_conf = calculate_agreement_and_confidence(pcts, confs)

        weighted_s, final_m, pct, eval_stat = calculate_weighted_marks_and_status(
            accuracy_score=acc_score,
            accuracy_status=acc_status,
            completeness_score=cmp_score,
            completeness_status=cmp_status,
            depth_score=dph_score,
            depth_status=dph_status,
            maximum_marks=max_m,
        )

        # Consolidate Feedback Lists
        acc_dict = {"correct_concepts": acc_r.correct_concepts, "technical_errors": acc_r.technical_errors, "remarks": acc_r.remarks} if acc_r else {}
        cmp_dict = {"covered_points": cmp_r.covered_points, "missing_points": cmp_r.missing_points, "missing_concepts": cmp_r.missing_concepts, "missing_keywords": cmp_r.missing_keywords, "remarks": cmp_r.remarks} if cmp_r else {}
        dph_dict = {"strong_sections": dph_r.strong_sections, "weak_sections": dph_r.weak_sections, "remarks": dph_r.remarks} if dph_r else {}

        strengths, weaknesses, missing_c, suggestions, final_rem = consolidate_agent_feedback(
            accuracy_report=acc_dict,
            completeness_report=cmp_dict,
            depth_report=dph_dict,
        )

        record = ConsolidatedEvaluation(
            consolidated_id=uuid.uuid4(),
            student_id=student_id,
            evaluation_id=evaluation_id,
            blueprint_id=blueprint_id,
            question_id=q_id,
            question_number=q_num,
            maximum_marks=max_m,
            accuracy_score=acc_score,
            completeness_score=cmp_score,
            depth_score=dph_score,
            weighted_score=weighted_s,
            final_marks=final_m,
            percentage=pct,
            agreement_level=agreement_lbl,
            evaluation_confidence=eval_conf,
            evaluation_status=eval_stat,
            strengths=strengths,
            weaknesses=weaknesses,
            missing_concepts=missing_c,
            improvement_suggestions=suggestions,
            final_remarks=final_rem,
        )
        consolidated_records.append(record)

    # Save to PostgreSQL DB
    repo_p6 = ConsolidatedEvaluationRepository(db)
    repo_p6.save_consolidated_evaluations(consolidated_records)

    elapsed = round(time.time() - start_time, 3)
    total_max = sum(r.maximum_marks for r in consolidated_records)
    total_scored = sum(r.final_marks for r in consolidated_records)
    overall_pct = round((total_scored / total_max * 100.0), 2) if total_max > 0 else 0.0

    if overall_pct >= 90.0:
        overall_stat = "Excellent"
    elif overall_pct >= 80.0:
        overall_stat = "Very Good"
    elif overall_pct >= 70.0:
        overall_stat = "Good"
    elif overall_pct >= 50.0:
        overall_stat = "Average"
    elif overall_pct >= 35.0:
        overall_stat = "Needs Improvement"
    else:
        overall_stat = "Fail"

    return ConsensusResponse(
        evaluation_id=evaluation_id,
        blueprint_id=blueprint_id,
        total_questions=len(consolidated_records),
        total_max_marks=round(total_max, 2),
        total_scored_marks=round(total_scored, 2),
        overall_percentage=overall_pct,
        overall_status=overall_stat,
        consolidated_evaluations=[ConsolidatedEvaluationOut.model_validate(r) for r in consolidated_records],
        status="COMPLETED",
        execution_time_seconds=elapsed,
    )
