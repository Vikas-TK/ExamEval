from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class BlueprintQuestion(BaseModel):
    question_id: str = Field(min_length=1, max_length=100)
    question_number: str = Field(min_length=1, max_length=50)
    question_text: str = Field(min_length=1)
    maximum_marks: float = Field(gt=0)
    question_type: str = Field(min_length=1, max_length=50)
    question_order: int = Field(ge=1)
    faculty_answer: str | None = None


class BlueprintSection(BaseModel):
    section_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=255)
    instructions: str | None = None
    questions: list[BlueprintQuestion] = Field(min_length=1)


class ExamMetadata(BaseModel):
    exam_name: str = Field(min_length=1, max_length=255)
    subject: str = Field(min_length=1, max_length=255)
    subject_code: str = Field(min_length=1, max_length=100)
    regulation: str = Field(min_length=1, max_length=100)
    semester: str = Field(min_length=1, max_length=100)
    department: str = Field(min_length=1, max_length=255)
    duration_minutes: int = Field(gt=0, le=1440)
    maximum_marks: float = Field(gt=0)


class BlueprintCreateResponse(BaseModel):
    blueprint_id: uuid.UUID
    metadata: ExamMetadata
    sections: list[BlueprintSection]
    faculty_answer_key_mapped: bool


class BlueprintOut(BlueprintCreateResponse):
    source_ocr: dict[str, Any]
    faculty_answer_key: list[dict[str, Any]] | None = None
    blueprint_url: str | None = None
    faculty_answer_key_s3_url: str | None = None
    model_config = ConfigDict(from_attributes=True)


class BlueprintCreateForm(BaseModel):
    metadata: ExamMetadata
    ocr: dict[str, Any]

    @field_validator("ocr")
    @classmethod
    def validate_ocr(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(value.get("pages"), list) or not value["pages"]:
            raise ValueError("ocr must contain a non-empty pages list")
        return value