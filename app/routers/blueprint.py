from __future__ import annotations

import json
import uuid

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.blueprint_engine import extract_metadata, parse_answer_key
from app.blueprint_schemas import BlueprintCreateResponse, BlueprintOut, ExamMetadata
from app.blueprint_service import create_blueprint
from app.database import get_db
from app.blueprint_models import ExamBlueprint
from app.security import require_api_key
from app.storage import presigned_url

router = APIRouter(prefix="/blueprints", tags=["blueprints"])


@router.post("", response_model=BlueprintCreateResponse, status_code=201)
async def create_exam_blueprint(
    metadata: str | None = Form(None, description="Optional JSON object matching ExamMetadata"),
    ocr_json: str = Form(..., description="Question paper OCR JSON"),
    answer_key: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    _auth: None = Depends(require_api_key),
):
    try:
        parsed_ocr = json.loads(ocr_json)
        if not isinstance(parsed_ocr, dict):
            raise ValueError("ocr_json must be a JSON object")
        parsed_metadata = (
            ExamMetadata.model_validate(json.loads(metadata))
            if metadata else extract_metadata(parsed_ocr)
        )
        answers = None
        answer_key_bytes = None
        answer_key_filename = None
        if answer_key is not None:
            if not answer_key.filename:
                raise ValueError("Answer key filename is required")
            answer_key_filename = answer_key.filename
            answer_key_bytes = await answer_key.read()
            answers = parse_answer_key(answer_key_bytes, answer_key_filename)
        blueprint = create_blueprint(
            db, parsed_metadata, parsed_ocr, answers, answer_key_bytes, answer_key_filename
        )
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except IntegrityError as exc:
        raise HTTPException(409, "An identical exam blueprint already exists") from exc
    return _to_create_response(blueprint)


@router.get("/{blueprint_id}", response_model=BlueprintOut)
def get_exam_blueprint(
    blueprint_id: uuid.UUID,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_api_key),
):
    blueprint = db.query(ExamBlueprint).filter_by(blueprint_id=blueprint_id).first()
    if blueprint is None:
        raise HTTPException(404, "blueprint_id not found")
    return _to_output(blueprint)


def _to_create_response(blueprint: ExamBlueprint) -> BlueprintCreateResponse:
    metadata = ExamMetadata.model_validate({key: getattr(blueprint, key) for key in ExamMetadata.model_fields})
    return BlueprintCreateResponse(
        blueprint_id=blueprint.blueprint_id, metadata=metadata,
        sections=blueprint.sections,
        faculty_answer_key_mapped=blueprint.faculty_answer_key is not None,
    )


def _to_output(blueprint: ExamBlueprint) -> BlueprintOut:
    return BlueprintOut(
        **_to_create_response(blueprint).model_dump(), source_ocr=blueprint.source_ocr,
        faculty_answer_key=blueprint.faculty_answer_key,
        blueprint_url=(
            presigned_url(blueprint.blueprint_s3_url.split("/", 3)[-1])
            if blueprint.blueprint_s3_url else None
        ),
        faculty_answer_key_s3_url=(
            presigned_url(blueprint.faculty_answer_key_s3_url.split("/", 3)[-1])
            if blueprint.faculty_answer_key_s3_url else None
        ),
    )