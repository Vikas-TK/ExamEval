import uuid
import pytest
from app.blueprint_validator import validate_blueprint_before_mapping, BlueprintValidationReport
from app.reports_generator import generate_student_report, generate_html_report_content


def test_blueprint_validator():
    bp_dict = {
        "blueprint_id": str(uuid.uuid4()),
        "sections": [
            {
                "section_name": "Part A",
                "questions": [
                    {"question_number": "13", "marks": 2.0, "answer_key": "Reservation system"},
                    {"question_number": "14", "marks": 2.0, "answer_key": "jQuery library"},
                ]
            }
        ],
        "faculty_answer_key": [
            {"question_number": "13", "answer": "Reservation system"},
            {"question_number": "14", "answer": "jQuery library"},
        ]
    }

    report = validate_blueprint_before_mapping(bp_dict)
    assert isinstance(report, BlueprintValidationReport)
    assert report.is_valid is True
    assert report.total_questions == 2
    assert report.valid_questions == 2


def test_blueprint_validator_detects_missing_marks():
    bp_dict = {
        "blueprint_id": str(uuid.uuid4()),
        "sections": [
            {
                "section_name": "Part A",
                "questions": [
                    {"question_number": "13", "marks": 0.0},  # Invalid 0 marks
                ]
            }
        ]
    }

    report = validate_blueprint_before_mapping(bp_dict)
    assert report.is_valid is False
    assert report.invalid_questions == 1
    assert len(report.errors) > 0
