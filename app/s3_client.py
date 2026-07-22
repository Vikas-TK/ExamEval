"""
Backward-compatibility adapter forwarding to the unified Storage Abstraction Layer (app.storage).
Primary Storage Provider: Supabase Storage.
Backup Provider: Amazon S3 (Controlled by AWS_BACKUP_ENABLED feature flag).
"""

from app.storage import (
    upload_bytes,
    upload_image,
    upload_transcript,
    upload_blueprint,
    upload_faculty_answer_key,
    upload_report,
    presigned_url,
    download_bytes,
)

__all__ = [
    "upload_bytes",
    "upload_image",
    "upload_transcript",
    "upload_blueprint",
    "upload_faculty_answer_key",
    "upload_report",
    "presigned_url",
    "download_bytes",
]
