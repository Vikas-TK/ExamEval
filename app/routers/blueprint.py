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
    ocr_json: str | None = Form(None, description="Question paper OCR JSON"),
    question_paper: UploadFile | None = File(None, description="Question paper PDF/Image/JSON file"),
    answer_key: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    _auth: None = Depends(require_api_key),
):
    try:
        parsed_ocr = None
        if question_paper is not None and question_paper.filename:
            paper_bytes = await question_paper.read()
            filename_lower = question_paper.filename.lower()
            if filename_lower.endswith(".json"):
                try:
                    parsed_ocr = json.loads(paper_bytes.decode("utf-8"))
                except Exception:
                    pass

            if parsed_ocr is None and filename_lower.endswith(".pdf"):
                try:
                    import io
                    from pypdf import PdfReader
                    pdf_reader = PdfReader(io.BytesIO(paper_bytes))
                    pdf_pages = []
                    for idx, page in enumerate(pdf_reader.pages, start=1):
                        txt = page.extract_text() or ""
                        if txt.strip():
                            pdf_pages.append({"page_number": idx, "transcript": txt})
                    if pdf_pages:
                        parsed_ocr = {"pages": pdf_pages}
                except Exception as pdf_exc:
                    logger.warning("pypdf extraction skipped: %s", pdf_exc)

            if parsed_ocr is None:
                from app.pipeline import _pages_from_upload
                from app.ocr_engine import extract_page
                try:
                    pages_raw = _pages_from_upload(paper_bytes, question_paper.filename)
                    extracted_pages = []
                    for idx, page_bytes in enumerate(pages_raw, start=1):
                        ocr_page = extract_page(page_bytes, page_number=idx)
                        extracted_pages.append(ocr_page.model_dump())
                    parsed_ocr = {"pages": extracted_pages}
                except Exception as exc:
                    parsed_ocr = {"pages": [{"page_number": 1, "transcript": paper_bytes.decode("utf-8", errors="ignore")}]}

        if parsed_ocr is None and ocr_json:
            try:
                parsed_ocr = json.loads(ocr_json)
            except Exception:
                parsed_ocr = {"pages": [{"page_number": 1, "transcript": ocr_json}]}

        if not parsed_ocr or not isinstance(parsed_ocr, dict):
            parsed_ocr = {"pages": [{"page_number": 1, "transcript": "Question Paper Document"}]}

        if metadata:
            parsed_metadata = ExamMetadata.model_validate(json.loads(metadata))
        else:
            try:
                parsed_metadata = extract_metadata(parsed_ocr)
            except Exception:
                parsed_metadata = ExamMetadata(
                    exam_name="End Semester Examination",
                    subject="General Examination",
                    subject_code="GENERAL",
                    regulation="R2021",
                    semester="SEM-01",
                    department="General",
                    duration_minutes=180,
                    maximum_marks=100.0,
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


@router.get("", response_model=list[BlueprintOut])
def list_exam_blueprints(
    db: Session = Depends(get_db),
    _auth: None = Depends(require_api_key),
):
    blueprints = db.query(ExamBlueprint).order_by(ExamBlueprint.created_at.desc()).all()
    return [_to_output(b) for b in blueprints]


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


@router.delete("/{blueprint_id}", status_code=204)
def delete_exam_blueprint(
    blueprint_id: uuid.UUID,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_api_key),
):
    blueprint = db.query(ExamBlueprint).filter_by(blueprint_id=blueprint_id).first()
    if blueprint is None:
        raise HTTPException(404, "blueprint_id not found")
    db.delete(blueprint)
    try:
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(500, f"Could not delete blueprint: {exc}") from exc
    return None


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