"""
Phase 4 – FastAPI Router

Endpoints:
  POST /api/evaluate/run                  – Trigger Phase 4 AI scoring
  GET  /api/evaluate/{evaluation_id}      – Get scored answers for one student
  GET  /api/evaluate/matrix/{blueprint_id} – Faculty marks matrix (all students)
  GET  /api/evaluate/matrix/{blueprint_id}/download  – CSV download
  GET  /api/evaluate/transcript/{evaluation_id}/txt  – Transcript TXT
  GET  /api/evaluate/transcript/{evaluation_id}/pdf  – Transcript PDF
  DELETE /api/evaluate/{evaluation_id}    – Re-score: clear existing results
"""
from __future__ import annotations

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.phase4.repository import EvaluationResultRepository
from app.phase4.schemas import (
    MarksMatrixResponse, Phase4Response, Phase4TriggerRequest, ScoredAnswerOut,
)
from app.phase4.service import Phase4Service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/evaluate", tags=["Phase4 – AI Evaluation"])


@router.post(
    "/run",
    response_model=Phase4Response,
    summary="Trigger Phase 4 AI Scoring",
    description="Scores all Q&A mapping records for an evaluation using Qwen2.5-7B. Requires Phase 3 to have run first.",
)
def run_evaluation(
    payload: Phase4TriggerRequest,
    db: Session = Depends(get_db),
) -> Phase4Response:
    try:
        svc = Phase4Service(db)
        return svc.run(payload.evaluation_id, payload.blueprint_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Phase 4 error: %s", exc)
        raise HTTPException(status_code=500, detail=f"Phase 4 failed: {exc}") from exc


@router.get(
    "/matrix/{blueprint_id}",
    response_model=MarksMatrixResponse,
    summary="Faculty Marks Matrix",
    description="Returns marks for all students across all questions for a given blueprint.",
)
def get_matrix(
    blueprint_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> MarksMatrixResponse:
    try:
        svc = Phase4Service(db)
        return svc.build_matrix(blueprint_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Matrix build error: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/matrix/{blueprint_id}/download",
    summary="Download Marks Matrix as CSV",
)
def download_matrix_csv(
    blueprint_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Response:
    try:
        svc = Phase4Service(db)
        csv_bytes = svc.export_matrix_csv(blueprint_id)
        return Response(
            content=csv_bytes,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=marks_matrix_{blueprint_id}.csv"},
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/{evaluation_id}",
    response_model=list[ScoredAnswerOut],
    summary="Get scored answers for one student evaluation",
)
def get_evaluation_results(
    evaluation_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> list[ScoredAnswerOut]:
    repo = EvaluationResultRepository(db)
    records = repo.get_by_evaluation(evaluation_id)
    if not records:
        raise HTTPException(
            status_code=404,
            detail=f"No evaluation results found for evaluation_id={evaluation_id}. Run Phase 4 first.",
        )
    return [ScoredAnswerOut.model_validate(r) for r in records]


@router.get(
    "/transcript/{evaluation_id}/txt",
    summary="Download student transcript as plain text",
)
def download_transcript_txt(
    evaluation_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Response:
    try:
        svc = Phase4Service(db)
        content = svc.build_transcript_txt(evaluation_id)
        return Response(
            content=content,
            media_type="text/plain; charset=utf-8",
            headers={"Content-Disposition": f"attachment; filename=transcript_{evaluation_id}.txt"},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get(
    "/transcript/{evaluation_id}/pdf",
    summary="Download student transcript as PDF",
)
def download_transcript_pdf(
    evaluation_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Response:
    try:
        svc = Phase4Service(db)
        content = svc.build_transcript_pdf(evaluation_id)
        media_type = "application/pdf" if content[:4] == b"%PDF" else "text/plain; charset=utf-8"
        ext = "pdf" if media_type == "application/pdf" else "txt"
        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename=transcript_{evaluation_id}.{ext}"},
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.delete(
    "/{evaluation_id}",
    summary="Clear evaluation results for re-scoring",
)
def delete_evaluation_results(
    evaluation_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> dict:
    repo = EvaluationResultRepository(db)
    deleted = repo.delete_by_evaluation(evaluation_id)
    return {"deleted": deleted, "evaluation_id": str(evaluation_id)}
