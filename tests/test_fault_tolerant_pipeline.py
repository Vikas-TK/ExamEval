import uuid
import io
from PIL import Image
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import EvaluationRecord, EvaluationStatus, StudentIdentity
from app.pipeline import process_evaluation
from app.config import get_settings

settings = get_settings()

def create_dummy_image_bytes():
    img = Image.new("RGB", (1000, 1000), color=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

def test_ocr_failure_routes_to_needs_review_not_failed():
    db: Session = SessionLocal()
    evaluation_id = uuid.uuid4()
    
    identity = StudentIdentity(
        evaluation_id=evaluation_id,
        student_hash="test-student-hash",
        regulation="R20",
        semester="5",
        subject_id="CS101",
    )
    record = EvaluationRecord(
        evaluation_id=evaluation_id,
        subject_id="CS101",
        status=EvaluationStatus.PROCESSING,
    )
    db.add(identity)
    db.commit()
    db.add(record)
    db.commit()
    
    raw_bytes = create_dummy_image_bytes()
    process_evaluation(evaluation_id, raw_bytes, "test_sheet.png")
    
    db.expire_all()
    updated = db.query(EvaluationRecord).filter_by(evaluation_id=evaluation_id).first()
    
    # Assertions per requirements:
    # 1. OCR failure must NEVER produce FAILED status
    assert updated.status != EvaluationStatus.FAILED
    # 2. Document routes to NEEDS_REVIEW
    assert updated.status == EvaluationStatus.NEEDS_REVIEW
    assert updated.needs_manual_review is True
    # 3. OCR confidence is low (<= 0.1)
    assert updated.overall_confidence <= 0.1
    # 4. Fallback OCR is stored in database
    assert updated.ocr_data is not None
    pages = updated.ocr_data.get("pages", [])
    assert len(pages) == 1
    assert pages[0]["transcript"] == ""
    assert pages[0]["confidence"] <= 0.1
