"""
Phase 5 – Service Layer for Multi-Agent Answer Evaluation Engine
Loads Evaluation Contexts, executes 3 AI agents in parallel, and persists reports in PostgreSQL.
"""
from __future__ import annotations

import time
import uuid
import logging
from typing import List

from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.phase4_context.repository import EvaluationContextRepository
from app.phase4_context.schemas import EvaluationContextOut
from app.phase5_agents.evaluator import run_multi_agent_evaluation
from app.phase5_agents.repository import AgentReportsRepository
from app.phase5_agents.schemas import (
    AccuracyReportOut,
    CompletenessReportOut,
    DepthReportOut,
    QuestionAgentResults,
    MultiAgentEvaluationResponse,
)

logger = logging.getLogger(__name__)


async def run_phase5_multi_agent_evaluation(
    db: Session, evaluation_id: uuid.UUID
) -> MultiAgentEvaluationResponse:
    """
    Executes Phase 5 Multi-Agent Answer Evaluation Engine.
    Loads Phase 4 Evaluation Contexts and runs Accuracy, Completeness, and Depth agents concurrently.
    """
    start_time = time.time()

    # Step 1: Load Phase 4 Evaluation Contexts from DB
    repo_ctx = EvaluationContextRepository(db)
    ctx_records = repo_ctx.get_contexts_by_evaluation_id(evaluation_id)
    if not ctx_records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No Phase 4 Evaluation Context found for evaluation_id '{evaluation_id}'. Run Phase 4 first.",
        )

    blueprint_id = ctx_records[0].blueprint_id if ctx_records else None
    repo_p5 = AgentReportsRepository(db)
    question_results: List[QuestionAgentResults] = []

    # Step 2: Iterate over questions and run 3 agents concurrently per question
    for rec in ctx_records:
        ctx_dto = EvaluationContextOut.model_validate(rec)

        acc_data, cmp_data, dph_data = await run_multi_agent_evaluation(ctx_dto)

        acc_rec, cmp_rec, dph_rec = repo_p5.save_reports(
            evaluation_id=evaluation_id,
            blueprint_id=blueprint_id,
            question_id=ctx_dto.question_id,
            question_number=ctx_dto.question_number,
            accuracy_data=acc_data,
            completeness_data=cmp_data,
            depth_data=dph_data,
        )

        question_results.append(
            QuestionAgentResults(
                question_id=ctx_dto.question_id,
                question_number=ctx_dto.question_number,
                maximum_marks=ctx_dto.maximum_marks,
                accuracy_report=AccuracyReportOut.model_validate(acc_rec),
                completeness_report=CompletenessReportOut.model_validate(cmp_rec),
                depth_report=DepthReportOut.model_validate(dph_rec),
            )
        )

    elapsed = round(time.time() - start_time, 3)

    return MultiAgentEvaluationResponse(
        evaluation_id=evaluation_id,
        blueprint_id=blueprint_id,
        total_questions=len(question_results),
        question_evaluations=question_results,
        status="COMPLETED",
        execution_time_seconds=elapsed,
    )
