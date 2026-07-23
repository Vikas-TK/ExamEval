from typing import Optional, List
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Response, Query
from fastapi.responses import StreamingResponse
import io

from app.core.config import get_settings
from app.core.supabase_client import SupabaseClientManager
from app.security import require_api_key
from app.storage.storage_service import storage_service

router = APIRouter(prefix="/api/storage", tags=["storage"])
settings = get_settings()

REQUIRED_BUCKETS = [
    settings.storage_bucket_question or "question-papers",
    settings.storage_bucket_faculty or "faculty-answer-keys",
    settings.storage_bucket_blueprint or "exam-blueprints",
    settings.storage_bucket_report or "evaluation-reports",
]


@router.get("/status")
def get_storage_status(
    _auth: None = Depends(require_api_key),
):
    """Checks the existence and status of all configured Supabase Storage buckets."""
    bucket_statuses = []
    client = None
    try:
        client = SupabaseClientManager.get_client()
    except Exception as exc:
        pass

    for b_name in REQUIRED_BUCKETS:
        status = "unavailable"
        file_count = 0
        if client:
            try:
                files = storage_service.list_files(b_name)
                file_count = len(files)
                status = "active"
            except Exception:
                status = "error"
        else:
            status = "configured"

        bucket_statuses.append({
            "bucket_name": b_name,
            "status": status,
            "provider": settings.storage_provider,
            "approx_files": file_count,
        })

    return {
        "storage_provider": settings.storage_provider,
        "supabase_url": settings.supabase_url,
        "buckets": bucket_statuses,
        "total_buckets": len(bucket_statuses),
    }


@router.get("/list/{bucket_name}")
def list_bucket_files(
    bucket_name: str,
    prefix: Optional[str] = Query(default=""),
    _auth: None = Depends(require_api_key),
):
    """Lists files within a specified Supabase Storage bucket."""
    if bucket_name not in REQUIRED_BUCKETS and bucket_name != settings.storage_bucket:
        raise HTTPException(400, f"Invalid storage bucket: '{bucket_name}'")
    files = storage_service.list_files(bucket_name, prefix or "")
    return {"bucket_name": bucket_name, "files": files}


@router.post("/upload")
async def upload_storage_file(
    bucket_name: str = Form(...),
    file_path: str = Form(...),
    file: UploadFile = File(...),
    _auth: None = Depends(require_api_key),
):
    """Uploads a file to a specified storage bucket and returns the public access URL."""
    if bucket_name not in REQUIRED_BUCKETS and bucket_name != settings.storage_bucket:
        raise HTTPException(400, f"Invalid storage bucket: '{bucket_name}'")

    raw_bytes = await file.read(settings.max_upload_bytes + 1)
    if len(raw_bytes) > settings.max_upload_bytes:
        raise HTTPException(413, "Uploaded file exceeds maximum allowed size limit.")

    content_type = file.content_type or "application/octet-stream"
    url = storage_service.upload_file(raw_bytes, bucket_name, file_path, content_type)
    return {
        "bucket_name": bucket_name,
        "file_path": file_path,
        "url": url,
        "size_bytes": len(raw_bytes),
        "content_type": content_type,
    }


@router.get("/download/{bucket_name}/{file_path:path}")
def download_storage_file(
    bucket_name: str,
    file_path: str,
    _auth: None = Depends(require_api_key),
):
    """Downloads bytes of a file from a specified storage bucket."""
    if bucket_name not in REQUIRED_BUCKETS and bucket_name != settings.storage_bucket:
        raise HTTPException(400, f"Invalid storage bucket: '{bucket_name}'")

    data = storage_service.download_file(bucket_name, file_path)
    if not data:
        raise HTTPException(404, f"File '{file_path}' not found in bucket '{bucket_name}'")

    filename = file_path.split("/")[-1]
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.delete("/delete/{bucket_name}/{file_path:path}")
def delete_storage_file(
    bucket_name: str,
    file_path: str,
    _auth: None = Depends(require_api_key),
):
    """Deletes a file from a specified storage bucket."""
    if bucket_name not in REQUIRED_BUCKETS and bucket_name != settings.storage_bucket:
        raise HTTPException(400, f"Invalid storage bucket: '{bucket_name}'")

    success = storage_service.delete_file(bucket_name, file_path)
    if not success:
        raise HTTPException(500, f"Could not delete file '{file_path}' from bucket '{bucket_name}'")

    return {"status": "deleted", "bucket_name": bucket_name, "file_path": file_path}
