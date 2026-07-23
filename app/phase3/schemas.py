"""
Phase 3 – Pydantic Schemas
Request and response models for the Q&A Mapping Engine.
"""
from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field


# ─── Request ─────────────────────────────────────────────────────────────────

class Phase3TriggerRequest(BaseModel):
    evaluation_id: uuid.UUID = Field(..., description="Evaluation UUID from Phase 1")
    blueprint_id: uuid.UUID = Field(..., description="Exam blueprint UUID from Phase 2")


# ─── Internal intermediate types ─────────────────────────────────────────────

class QuestionAnchor(BaseModel):
    """One detected question anchor in the OCR text."""
    raw_label: str          # e.g. "Q1", "1.", "(a)"
    normalized: str         # e.g. "Q1"
    char_offset: int        # byte offset in flat text where anchor starts
    page_number: int
    confidence: float       # 0.0–1.0
    detection_method: str   # "regex" | "llm_fallback"


class AnswerBlock(BaseModel):
    """Segmented answer text belonging to one question anchor."""
    anchor: QuestionAnchor
    raw_text: str
    visual_elements: list[dict[str, Any]] = Field(default_factory=list)
    page_numbers: list[int] = Field(default_factory=list)


class BlueprintQuestion(BaseModel):
    """Flattened question from the blueprint sections."""
    question_id: str
    question_number: str
    question_text: str | None
    maximum_marks: float
    question_type: str
    section_name: str
    question_order: int


class MappedQA(BaseModel):
    """A single mapped question–answer record ready for storage."""
    mapping_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    evaluation_id: uuid.UUID
    blueprint_id: uuid.UUID
    question_id: str
    question_number: str
    question_text: str | None
    maximum_marks: float
    question_type: str
    section_name: str
    student_answer: str | None
    answer_length: int
    visual_elements: list[dict[str, Any]] = Field(default_factory=list)
    anchor_text: str | None
    anchor_confidence: float
    mapping_status: str    # MAPPED | UNMAPPED | SKIPPED
    question_sequence: int


class ValidationReport(BaseModel):
    """Validation outcome for the full Q&A mapping."""
    validation_status: str   # VALID | INVALID | WARNING
    total_blueprint_questions: int
    mapped_count: int
    unmapped_count: int
    skipped_count: int
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ─── Response ─────────────────────────────────────────────────────────────────

class Phase3Response(BaseModel):
    status: str
    student_id: str | None
    evaluation_id: str
    blueprint_id: str
    questions_processed: int
    mapped_questions: int
    unmapped_questions: int
    skipped_questions: int
    validation_status: str
    output: str
    validation_report: ValidationReport | None = None


class MappedQAOut(BaseModel):
    mapping_id: uuid.UUID
    evaluation_id: uuid.UUID
    blueprint_id: uuid.UUID | None
    question_id: str
    question_number: str
    question_text: str | None
    maximum_marks: float | None
    question_type: str | None
    section_name: str | None
    student_answer: str | None
    answer_length: int
    visual_elements: list[dict[str, Any]] | None
    anchor_confidence: float | None
    anchor_text: str | None
    mapping_status: str
    validation_status: str
    validation_warnings: list[str] | None
    validation_errors: list[str] | None
    question_sequence: int

    class Config:
        from_attributes = True
