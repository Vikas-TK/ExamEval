import uuid
import pytest
from app.blueprint_manager import (
    ComprehensiveBlueprintSchema,
    SectionDetail,
    QuestionDetail,
    validate_blueprint_json,
    get_active_approved_blueprint,
)
from app.blueprint_models import ExamBlueprint


def test_validate_blueprint_json_success():
    valid_json = {
        "exam_name": "Internal Test 1",
        "subject": "Data Structures",
        "subject_code": "CS8351",
        "regulation": "R2021",
        "semester": "SEM-03",
        "department": "CSE",
        "duration_minutes": 90,
        "maximum_marks": 50.0,
        "status": "Approved",
        "blueprint_type": "json_upload",
        "sections": [
            {
                "section_name": "Part A",
                "total_marks": 10.0,
                "questions": [
                    {
                        "question_number": "1",
                        "marks": 2.0,
                        "course_outcome": "CO1",
                        "blooms_taxonomy": "Remember",
                        "difficulty_level": "Easy",
                        "question_type": "Short Answer",
                        "expected_depth": "Brief definition",
                        "answer_key": "Linear data structure where elements are stored contiguously."
                    }
                ]
            }
        ]
    }

    res = validate_blueprint_json(valid_json)
    assert res.is_valid is True
    assert res.total_sections == 1
    assert res.total_questions == 1


def test_validate_blueprint_json_detects_duplicate_questions():
    dup_json = {
        "exam_name": "Internal Test 1",
        "subject": "Data Structures",
        "subject_code": "CS8351",
        "regulation": "R2021",
        "semester": "SEM-03",
        "department": "CSE",
        "duration_minutes": 90,
        "maximum_marks": 50.0,
        "sections": [
            {
                "section_name": "Part A",
                "total_marks": 10.0,
                "questions": [
                    {"question_number": "Q1", "marks": 2.0},
                    {"question_number": "Q1", "marks": 2.0},  # Duplicate
                ]
            }
        ]
    }

    res = validate_blueprint_json(dup_json)
    assert res.is_valid is False
    assert any("Duplicate" in err for err in res.errors)
