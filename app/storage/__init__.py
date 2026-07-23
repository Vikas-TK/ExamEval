"""
Storage Layer package maintaining backwards compatibility for Phase 1 and Phase 2.
Delegates file storage operations to StorageService.
"""

import io
import logging
from app.core.config import get_settings
from app.storage.storage_service import storage_service, StorageService, SupabaseStorageProvider, BaseStorageProvider

logger = logging.getLogger(__name__)
settings = get_settings()

_s3_client = None


def _get_s3_client():
    global _s3_client
    if _s3_client is None:
        import boto3
        kwargs = {"region_name": settings.aws_region or "ap-south-1"}
        if settings.aws_access_key_id:
            kwargs.update(
                aws_access_key_id=settings.aws_access_key_id,
                aws_secret_access_key=settings.aws_secret_access_key,
            )
        if settings.s3_endpoint_url:
            kwargs["endpoint_url"] = settings.s3_endpoint_url
        _s3_client = boto3.client("s3", **kwargs)
    return _s3_client


def _perform_s3_backup(data: bytes, key: str, content_type: str):
    if not settings.aws_backup_enabled:
        return
    try:
        bucket = settings.aws_s3_bucket or settings.s3_bucket_name
        _get_s3_client().put_object(
            Bucket=bucket,
            Key=key,
            Body=data,
            ContentType=content_type,
            ServerSideEncryption="AES256",
        )
        logger.info("S3 backup successful for key=%s", key)
    except Exception as exc:
        logger.warning("S3 backup failed for key=%s: %s", key, exc)


def upload_bytes(data: bytes, key: str, content_type: str = "application/octet-stream") -> str:
    try:
        bucket_name = settings.storage_bucket_question or settings.storage_bucket or "question-papers"
        url = storage_service.upload_file(data, bucket_name, key, content_type)
        if settings.aws_backup_enabled:
            _perform_s3_backup(data, key, content_type)
        return url
    except Exception as exc:
        logger.warning("Storage upload_bytes failed for key=%s: %s", key, exc)
        return f"storage-fallback://{key}"


def upload_image(image_bytes: bytes, evaluation_id: str, stage: str, filename: str) -> str:
    try:
        mapped_stage = "original" if stage == "raw" else stage
        key = f"answer-sheets/{mapped_stage}/{evaluation_id}/{filename}"
        content_type = "image/png" if filename.lower().endswith(".png") else "application/octet-stream"
        bucket = settings.storage_bucket_question or "question-papers"
        return storage_service.upload_file(image_bytes, bucket, key, content_type)
    except Exception as exc:
        logger.warning("Storage upload_image failed for evaluation_id=%s stage=%s: %s", evaluation_id, stage, exc)
        return f"storage-fallback://answer-sheets/{stage}/{evaluation_id}/{filename}"


def upload_transcript(data: bytes, evaluation_id: str) -> str:
    try:
        bucket = settings.storage_bucket_report or "evaluation-reports"
        return storage_service.upload_file(data, bucket, f"answer-sheets/transcripts/{evaluation_id}/transcript.txt", "text/plain; charset=utf-8")
    except Exception as exc:
        logger.warning("Storage upload_transcript failed for evaluation_id=%s: %s", evaluation_id, exc)
        return f"storage-fallback://answer-sheets/transcripts/{evaluation_id}/transcript.txt"


def upload_blueprint(data: bytes, blueprint_id: str) -> str:
    try:
        bucket = settings.storage_bucket_blueprint or "exam-blueprints"
        return storage_service.upload_file(data, bucket, f"{blueprint_id}/blueprint.json", "application/json")
    except Exception as exc:
        logger.warning("Storage upload_blueprint failed for blueprint_id=%s: %s", blueprint_id, exc)
        return f"storage-fallback://{blueprint_id}/blueprint.json"


def upload_faculty_answer_key(data: bytes, blueprint_id: str, filename: str) -> str:
    try:
        content_type = "application/octet-stream"
        if filename.lower().endswith(".txt"):
            content_type = "text/plain; charset=utf-8"
        elif filename.lower().endswith(".docx"):
            content_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        elif filename.lower().endswith(".pdf"):
            content_type = "application/pdf"
        bucket = settings.storage_bucket_faculty or "faculty-answer-keys"
        return storage_service.upload_file(data, bucket, f"{blueprint_id}/{filename}", content_type)
    except Exception as exc:
        logger.warning("Storage upload_faculty_answer_key failed for blueprint_id=%s: %s", blueprint_id, exc)
        return f"storage-fallback://{blueprint_id}/{filename}"


def upload_report(data: bytes, filename: str) -> str:
    try:
        bucket = settings.storage_bucket_report or "evaluation-reports"
        return storage_service.upload_file(data, bucket, filename, "application/octet-stream")
    except Exception as exc:
        logger.warning("Storage upload_report failed for filename=%s: %s", filename, exc)
        return f"storage-fallback://{filename}"


def build_canonical_question_label(raw_qno: str) -> str:
    """Returns clean canonical display label e.g. Q13, Q14, Q15 instead of raw UUIDs."""
    s = str(raw_qno or "").strip().upper()
    if s.startswith("Q") and len(s) > 1 and s[1:].isdigit():
        return s
    if s.isdigit():
        return f"Q{s}"
    return f"Q{s}" if len(s) <= 4 and not s.startswith("Q") else s


def upload_subject_file(
    data: bytes,
    subject_code: str,
    academic_year: str,
    semester: str,
    category: str,
    filename: str,
    student_id: str | None = None,
) -> str:
    """
    Subject-wise naming convention & storage pathing:
    {subject_code}/{academic_year}/{semester}/{category}/[student_id/]{filename}
    """
    clean_sub = (subject_code or "GENERAL").upper().replace("/", "_").strip()
    clean_ay = (academic_year or "2025-2026").replace("/", "-").strip()
    clean_sem = (semester or "SEM").upper().replace(" ", "").strip()

    if student_id and category == "answer-sheets":
        key = f"{clean_sub}/{clean_ay}/{clean_sem}/answer-sheets/{student_id}/{filename}"
    else:
        key = f"{clean_sub}/{clean_ay}/{clean_sem}/{category}/{filename}"

    bucket = settings.storage_bucket_question or settings.storage_bucket or "question-papers"
    content_type = "application/octet-stream"
    if filename.lower().endswith(".pdf"):
        content_type = "application/pdf"
    elif filename.lower().endswith(".png"):
        content_type = "image/png"
    elif filename.lower().endswith(".json"):
        content_type = "application/json"

    try:
        url = storage_service.upload_file(data, bucket, key, content_type)
        if settings.aws_backup_enabled:
            _perform_s3_backup(data, key, content_type)
        return url
    except Exception as exc:
        logger.warning("Storage upload_subject_file failed for key=%s: %s", key, exc)
        return f"storage-fallback://{key}"


def presigned_url(key: str) -> str:
    bucket_name = settings.storage_bucket_question or settings.storage_bucket or "question-papers"
    if settings.supabase_url:
        return f"{settings.supabase_url.rstrip('/')}/storage/v1/object/public/{bucket_name}/{key}"
    return f"https://supabase.local/storage/v1/object/public/{bucket_name}/{key}"


def download_bytes(key: str) -> bytes:
    bucket_name = settings.storage_bucket_question or settings.storage_bucket or "question-papers"
    data = storage_service.download_file(bucket_name, key)
    if not data and settings.aws_backup_enabled:
        try:
            buf = io.BytesIO()
            bucket = settings.aws_s3_bucket or settings.s3_bucket_name
            _get_s3_client().download_fileobj(bucket, key, buf)
            return buf.getvalue()
        except Exception as exc:
            logger.warning("S3 backup download fallback failed for key=%s: %s", key, exc)
    return data


__all__ = [
    "upload_bytes",
    "upload_image",
    "upload_subject_file",
    "build_canonical_question_label",
    "upload_transcript",
    "upload_blueprint",
    "upload_faculty_answer_key",
    "upload_report",
    "presigned_url",
    "download_bytes",
    "StorageService",
    "storage_service",
    "SupabaseStorageProvider",
    "BaseStorageProvider",
]
