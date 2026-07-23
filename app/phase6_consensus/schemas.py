"""
Phase 6 – Schemas for Multi-Agent Consensus Engine
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict


class ConsolidatedEvaluationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    consolidated_id: uuid.UUID
    student_id: str
    evaluation_id: uuid.UUID
    blueprint_id: Optional[uuid.UUID] = None

    question_id: str
    question_number: str
    maximum_marks: float

    accuracy_score: float
    completeness_score: float
    depth_score: float
    weighted_score: float

    final_marks: float
    percentage: float

    agreement_level: str
    evaluation_confidence: float
    evaluation_status: str

    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    missing_concepts: List[str] = Field(default_factory=list)
    improvement_suggestions: List[str] = Field(default_factory=list)
    final_remarks: Optional[str] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ConsensusResponse(BaseModel):
    evaluation_id: uuid.UUID
    blueprint_id: Optional[uuid.UUID] = None
    total_questions: int
    total_max_marks: float
    total_scored_marks: float
    overall_percentage: float
    overall_status: str
    consolidated_evaluations: List[ConsolidatedEvaluationOut]
    status: str = "COMPLETED"
    execution_time_seconds: float = 0.0
