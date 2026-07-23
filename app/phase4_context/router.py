"""
Phase 4 – Evaluation Context Builder API Router
REST API endpoints for building, retrieving, and managing Evaluation Contexts.
"""
from __future__ import annotations

import uuid
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.phase4_context.service import build_evaluation_context_service
from app.phase4_context.repository import EvaluationContextRepository
from app.phase4_context.schemas import EvaluationContextOut, EvaluationContextBuildResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/evaluation-context", tags=["Phase 4 – Evaluation Context Builder"])


class BuildContextRequest(BaseModel):
    evaluation_id: uuid.UUID
    blueprint_id: uuid.UUID


@router.post(
    "/build",
    response_model=EvaluationContextBuildResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Build Evaluation Context for Phase 5 AI Evaluation Agents",
)
def build_evaluation_context(
    body: BuildContextRequest,
    db: Session = Depends(get_db),
):
    """
    Transforms Phase 3 Structured Q&A JSON into rich Evaluation Contexts
    containing Intent, Expected Depth, Key Concepts, Keywords, and Evaluation Criteria.
    """
    logger.info("Building Phase 4 Evaluation Context for evaluation_id=%s, blueprint_id=%s",
                body.evaluation_id, body.blueprint_id)
    return build_evaluation_context_service(
        db=db,
        evaluation_id=body.evaluation_id,
        blueprint_id=body.blueprint_id,
    )


@router.get(
    "/{evaluation_id}",
    response_model=List[EvaluationContextOut],
    summary="Get all Evaluation Contexts for a student evaluation",
)
def get_evaluation_contexts(
    evaluation_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Retrieves all built Evaluation Context records for a given evaluation_id."""
    repo = EvaluationContextRepository(db)
    records = repo.get_contexts_by_evaluation_id(evaluation_id)
    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No Evaluation Contexts found for evaluation_id '{evaluation_id}'. Run /build endpoint first.",
        )
    return records


@router.get(
    "/{evaluation_id}/{question_id}",
    response_model=EvaluationContextOut,
    summary="Get Evaluation Context for a specific question",
)
def get_question_context(
    evaluation_id: uuid.UUID,
    question_id: str,
    db: Session = Depends(get_db),
):
    """Retrieves Evaluation Context for a single question."""
    repo = EvaluationContextRepository(db)
    record = repo.get_context_by_question_id(evaluation_id, question_id)
    if not record:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No Evaluation Context found for question_id '{question_id}' under evaluation_id '{evaluation_id}'.",
        )
    return record


@router.delete(
    "/{evaluation_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Evaluation Contexts for a student evaluation",
)
def delete_evaluation_contexts(
    evaluation_id: uuid.UUID,
    db: Session = Depends(get_db),
):
    """Deletes stored Evaluation Context records for an evaluation_id."""
    repo = EvaluationContextRepository(db)
    deleted_count = repo.delete_contexts_by_evaluation_id(evaluation_id)
    return {
        "evaluation_id": str(evaluation_id),
        "deleted_records": deleted_count,
        "message": f"Successfully deleted {deleted_count} evaluation context records.",
    }
