from app.blueprint_engine import extract_sections, validate_blueprint
from app.blueprint_schemas import ExamMetadata
from app.security import student_hash


def test_blueprint_parses_optional_question_marks(monkeypatch):
    ocr = {"pages": [{"transcript": "Part A: Answer any five\n1. Define X (10 marks)\n2. Explain Y (10 marks)"}]}
    sections = extract_sections(ocr)
    metadata = ExamMetadata(
        exam_name="Exam", subject="Subject", subject_code="S1", regulation="R1",
        semester="I", department="CSE", duration_minutes=180, maximum_marks=10,
    )
    validate_blueprint(metadata, sections)
    assert len(sections[0].questions) == 2


def test_student_hash_is_keyed(monkeypatch):
    monkeypatch.setenv("IDENTITY_HASH_SECRET", "test-secret")
    from app.config import get_settings
    get_settings.cache_clear()
    assert student_hash(" ABC ") == student_hash("abc")
    assert student_hash("abc") != student_hash("abd")


def test_create_blueprint_with_s3_upload(monkeypatch):
    # Mock upload functions in blueprint_service where they are imported
    monkeypatch.setattr("app.blueprint_service.upload_blueprint", lambda data, bp_id: f"s3://bucket/exam-blueprints/{bp_id}/blueprint.json")
    monkeypatch.setattr("app.blueprint_service.upload_faculty_answer_key", lambda data, bp_id, filename: f"s3://bucket/faculty-answer-keys/{bp_id}/{filename}")
    
    # Mock DB session
    from unittest.mock import MagicMock
    db = MagicMock()
    
    ocr = {"pages": [{"transcript": "Part A: Answer any five\n1. Define X (10 marks)"}]}
    metadata = ExamMetadata(
        exam_name="Exam", subject="Subject", subject_code="S1", regulation="R1",
        semester="I", department="CSE", duration_minutes=180, maximum_marks=10,
    )
    
    from app.blueprint_service import create_blueprint
    bp = create_blueprint(
        db, metadata, ocr, 
        answer_key={"1": "Answer to Q1"}, 
        answer_key_bytes=b"Q1: Answer to Q1", 
        answer_key_filename="key.txt"
    )
    
    assert bp.faculty_answer_key_s3_url is not None
    assert "faculty-answer-keys" in bp.faculty_answer_key_s3_url
    assert bp.blueprint_s3_url is not None
    assert "exam-blueprints" in bp.blueprint_s3_url
    assert db.add.called