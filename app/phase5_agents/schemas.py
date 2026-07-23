"""
Phase 5 – Schemas for Multi-Agent Answer Evaluation Engine
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, List, Optional
from pydantic import BaseModel, Field, ConfigDict


class AccuracyReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    report_id: uuid.UUID
    evaluation_id: uuid.UUID
    question_id: str
    question_number: str
    score: float
    percentage: float
    confidence: float = 1.0
    correct_concepts: List[str] = Field(default_factory=list)
    incorrect_concepts: List[str] = Field(default_factory=list)
    technical_errors: List[str] = Field(default_factory=list)
    remarks: Optional[str] = None
    status: str = "COMPLETED"


class CompletenessReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    report_id: uuid.UUID
    evaluation_id: uuid.UUID
    question_id: str
    question_number: str
    score: float
    percentage: float
    confidence: float = 1.0
    covered_points: List[str] = Field(default_factory=list)
    missing_points: List[str] = Field(default_factory=list)
    missing_keywords: List[str] = Field(default_factory=list)
    missing_concepts: List[str] = Field(default_factory=list)
    remarks: Optional[str] = None
    status: str = "COMPLETED"


class DepthReportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    report_id: uuid.UUID
    evaluation_id: uuid.UUID
    question_id: str
    question_number: str
    score: float
    percentage: float
    confidence: float = 1.0
    strong_sections: List[str] = Field(default_factory=list)
    weak_sections: List[str] = Field(default_factory=list)
    remarks: Optional[str] = None
    status: str = "COMPLETED"


class QuestionAgentResults(BaseModel):
    question_id: str
    question_number: str
    maximum_marks: float
    accuracy_report: AccuracyReportOut
    completeness_report: CompletenessReportOut
    depth_report: DepthReportOut


class MultiAgentEvaluationResponse(BaseModel):
    evaluation_id: uuid.UUID
    blueprint_id: Optional[uuid.UUID] = None
    total_questions: int
    question_evaluations: List[QuestionAgentResults]
    status: str = "COMPLETED"
    execution_time_seconds: float = 0.0
