import io
import json
import uuid
import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont

from app.main import app
from app.models import EvaluationRecord, StudentIdentity
from app.blueprint_models import ExamBlueprint
from app.security import student_hash

def create_sample_image():
    # 1000x1200 paper sheet with realistic background and text lines for OpenCV quality gate
    img = Image.new('RGB', (1000, 1200), color=(200, 200, 200))
    d = ImageDraw.Draw(img)
    # Add dark margin line and handwritten style text blocks
    d.rectangle([50, 50, 950, 1150], outline=(50, 50, 50), width=4)
    for y in range(100, 1100, 40):
        d.line([80, y, 920, y], fill=(120, 120, 120), width=1)
    d.text((100, 80), "Question 1: Explain Database Normalization", fill=(10, 10, 10))
    d.text((100, 120), "Database normalization is the process of structuring a relational database.", fill=(10, 10, 10))
    d.text((100, 160), "1NF removes duplicate columns. 2NF removes partial key dependencies.", fill=(10, 10, 10))
    d.text((100, 200), "3NF removes transitive dependencies. BCNF addresses multi-valued attributes.", fill=(10, 10, 10))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()

def test_e2e_phase1_and_phase2_integration(db_session, monkeypatch):
    monkeypatch.setenv("IDENTITY_HASH_SECRET", "e2e-secret-key-12345")
    
    # Mock external Qwen2.5-VL API call to return valid structured OCR
    def mock_qwen_call(*args, **kwargs):
        class MockChoiceMessage:
            content = json.dumps({
                "transcript": "Question 1: Explain Database Normalization\nNormalization is the process of organizing data.",
                "structure_map": {"1": "Normalization is the process of organizing data."},
                "confidence": 0.95,
                "visual_elements": []
            })
        class MockChoice:
            message = MockChoiceMessage()
        class MockResponse:
            choices = [MockChoice()]
        return MockResponse()

    monkeypatch.setattr("app.ocr_engine.openai_client.chat.completions.create", mock_qwen_call)
    
    # Mock Storage uploads to return valid presigned references
    monkeypatch.setattr("app.storage.upload_bytes", lambda data, key, content_type="": f"https://supabase.test/storage/v1/object/public/exam-eval/{key}")

    client = TestClient(app)

    # -----------------------------------------------------------------------
    # PHASE 1 EXECUTION: Answer Sheet Ingestion & Anonymization
    # -----------------------------------------------------------------------
    img_bytes = create_sample_image()
    
    ingest_resp = client.post(
        "/evaluations",
        data={
            "regulation": "R2021",
            "semester": "SEM-04",
            "subject_id": "CS8451",
            "register_number": "312221104001"
        },
        files={"file": ("answersheet.png", img_bytes, "image/png")}
    )
    
    assert ingest_resp.status_code == 202
    eval_id = ingest_resp.json()["evaluation_id"]
    assert eval_id is not None

    # Execute background pipeline synchronously for test verification
    from app.pipeline import process_evaluation
    monkeypatch.setattr("app.pipeline.SessionLocal", lambda: db_session)
    process_evaluation(uuid.UUID(eval_id), img_bytes, "answersheet.png")

    # Verify Zero-Trust Boundary in DB
    identity_record = db_session.query(StudentIdentity).filter_by(evaluation_id=uuid.UUID(eval_id)).first()
    assert identity_record is not None
    assert identity_record.student_hash == student_hash("312221104001")
    assert not hasattr(identity_record, "register_number") or identity_record.register_number is None

    # Fetch updated evaluation status
    get_resp = client.get(f"/evaluations/{eval_id}")
    assert get_resp.status_code == 200
    eval_data = get_resp.json()
    assert eval_data["status"] in ("COMPLETED", "NEEDS_REVIEW")
    assert eval_data["quality_report"] is not None
    assert eval_data["quality_report"]["passed"] == True

    # -----------------------------------------------------------------------
    # PHASE 2 EXECUTION: Question Paper Blueprint Generation
    # -----------------------------------------------------------------------
    ocr_payload = {
        "pages": [
            {
                "transcript": (
                    "Exam Name: End Semester Examination\n"
                    "Subject: Database Management Systems\n"
                    "Subject Code: CS8451\n"
                    "Regulation: R2021\n"
                    "Semester: IV\n"
                    "Department: Computer Science and Engineering\n"
                    "Duration: 180 minutes\n"
                    "Maximum Marks: 100\n\n"
                    "Part A: Short Answer Questions\n"
                    "1. Define First Normal Form (1NF). (2 marks)\n"
                    "2. What is a Foreign Key constraint? (2 marks)\n\n"
                    "Part B: Descriptive Questions\n"
                    "3. Explain relational database normalization up to BCNF with examples. (16 marks)"
                )
            }
        ]
    }

    blueprint_resp = client.post(
        "/blueprints",
        data={
            "ocr_json": json.dumps(ocr_payload)
        }
    )

    assert blueprint_resp.status_code == 201
    bp_data = blueprint_resp.json()
    bp_id = bp_data["blueprint_id"]
    assert bp_id is not None

    # Fetch full blueprint
    bp_detail_resp = client.get(f"/blueprints/{bp_id}")
    assert bp_detail_resp.status_code == 200
    bp_detail = bp_detail_resp.json()
    assert bp_detail["metadata"]["subject_code"] == "CS8451"
    assert len(bp_detail["sections"]) >= 1

    # -----------------------------------------------------------------------
    # FINAL INTEGRATION VERIFICATION: Phase 1 Script + Phase 2 Blueprint
    # -----------------------------------------------------------------------
    assert eval_data["subject_id"] == bp_detail["metadata"]["subject_code"]
    assert eval_data["s3_urls"]["raw_script"] is not None
    assert bp_detail["blueprint_url"] is not None
