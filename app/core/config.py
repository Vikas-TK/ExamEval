"""
Central configuration for AI AutoGrader system.
Loaded from environment variables using Pydantic Settings v2.
"""

from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Application ---
    app_name: str = "AI AutoGrader"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    log_level: str = "INFO"

    # --- Supabase & Database ---
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_db_url: str = ""
    database_url: str = "sqlite:///./exam_eval_platform.db"
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # --- Security & Identity ---
    secret_key: str = "generate-a-long-random-secret"
    jwt_secret: str = "generate-a-long-random-secret"
    identity_hash_secret: str = "generate-a-long-random-secret"
    api_key: str = ""
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # --- CORS & Trusted Hosts ---
    cors_origins: str = "http://localhost:3000"
    trusted_hosts: str = "localhost,127.0.0.1,testserver"

    # --- Storage Buckets ---
    storage_provider: str = "supabase"
    storage_bucket_question: str = "question-papers"
    storage_bucket_faculty: str = "faculty-answer-keys"
    storage_bucket_blueprint: str = "exam-blueprints"
    storage_bucket_report: str = "evaluation-reports"
    storage_bucket: str = "exam-eval-platform"

    # --- AWS Backup (Optional) ---
    aws_backup_enabled: bool = False
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region: str = "ap-south-1"
    aws_s3_bucket: str = "exam-eval-platform"
    s3_bucket_name: str = "exam-eval-platform"
    s3_endpoint_url: Optional[str] = None
    s3_force_path_style: bool = False

    # --- Upload Constraints ---
    max_upload_bytes: int = 26214400
    max_pdf_pages: int = 20
    allowed_image_types: str = "image/jpeg,image/png,image/jpg"
    allowed_document_types: str = "application/pdf"

    # --- Pipeline & OCR Thresholds ---
    ocr_confidence_threshold: float = 60.0
    blur_threshold: float = 30.0
    brightness_low: int = 20
    brightness_high: int = 254
    skew_angle_threshold: float = 10.0
    min_image_width: int = 0
    min_image_height: int = 0
    min_contrast: float = 10.0
    max_noise_score: float = 50.0
    artifact_url_expiry_seconds: int = 900

    # --- Models ---
    qwen_api_base: str = "http://127.0.0.1:11434/v1"
    qwen_api_key: str = "ollama"
    qwen_model_name: str = "qwen2.5vl-16k"
    blueprint_qwen_model_name: str = "qwen2.5:7b-instruct-q4_K_M"
    ocr_model: str = "qwen2.5vl:7b"
    llm_model: str = "qwen2.5:7b-instruct-q4_K_M"
    evaluation_llm_model: str = "qwen2.5:3b-instruct"
    got_ocr_enabled: bool = True
    got_ocr_model_name: str = "stepfun-ai/GOT-OCR2_0"
    got_ocr_device: str = "auto"
    qwen_num_ctx: int = 16384

    # --- Frontend Integration ---
    frontend_url: str = "http://localhost:3000"
    vite_api_base_url: str = "http://localhost:8000"
    vite_supabase_url: str = ""
    vite_supabase_anon_key: str = ""

    @property
    def normalized_ocr_threshold(self) -> float:
        """Returns OCR confidence threshold normalized to 0.0-1.0 scale."""
        if self.ocr_confidence_threshold > 1.0:
            return self.ocr_confidence_threshold / 100.0
        return self.ocr_confidence_threshold

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
