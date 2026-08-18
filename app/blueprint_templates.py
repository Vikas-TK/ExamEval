"""
Fixed structure for this institution's internal-assessment question papers
(exam_type "INTERNAL_NORMAL", 50 marks total, Part A-D). Single source of
truth reused by:
  - Mode 1 (AI-OCR upload, app/blueprint_service.py) to force correct
    per-question marks onto whatever the OCR parser detected.
  - The startup-seeded "INTERNAL_NORMAL" template ExamBlueprint row, so it's
    listed via GET /manual-review/templates.

Mirrors the INTERNAL_NORMAL_TEMPLATE constant in
frontend/src/pages/QuestionPaperPage.jsx (Mode 2/3, which already collects
this structure directly from the faculty and needs no OCR override).
"""
from __future__ import annotations

import re
import uuid
from typing import Any, TYPE_CHECKING

from app.blueprint_schemas import BlueprintSection

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from app.blueprint_models import ExamBlueprint

TEMPLATE_SUBJECT_CODE = "TEMPLATE-INTERNAL-NORMAL"

INTERNAL_NORMAL_TEMPLATE: dict[str, Any] = {
    "exam_type": "INTERNAL_NORMAL",
    "total_marks": 50,
    "parts": [
        {"part_name": "Part A", "choice_type": "ALL_COMPULSORY", "total_questions": 12, "questions_to_answer": 12, "marks_per_question": 0.5, "has_subparts": False, "has_internal_or_choice": False},
        {"part_name": "Part B", "choice_type": "ALL_COMPULSORY", "total_questions": 3, "questions_to_answer": 3, "marks_per_question": 2.0, "has_subparts": False, "has_internal_or_choice": False},
        {"part_name": "Part C", "choice_type": "SELECT_ANY_N", "total_questions": 3, "questions_to_answer": 2, "marks_per_question": 14.0, "has_subparts": True, "has_internal_or_choice": True},
        {"part_name": "Part D", "choice_type": "SELECT_ANY_N", "total_questions": 2, "questions_to_answer": 1, "marks_per_question": 10.0, "has_subparts": True, "has_internal_or_choice": True},
    ],
}

_PART_MATCH_RE = re.compile(r"(?i)^\s*(?:part|section)\s*[-:]?\s*([a-d])\b")
_QNO_SPLIT_RE = re.compile(r"(?i)^Q?(\d+)\s*([A-Za-z]?)$")


def _match_part(section_name: str | None) -> dict[str, Any] | None:
    if not section_name:
        return None
    m = _PART_MATCH_RE.match(section_name)
    if not m:
        return None
    letter = m.group(1).upper()
    for part in INTERNAL_NORMAL_TEMPLATE["parts"]:
        if part["part_name"].strip().upper().endswith(letter):
            return part
    return None


def _build_instruction_hint(existing: str | None, part: dict[str, Any]) -> str:
    if part["choice_type"] == "SELECT_ANY_N":
        hint = (
            f"Answer any {part['questions_to_answer']} of {part['total_questions']} questions. "
            f"Each question carries {part['marks_per_question']} marks split across sub-parts (a) and (b)."
        )
    else:
        hint = "Answer all questions."
    existing = (existing or "").strip()
    if not existing:
        return hint
    if hint in existing:
        return existing
    return f"{existing} — {hint}"


def apply_internal_normal_marks(sections: list[BlueprintSection]) -> list[BlueprintSection]:
    """
    Overrides Mode 1 (AI-OCR) per-question marks with the fixed INTERNAL_NORMAL
    Part A-D values, matched by the detected Part letter (A/B/C/D) rather than
    trusting the OCR/regex-guessed mark values. Sections that don't match a
    known internal Part are left untouched.

    For Part C/D (has_subparts), OCR sometimes splits a sub-question like
    "13(a)/13(b)" into two separate parsed entries and sometimes keeps them
    combined as one "13" entry - so entries are grouped by their base question
    number first, and the part's marks_per_question is divided across however
    many entries share that base number (instead of forcing the full value
    onto every split entry, which would double-count).
    """
    for section in sections:
        part = _match_part(section.name)
        if part is None:
            continue

        section.name = part["part_name"]
        section.instructions = _build_instruction_hint(section.instructions, part)

        if not part["has_subparts"]:
            for question in section.questions:
                question.maximum_marks = part["marks_per_question"]
            continue

        groups: dict[str, list] = {}
        order: list[str] = []
        for question in section.questions:
            m = _QNO_SPLIT_RE.match(question.question_number.strip())
            base = m.group(1) if m else question.question_number
            if base not in groups:
                groups[base] = []
                order.append(base)
            groups[base].append(question)

        for base in order:
            members = groups[base]
            if len(members) > 1:
                share = round(part["marks_per_question"] / len(members), 2)
                for question in members:
                    question.maximum_marks = share
            else:
                members[0].maximum_marks = part["marks_per_question"]

    return sections


def build_internal_normal_sections() -> list[dict[str, Any]]:
    """Section/question dicts (Mode 2/3 SectionDetail shape) for the seeded template ExamBlueprint row."""
    sections = []
    for part_idx, part in enumerate(INTERNAL_NORMAL_TEMPLATE["parts"]):
        marks = part["marks_per_question"]
        questions = []
        for i in range(part["total_questions"]):
            question = {
                "question_number": f"Q{part_idx * 100 + i + 1}",
                "is_sub_question": False,
                "parent_question": None,
                "marks": marks,
                "course_outcome": "CO1",
                "blooms_taxonomy": "Understand",
                "difficulty_level": "Medium",
                "question_type": "Theory",
                "expected_depth": "Detailed",
                "keywords": [],
                "key_concepts": [],
                "evaluation_criteria": [],
                "is_optional": False,
                "answer_key": None,
                "subparts": (
                    [
                        {"label": "a", "marks": round(marks / 2, 2), "question_text": None, "answer_key": None},
                        {"label": "b", "marks": round(marks / 2, 2), "question_text": None, "answer_key": None},
                    ]
                    if part["has_subparts"] else []
                ),
            }
            questions.append(question)

        sections.append({
            "section_name": part["part_name"],
            "is_optional": part["choice_type"] == "SELECT_ANY_N",
            "compulsory_count": part["questions_to_answer"] if part["choice_type"] == "ALL_COMPULSORY" else None,
            "total_marks": part["questions_to_answer"] * marks,
            "instructions": _build_instruction_hint(None, part),
            "questions": questions,
            "choice_type": part["choice_type"],
            "total_questions": part["total_questions"],
            "questions_to_answer": part["questions_to_answer"],
            "marks_per_question": marks,
            "has_subparts": part["has_subparts"],
            "has_internal_or_choice": part["has_internal_or_choice"],
        })
    return sections


def ensure_internal_normal_template(db: "Session") -> "ExamBlueprint":
    """
    Upserts a reusable, subject-agnostic ExamBlueprint row (is_template=True,
    template_name="INTERNAL_NORMAL") encoding the fixed Part A-D structure, so
    it's durably saved and discoverable via GET /manual-review/templates
    instead of only existing as in-code defaults.
    """
    from app.blueprint_models import ExamBlueprint

    sections = build_internal_normal_sections()
    existing = db.query(ExamBlueprint).filter_by(
        exam_name="INTERNAL_NORMAL Template",
        subject_code=TEMPLATE_SUBJECT_CODE,
        regulation="TEMPLATE",
        semester="TEMPLATE",
    ).first()

    if existing:
        existing.sections = sections
        existing.is_template = True
        existing.template_name = "INTERNAL_NORMAL"
        db.commit()
        return existing

    blueprint = ExamBlueprint(
        blueprint_id=uuid.uuid4(),
        exam_name="INTERNAL_NORMAL Template",
        subject="Internal Assessment Template",
        subject_code=TEMPLATE_SUBJECT_CODE,
        regulation="TEMPLATE",
        semester="TEMPLATE",
        department="All Departments",
        duration_minutes=90,
        maximum_marks=INTERNAL_NORMAL_TEMPLATE["total_marks"],
        sections=sections,
        source_ocr={"source": "INTERNAL_NORMAL fixed template"},
        status="Approved",
        blueprint_type="template",
        exam_type="INTERNAL_NORMAL",
        is_template=True,
        template_name="INTERNAL_NORMAL",
    )
    db.add(blueprint)
    db.commit()
    return blueprint
