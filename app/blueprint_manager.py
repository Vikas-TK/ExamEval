"""
Manual Blueprint & Answer Key Manager Module
Handles Manual Visual Builder, JSON Upload Validation, Template Management,
Approval State Workflow (Draft/Under Review/Approved/Archived), and Priority Blueprint Resolution.
"""
from __future__ import annotations

import json
import uuid
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.orm import Session

from app.blueprint_models import ExamBlueprint, AuditLog

logger = logging.getLogger(__name__)


# --- Question & Section Pydantic Models ---

class SubpartDetail(BaseModel):
    label: str
    marks: float
    question_text: Optional[str] = None
    answer_key: Optional[str] = None


class QuestionDetail(BaseModel):
    question_number: str
    is_sub_question: bool = False
    parent_question: Optional[str] = None
    marks: float
    course_outcome: str = "CO1"
    blooms_taxonomy: str = "Understand"  # Remember | Understand | Apply | Analyze | Evaluate | Create
    difficulty_level: str = "Medium"     # Easy | Medium | Hard
    question_type: str = "Theory"        # Theory | Numerical | Programming | Diagram | MCQ | Short Answer | Long Answer
    expected_depth: str = "Detailed"
    expected_structure: Optional[str] = None
    expected_coverage: Optional[str] = None
    expected_detail: Optional[str] = None
    keywords: List[str] = Field(default_factory=list)
    key_concepts: List[str] = Field(default_factory=list)
    evaluation_criteria: List[str] = Field(default_factory=list)
    is_optional: bool = False
    answer_key: Optional[str] = None
    subparts: List[SubpartDetail] = Field(default_factory=list)


class SectionDetail(BaseModel):
    section_name: str
    is_optional: bool = False
    compulsory_count: Optional[int] = None
    total_marks: float
    instructions: Optional[str] = None
    questions: List[QuestionDetail]
    choice_type: str = "ALL_COMPULSORY"  # ALL_COMPULSORY | SELECT_ANY_N
    total_questions: Optional[int] = None
    questions_to_answer: Optional[int] = None
    marks_per_question: Optional[float] = None
    has_subparts: bool = False
    has_internal_or_choice: bool = False


class ComprehensiveBlueprintSchema(BaseModel):
    blueprint_id: Optional[uuid.UUID] = None
    exam_name: str = "End Semester Examination"
    subject: str
    subject_code: str
    regulation: str = "R2021"
    semester: str = "SEM-05"
    department: str = "Computer Science"
    academic_year: str = "2025-2026"
    exam_type: str = "Internal Assessment"
    duration_minutes: int = 180
    maximum_marks: float = 100.0
    status: str = "Approved"       # Draft | Under Review | Approved | Archived
    blueprint_type: str = "manual_builder"  # manual_builder | json_upload | ai_generated
    is_template: bool = False
    template_name: Optional[str] = None
    sections: List[SectionDetail]
    faculty_answer_key: Optional[List[Dict[str, Any]]] = None

    @field_validator("maximum_marks")
    @classmethod
    def validate_marks_positive(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("Maximum marks must be greater than zero.")
        return v


# --- Validation Result Model ---

class BlueprintJSONValidationResult(BaseModel):
    is_valid: bool
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    total_sections: int = 0
    total_questions: int = 0
    calculated_total_marks: float = 0.0


def validate_blueprint_json(data: Dict[str, Any]) -> BlueprintJSONValidationResult:
    """
    Validates uploaded Blueprint JSON schema, section totals, marks consistency, duplicate numbers, and answer keys.
    """
    errors: list[str] = []
    warnings: list[str] = []
    total_sections = 0
    total_questions = 0
    calculated_marks = 0.0

    try:
        bp = ComprehensiveBlueprintSchema.model_validate(data)
    except Exception as exc:
        return BlueprintJSONValidationResult(
            is_valid=False,
            errors=[f"JSON Schema Validation Error: {exc}"],
        )

    seen_qnos: set[str] = set()

    for sec_idx, sec in enumerate(bp.sections, start=1):
        total_sections += 1
        sec_marks = 0.0
        for q in sec.questions:
            total_questions += 1
            qno = q.question_number.strip().upper()
            if qno in seen_qnos:
                errors.append(f"Duplicate question number detected: '{qno}'.")
            seen_qnos.add(qno)

            if q.marks <= 0:
                errors.append(f"Question '{qno}' in Section '{sec.section_name}' has invalid marks ({q.marks}).")

            if q.subparts:
                subpart_sum = sum(sp.marks for sp in q.subparts)
                if abs(subpart_sum - q.marks) > 0.01:
                    errors.append(
                        f"Question '{qno}' in Section '{sec.section_name}' has subpart marks ({subpart_sum}) "
                        f"that don't sum to the question's marks ({q.marks})."
                    )

            sec_marks += q.marks
            calculated_marks += q.marks

            if not q.answer_key:
                warnings.append(f"Question '{qno}' has no embedded answer key defined.")

        if sec.questions_to_answer is not None and sec.total_questions is not None:
            if sec.questions_to_answer > sec.total_questions:
                errors.append(
                    f"Section '{sec.section_name}' requires answering {sec.questions_to_answer} questions "
                    f"but only declares {sec.total_questions} total questions."
                )
            if len(sec.questions) != sec.total_questions:
                warnings.append(
                    f"Section '{sec.section_name}' declares total_questions={sec.total_questions} but "
                    f"{len(sec.questions)} question(s) were provided."
                )

        if sec.choice_type == "SELECT_ANY_N" and sec.questions_to_answer is not None and sec.marks_per_question is not None:
            expected_marks = sec.questions_to_answer * sec.marks_per_question
            if abs(expected_marks - sec.total_marks) > 0.01 and sec.total_marks > 0:
                warnings.append(
                    f"Section '{sec.section_name}' declared total marks ({sec.total_marks}) differs from "
                    f"questions_to_answer x marks_per_question ({expected_marks})."
                )
        elif abs(sec_marks - sec.total_marks) > 0.01 and sec.total_marks > 0:
            warnings.append(
                f"Section '{sec.section_name}' declared total marks ({sec.total_marks}) differs from sum of question marks ({sec_marks})."
            )

    is_valid = len(errors) == 0

    return BlueprintJSONValidationResult(
        is_valid=is_valid,
        errors=errors,
        warnings=warnings,
        total_sections=total_sections,
        total_questions=total_questions,
        calculated_total_marks=calculated_marks,
    )


# --- Approval & Priority Resolution ---

def get_active_approved_blueprint(db: Session, subject_code: str, semester: Optional[str] = None) -> Optional[ExamBlueprint]:
    """
    Resolves the exact blueprint to be used downstream.
    Priority Order:
    1. Approved Manual Blueprint (manual_builder or json_upload with status == 'Approved')
    2. Approved AI-generated Blueprint (ai_generated with status == 'Approved')
    3. Any active blueprint for the subject
    """
    query = db.query(ExamBlueprint).filter(ExamBlueprint.subject_code == subject_code)
    if semester:
        query = query.filter(ExamBlueprint.semester == semester)

    # 1. Manual approved
    manual_bp = query.filter(
        ExamBlueprint.status == "Approved",
        ExamBlueprint.blueprint_type.in_(["manual_builder", "json_upload"])
    ).order_by(ExamBlueprint.updated_at.desc()).first()

    if manual_bp:
        logger.info("Priority 1: Selected Approved Manual Blueprint '%s' for subject %s", manual_bp.blueprint_id, subject_code)
        return manual_bp

    # 2. AI approved
    ai_bp = query.filter(
        ExamBlueprint.status == "Approved",
        ExamBlueprint.blueprint_type == "ai_generated"
    ).order_by(ExamBlueprint.updated_at.desc()).first()

    if ai_bp:
        logger.info("Priority 2: Selected Approved AI Blueprint '%s' for subject %s", ai_bp.blueprint_id, subject_code)
        return ai_bp

    # 3. Fallback any
    fallback_bp = query.order_by(ExamBlueprint.updated_at.desc()).first()
    if fallback_bp:
        logger.warning("Priority 3: Fallback blueprint '%s' selected for subject %s", fallback_bp.blueprint_id, subject_code)
    return fallback_bp
