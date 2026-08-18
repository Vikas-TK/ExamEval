from __future__ import annotations

import uuid
import json
from typing import Any

from sqlalchemy.orm import Session

from app.blueprint_engine import attach_answer_key, extract_sections, validate_blueprint
from app.blueprint_models import ExamBlueprint
from app.blueprint_schemas import ExamMetadata
from app.blueprint_templates import apply_internal_normal_marks
from app.storage import upload_blueprint, upload_faculty_answer_key


def create_blueprint(
    db: Session,
    metadata: ExamMetadata,
    ocr: dict[str, Any],
    answer_key: dict[str, str] | None = None,
    answer_key_bytes: bytes | None = None,
    answer_key_filename: str | None = None,
) -> ExamBlueprint:
    sections = extract_sections(ocr)
    if (metadata.exam_type or "").strip().upper() == "INTERNAL_NORMAL":
        sections = apply_internal_normal_marks(sections)
    if answer_key:
        sections = attach_answer_key(sections, answer_key)
    validate_blueprint(metadata, sections)

    existing = db.query(ExamBlueprint).filter_by(
        exam_name=metadata.exam_name,
        subject_code=metadata.subject_code,
        regulation=metadata.regulation,
        semester=metadata.semester,
    ).first()

    is_update = existing is not None and isinstance(existing, ExamBlueprint)
    blueprint_id = existing.blueprint_id if is_update else uuid.uuid4()

    faculty_s3_url = None
    if answer_key_bytes and answer_key_filename:
        faculty_s3_url = upload_faculty_answer_key(
            answer_key_bytes, str(blueprint_id), answer_key_filename
        )

    blueprint_json = json.dumps({
        "blueprint_id": str(blueprint_id),
        "metadata": metadata.model_dump(),
        "sections": [section.model_dump() for section in sections],
    }).encode("utf-8")
    s3_url = upload_blueprint(blueprint_json, str(blueprint_id))

    if is_update:
        for key, value in metadata.model_dump().items():
            setattr(existing, key, value)
        existing.sections = [section.model_dump() for section in sections]
        existing.source_ocr = ocr
        if answer_key:
            existing.faculty_answer_key = [{"question_number": key, "answer": value} for key, value in answer_key.items()]
        if faculty_s3_url:
            existing.faculty_answer_key_s3_url = faculty_s3_url
        existing.blueprint_s3_url = s3_url
        blueprint = existing
    else:
        blueprint = ExamBlueprint(
            blueprint_id=blueprint_id,
            **metadata.model_dump(),
            sections=[section.model_dump() for section in sections],
            source_ocr=ocr,
            faculty_answer_key=(
                [{"question_number": key, "answer": value} for key, value in answer_key.items()]
                if answer_key else None
            ),
            faculty_answer_key_s3_url=faculty_s3_url,
            blueprint_s3_url=s3_url,
        )
        db.add(blueprint)

    try:
        db.commit()
        db.refresh(blueprint)
    except Exception:
        db.rollback()
        raise
    return blueprint