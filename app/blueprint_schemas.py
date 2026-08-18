from __future__ import annotations

import uuid
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

class BlueprintQuestion(BaseModel):
    question_id: str = Field(default="", max_length=100)
    question_number: str = Field(default="Q1", max_length=50)
    question_text: str = Field(default="Question text unavailable")
    maximum_marks: float = Field(default=1.0, ge=0)
    question_type: str = Field(default="Descriptive", max_length=50)
    question_order: int = Field(default=1, ge=1)
    faculty_answer: str | None = None

    @field_validator("question_id", mode="before")
    @classmethod
    def default_q_id(cls, v: Any) -> str:
        return str(v) if v else ""

    @model_validator(mode="before")
    @classmethod
    def normalize_question_dict(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            if "maximum_marks" not in data and "marks" in data:
                data["maximum_marks"] = data["marks"]
            if not data.get("maximum_marks"):
                data["maximum_marks"] = 1.0

            if "question_number" not in data or not data["question_number"]:
                data["question_number"] = data.get("number", "Q1")

            if "question_id" not in data or not data["question_id"]:
                data["question_id"] = f"q-{data['question_number']}".lower()

            if "question_text" not in data or data["question_text"] is None:
                data["question_text"] = data.get("text", "Question text unavailable")
            if not str(data["question_text"]).strip():
                data["question_text"] = "Question text unavailable"

            if "question_type" not in data or not data["question_type"]:
                data["question_type"] = "Descriptive"

            if "question_order" not in data or data["question_order"] is None:
                data["question_order"] = 1
        return data


class BlueprintSection(BaseModel):
    section_id: str = Field(default="section-1", max_length=100)
    name: str = Field(default="Part A", max_length=255)
    instructions: str | None = None
    questions: list[BlueprintQuestion] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def normalize_section_dict(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            if "name" not in data and "section_name" in data:
                data["name"] = data["section_name"]
            if not data.get("name"):
                data["name"] = "Part A"

            if "section_id" not in data or not data["section_id"]:
                data["section_id"] = f"section-{data['name']}".lower().replace(" ", "-")

            if "questions" not in data or not isinstance(data["questions"], list):
                data["questions"] = []
        return data


class ExamMetadata(BaseModel):
    exam_name: str = Field(min_length=1, max_length=255)
    subject: str = Field(min_length=1, max_length=255)
    subject_code: str = Field(min_length=1, max_length=100)
    regulation: str = Field(min_length=1, max_length=100)
    semester: str = Field(min_length=1, max_length=100)
    department: str = Field(min_length=1, max_length=255)
    duration_minutes: int = Field(gt=0, le=1440)
    maximum_marks: float = Field(gt=0)
    exam_type: str = "INTERNAL_NORMAL"


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