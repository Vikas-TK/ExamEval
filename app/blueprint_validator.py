"""
Module 11 – Blueprint Verification Before Mapping
Pre-mapping validator ensuring every question has marks, answer key, consistent numbering,
sections, and optional question configuration before Phase 3 begins.
"""
from __future__ import annotations

import logging
from typing import Dict, Any, List
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class QuestionValidationStatus(BaseModel):
    question_number: str
    has_marks: bool
    marks_assigned: float
    has_answer_key: bool
    has_section: bool
    is_valid: bool
    issues: List[str] = Field(default_factory=list)


class BlueprintValidationReport(BaseModel):
    blueprint_id: str
    is_valid: bool
    total_questions: int
    valid_questions: int
    invalid_questions: int
    errors: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    question_statuses: List[QuestionValidationStatus] = Field(default_factory=list)


def validate_blueprint_before_mapping(blueprint_dict: Dict[str, Any]) -> BlueprintValidationReport:
    """
    Validates Blueprint integrity before Phase 3 Mapping starts.
    Checks marks assignment, answer key presence, numbering consistency, and section alignment.
    """
    bp_id = str(blueprint_dict.get("blueprint_id", "unknown"))
    sections = blueprint_dict.get("sections", [])
    answer_keys = blueprint_dict.get("faculty_answer_key", [])

    # Map faculty answer key by question number
    key_map = {}
    if isinstance(answer_keys, list):
        for item in answer_keys:
            if isinstance(item, dict):
                qno = str(item.get("question_number", "")).strip().upper()
                key_map[qno] = item.get("answer", "")

    errors: list[str] = []
    warnings: list[str] = []
    statuses: list[QuestionValidationStatus] = []

    if not sections:
        errors.append("Blueprint contains no defined sections.")
        return BlueprintValidationReport(
            blueprint_id=bp_id,
            is_valid=False,
            total_questions=0,
            valid_questions=0,
            invalid_questions=0,
            errors=errors,
            warnings=warnings,
            question_statuses=[],
        )

    q_count = 0
    valid_count = 0
    invalid_count = 0

    for sec in sections:
        sec_name = sec.get("section_name", "General")
        questions = sec.get("questions", [])
        for q in questions:
            q_count += 1
            q_num = str(q.get("question_number", f"Q{q_count}")).strip().upper()
            marks = float(q.get("marks", 0.0))
            q_issues: list[str] = []

            has_m = marks > 0.0
            if not has_m:
                q_issues.append(f"Question '{q_num}' has 0 or invalid marks assigned.")

            has_k = bool(key_map.get(q_num) or q.get("answer_key") or q.get("model_answer"))
            if not has_k:
                q_issues.append(f"Question '{q_num}' has no faculty answer key defined.")
                warnings.append(f"Answer key missing for question '{q_num}' in section '{sec_name}'.")

            q_is_valid = has_m and len(q_issues) == 0

            if q_is_valid:
                valid_count += 1
            else:
                invalid_count += 1
                errors.extend(q_issues)

            statuses.append(
                QuestionValidationStatus(
                    question_number=q_num,
                    has_marks=has_m,
                    marks_assigned=marks,
                    has_answer_key=has_k,
                    has_section=bool(sec_name),
                    is_valid=q_is_valid,
                    issues=q_issues,
                )
            )

    overall_valid = invalid_count == 0 and len(errors) == 0

    return BlueprintValidationReport(
        blueprint_id=bp_id,
        is_valid=overall_valid,
        total_questions=q_count,
        valid_questions=valid_count,
        invalid_questions=invalid_count,
        errors=list(dict.fromkeys(errors)),
        warnings=list(dict.fromkeys(warnings)),
        question_statuses=statuses,
    )
