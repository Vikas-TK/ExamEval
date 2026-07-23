"""
Phase 3 – FastAPI Router

Endpoints:
  POST /api/mapping/process      – Trigger Q&A mapping pipeline
  GET  /api/mapping/{evaluation_id}  – Retrieve stored Q&A records
  DELETE /api/mapping/{evaluation_id} – Clear mapping for re-processing
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.phase3.repository import QAMappingRepository
from app.phase3.schemas import (
    MappedQAOut,
    Phase3Response,
    Phase3TriggerRequest,
)
from app.phase3.service import Phase3Service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mapping", tags=["Phase3 – Q&A Mapping"])


@router.post(
    "/process",
    response_model=Phase3Response,
    status_code=status.HTTP_200_OK,
    summary="Trigger Phase 3 Q&A Mapping",
    description=(
        "Runs the full Phase 3 pipeline: detect anchors, segment answers, "
        "map to blueprint, validate, and store to PostgreSQL."
    ),
)
def run_mapping(
    payload: Phase3TriggerRequest,
    db: Session = Depends(get_db),
) -> Phase3Response:
    try:
        service = Phase3Service(db)
        result = service.run(
            evaluation_id=payload.evaluation_id,
            blueprint_id=payload.blueprint_id,
        )
        return result
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Phase 3 pipeline error: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Phase 3 failed: {exc}",
        ) from exc


@router.get(
    "/{evaluation_id}",
    response_model=list[MappedQAOut],
    summary="Get Q&A mapping records for an evaluation",
)
def get_mapping(
    evaluation_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> list[MappedQAOut]:
    repo = QAMappingRepository(db)
    records = repo.get_by_evaluation(evaluation_id)
    if not records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No Q&A mapping found for evaluation_id={evaluation_id}",
        )
    return [MappedQAOut.model_validate(r) for r in records]


@router.delete(
    "/{evaluation_id}",
    summary="Delete Q&A mapping records for an evaluation",
)
def delete_mapping(
    evaluation_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> dict:
    repo = QAMappingRepository(db)
    deleted = repo.delete_by_evaluation(evaluation_id)
    return {"deleted": deleted, "evaluation_id": str(evaluation_id)}
