"""
Phase 4 – Pydantic Schemas
"""
from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


# ─── Request ──────────────────────────────────────────────────────────────────

class Phase4TriggerRequest(BaseModel):
    evaluation_id: uuid.UUID
    blueprint_id: uuid.UUID


# ─── Internal ─────────────────────────────────────────────────────────────────

class ScoringResult(BaseModel):
    score: float
    feedback: str
    confidence: float


# ─── Response: single evaluation ──────────────────────────────────────────────

class ScoredAnswerOut(BaseModel):
    eval_result_id: uuid.UUID
    evaluation_id: uuid.UUID
    blueprint_id: uuid.UUID | None
    question_id: str
    question_number: str
    question_text: str | None
    section_name: str | None
    maximum_marks: float
    student_answer: str | None
    answer_key: str | None
    scored_marks: float | None
    ai_feedback: str | None
    ai_confidence: float | None
    evaluation_status: str
    question_sequence: int

    class Config:
        from_attributes = True


class Phase4Response(BaseModel):
    status: str
    evaluation_id: str
    blueprint_id: str
    student_id: str | None
    questions_evaluated: int
    total_scored_marks: float
    total_maximum_marks: float
    percentage: float
    output: str


# ─── Marks Matrix ─────────────────────────────────────────────────────────────

class MatrixCell(BaseModel):
    evaluation_id: str
    register_number: str          # resolved from student_hash via StudentIdentity
    question_scores: dict[str, float | None]   # question_number → scored_marks
    section_totals: dict[str, float]            # section_name → subtotal
    grand_total: float
    maximum_total: float
    percentage: float


class MarksMatrixResponse(BaseModel):
    blueprint_id: str
    exam_name: str
    subject: str
    subject_code: str
    question_headers: list[dict[str, Any]]     # [{question_number, maximum_marks, section_name}]
    section_headers: list[dict[str, Any]]      # [{section_name, section_max}]
    rows: list[MatrixCell]
    total_students: int
