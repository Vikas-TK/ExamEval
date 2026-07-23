"""
Phase 6 – API Router for Multi-Agent Consensus Engine
"""
from __future__ import annotations

import uuid
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.phase6_consensus.service import run_phase6_consensus_service
from app.phase6_consensus.repository import ConsolidatedEvaluationRepository
from app.phase6_consensus.schemas import ConsolidatedEvaluationOut, ConsensusResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/phase6", tags=["Phase 6 – Multi-Agent Consensus Engine"])


class Phase6ConsensusRequest(BaseModel):
    evaluation_id: uuid.UUID


@router.post(
    "/consensus",
    response_model=ConsensusResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run Phase 6 Multi-Agent Consensus & Mark Assignment",
)
def run_consensus(
    body: Phase6ConsensusRequest,
    db: Session = Depends(get_db),
):
    """
    Consumes Phase 5 Accuracy, Completeness, and Depth reports, performs weighted consensus,
    assigns final marks, and synthesizes consolidated feedback.
    """
    logger.info("Executing Phase 6 Consensus Engine for evaluation_id=%s", body.evaluation_id)
    return run_phase6_consensus_service(db, body.evaluation_id)


@router.get(
    "/consensus/{evaluation_id}",
    response_model=List[ConsolidatedEvaluationOut],
    summary="Get Consolidated Evaluations for a student evaluation",
)
def get_consolidated_evaluations(
    evaluation_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Retrieves all stored Consolidated Evaluation records for an evaluation_id."""
    repo = ConsolidatedEvaluationRepository(db)
    records = repo.get_consolidated_by_evaluation(evaluation_id)
    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No Consolidated Evaluations found for evaluation_id '{evaluation_id}'. Run Phase 6 consensus first.",
        )
    return records
