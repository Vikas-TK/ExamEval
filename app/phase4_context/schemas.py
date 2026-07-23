"""
Phase 4 – Schemas for Evaluation Context Builder
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, List, Dict, Optional
from pydantic import BaseModel, Field, ConfigDict


class EvaluationContextOut(BaseModel):
    """Structured Evaluation Context JSON for Phase 5 AI Evaluation Agents."""
    model_config = ConfigDict(from_attributes=True)

    context_id: uuid.UUID
    student_id: str
    evaluation_id: uuid.UUID
    blueprint_id: Optional[uuid.UUID] = None

    question_id: str
    question_number: str
    question_text: str
    question_intent: str
    question_type: str
    maximum_marks: float
    expected_answer_depth: str

    student_answer: Optional[str] = ""

    expected_answer_characteristics: List[str] = Field(default_factory=list)
    expected_structure: Optional[str] = None
    expected_coverage: Optional[str] = None
    expected_detail: Optional[str] = None

    key_concepts: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    subject_domain: Optional[str] = "General Computer Science"
    difficulty_level: Optional[str] = "Medium"

    evaluation_criteria: List[str] = Field(default_factory=list)
    visual_elements: List[Dict[str, Any]] = Field(default_factory=list)

    status: str = "READY_FOR_PHASE_5"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class EvaluationContextCreate(BaseModel):
    """Payload to build context for a single question."""
    student_id: str
    evaluation_id: uuid.UUID
    blueprint_id: uuid.UUID
    question_id: str
    question_number: str
    question_text: str
    student_answer: Optional[str] = ""
    question_type: Optional[str] = "Descriptive"
    maximum_marks: float = 5.0
    visual_elements: Optional[List[Dict[str, Any]]] = Field(default_factory=list)


class ProcessingSummary(BaseModel):
    """Processing Summary for Phase 4 Execution."""
    total_questions: int = 0
    successfully_built: int = 0
    incomplete_questions: int = 0
    status: str = "COMPLETED"
    execution_time_seconds: float = 0.0


class ValidationReport(BaseModel):
    """Validation Report for Input QA JSON."""
    is_valid: bool = True
    student_id_valid: bool = True
    evaluation_id_valid: bool = True
    blueprint_id_valid: bool = True
    question_ids_valid: bool = True
    missing_fields: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class EvaluationContextBuildResponse(BaseModel):
    """Final Output Object for Phase 4 Endpoint."""
    evaluation_contexts: List[EvaluationContextOut]
    processing_summary: ProcessingSummary
    validation_report: ValidationReport
    storage_status: str = "STORED_IN_POSTGRESQL"
