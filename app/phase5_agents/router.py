"""
Phase 5 – API Router for Multi-Agent Answer Evaluation Engine
"""
from __future__ import annotations

import uuid
import logging
from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.phase5_agents.service import run_phase5_multi_agent_evaluation
from app.phase5_agents.schemas import MultiAgentEvaluationResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/phase5", tags=["Phase 5 – Multi-Agent Answer Evaluation Engine"])


class Phase5EvaluateRequest(BaseModel):
    evaluation_id: uuid.UUID


@router.post(
    "/evaluate",
    response_model=MultiAgentEvaluationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run Phase 5 Parallel Multi-Agent Answer Evaluation",
)
async def evaluate_multi_agent(
    body: Phase5EvaluateRequest,
    db: Session = Depends(get_db),
):
    """
    Executes Accuracy, Completeness, and Depth specialized AI evaluation agents concurrently
    for every mapped question in an evaluation.
    """
    logger.info("Executing Phase 5 Multi-Agent Evaluation for evaluation_id=%s", body.evaluation_id)
    return await run_phase5_multi_agent_evaluation(db, body.evaluation_id)
