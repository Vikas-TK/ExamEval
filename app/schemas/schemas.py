import uuid
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------- Ingestion ----------

class IngestResponse(BaseModel):
    evaluation_id: uuid.UUID
    status: str = "PROCESSING"


# ---------- Quality Report ----------

class QualityReport(BaseModel):
    blur_score: float
    brightness_score: float
    contrast_score: float
    width: int
    height: int
    noise_score: float
    resolution_passed: bool
    skew_angle: float
    is_skewed: bool
    passed: bool
    failure_reasons: List[str] = Field(default_factory=list)


# ---------- OCR Output ----------

class VisualElement(BaseModel):
    type: str  # diagram | table | graph | formula
    description: str
    bbox: List[float]  # [x_min, y_min, x_max, y_max]

    @field_validator("bbox")
    @classmethod
    def validate_bbox(cls, value: List[float]) -> List[float]:
        if len(value) != 4 or any(v < 0 for v in value) or value[2] < value[0] or value[3] < value[1]:
            raise ValueError("bbox must be [x_min, y_min, x_max, y_max]")
        return value


class OCRPage(BaseModel):
    page_number: int
    transcript: str
    structure_map: Optional[dict] = None  # question/answer layout mapping
    confidence: float
    visual_elements: List[VisualElement] = Field(default_factory=list)


class OCRData(BaseModel):
    pages: List[OCRPage]


# ---------- Full record (API response) ----------

class S3Urls(BaseModel):
    raw_script: Optional[str] = None
    enhanced_script: Optional[str] = None
    transcript: Optional[str] = None


class EvaluationRecordOut(BaseModel):
    evaluation_id: uuid.UUID
    subject_id: str
    status: str
    quality_report: Optional[QualityReport] = None
    ocr_data: Optional[OCRData] = None
    s3_urls: S3Urls
    overall_confidence: Optional[float] = None
    needs_manual_review: bool
    error_message: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


# ---------- Manual Review Workflow ----------

class ManualReviewRequest(BaseModel):
    action: str  # "approve" | "reject" | "reprocess"
    notes: Optional[str] = None


class ManualReviewItem(BaseModel):
    evaluation_id: uuid.UUID
    student_hash: Optional[str] = None
    subject_id: str
    status: str
    overall_confidence: Optional[float] = None
    quality_report: Optional[QualityReport] = None
    ocr_data: Optional[OCRData] = None
    s3_urls: S3Urls
    error_message: Optional[str] = None
    created_at: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ManualReviewListResponse(BaseModel):
    items: List[ManualReviewItem]
