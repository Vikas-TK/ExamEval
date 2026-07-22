from __future__ import annotations

import uuid
import json
from typing import Any

from sqlalchemy.orm import Session

from app.blueprint_engine import attach_answer_key, extract_sections, validate_blueprint
from app.blueprint_models import ExamBlueprint
from app.blueprint_schemas import ExamMetadata
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
    if answer_key:
        sections = attach_answer_key(sections, answer_key)
    validate_blueprint(metadata, sections)
    
    blueprint_id = uuid.uuid4()
    
    faculty_s3_url = None
    if answer_key_bytes and answer_key_filename:
        faculty_s3_url = upload_faculty_answer_key(
            answer_key_bytes, str(blueprint_id), answer_key_filename
        )

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
    )
    blueprint_json = json.dumps({
        "blueprint_id": str(blueprint.blueprint_id),
        "metadata": metadata.model_dump(),
        "sections": [section.model_dump() for section in sections],
    }).encode("utf-8")
    blueprint.blueprint_s3_url = upload_blueprint(blueprint_json, str(blueprint.blueprint_id))
    db.add(blueprint)
    try:
        db.commit()
        db.refresh(blueprint)
    except Exception:
        db.rollback()
        raise
    return blueprint