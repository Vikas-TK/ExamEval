import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import EvaluationRecord, EvaluationStatus, StudentIdentity
from app.pipeline import process_evaluation
from app.schemas import (
    EvaluationRecordOut, IngestResponse, OCRData, QualityReport, S3Urls,
    ManualReviewRequest, ManualReviewItem, ManualReviewListResponse,
)
from app.config import get_settings
from app.security import require_api_key
from app.storage import presigned_url

router = APIRouter(prefix="/evaluations", tags=["evaluations"])

ALLOWED_CONTENT_TYPES = {"image/png", "image/jpeg", "image/jpg", "application/pdf"}
settings = get_settings()


@router.post("", response_model=IngestResponse, status_code=202)
async def submit_evaluation(
    background_tasks: BackgroundTasks,
    regulation: str = Form(...),
    semester: str = Form(...),
    subject_id: str = Form(...),
    register_number: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _auth: None = Depends(require_api_key),
):
    if not file.filename:
        raise HTTPException(400, "A filename is required")
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(400, f"Unsupported file type: {file.content_type}")

    raw_bytes = await file.read(settings.max_upload_bytes + 1)
    if len(raw_bytes) > settings.max_upload_bytes:
        raise HTTPException(413, "Uploaded file exceeds the configured size limit")
    if not raw_bytes:
        raise HTTPException(400, "Uploaded file is empty")

    evaluation_id = uuid.uuid4()

    # --- PII written ONLY here, to StudentIdentity ---
    identity = StudentIdentity(
        evaluation_id=evaluation_id,
        register_number=register_number.strip(),
        regulation=regulation,
        semester=semester,
        subject_id=subject_id,
    )
    try:
        # Commit StudentIdentity first so the parent FK row is durably present
        # before we insert EvaluationRecord.  Without a SQLAlchemy relationship()
        # between the two models the ORM cannot guarantee INSERT ordering during a
        # single commit's implicit flush, which causes a FK violation on PostgreSQL.
        db.add(identity)
        db.commit()  # parent row is now visible to any subsequent INSERT on this connection
    except Exception as exc:
        db.rollback()
        raise HTTPException(503, f"Could not create evaluation: {exc}") from exc

    try:
        # Everything downstream only ever sees evaluation_id + subject_id.
        record = EvaluationRecord(
            evaluation_id=evaluation_id,
            subject_id=subject_id,
            status=EvaluationStatus.PROCESSING,
        )
        db.add(record)
        db.commit()
    except Exception as exc:
        db.rollback()
        # Best-effort cleanup: remove the orphaned StudentIdentity row so the
        # evaluation_id doesn't linger without a corresponding EvaluationRecord.
        try:
            db.delete(identity)
            db.commit()
        except Exception:
            db.rollback()
        raise HTTPException(503, f"Could not create evaluation: {exc}") from exc


    background_tasks.add_task(
        process_evaluation,
        evaluation_id=evaluation_id,
        raw_bytes=raw_bytes,
        filename=file.filename,
    )

    return IngestResponse(evaluation_id=evaluation_id, status="PROCESSING")


@router.get("", tags=["evaluations"])
def list_evaluations(
    page: int = 1,
    page_size: int = 50,
    db: Session = Depends(get_db),
):
    """List all evaluation records (newest first). No auth required for UI dropdowns."""
    records = (
        db.query(EvaluationRecord)
        .order_by(EvaluationRecord.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    items = [
        {
            "evaluation_id": str(r.evaluation_id),
            "subject_id": r.subject_id,
            "status": r.status.value if r.status else "UNKNOWN",
            "overall_confidence": r.overall_confidence,
            "needs_manual_review": r.needs_manual_review,
            "created_at": str(r.created_at) if r.created_at else None,
        }
        for r in records
    ]
    return {"items": items, "page": page, "page_size": page_size}


@router.get("/manual-review", response_model=ManualReviewListResponse)
def list_manual_reviews(
    db: Session = Depends(get_db),
    _auth: None = Depends(require_api_key),
):
    records = (
        db.query(EvaluationRecord)
        .filter(EvaluationRecord.needs_manual_review == True)
        .order_by(EvaluationRecord.created_at.desc())
        .all()
    )
    items = []
    for r in records:
        identity = db.query(StudentIdentity).filter_by(evaluation_id=r.evaluation_id).first()
        quality_report = None
        if r.blur_score is not None:
            quality_report = QualityReport(
                blur_score=r.blur_score,
                brightness_score=r.brightness_score,
                contrast_score=r.contrast_score,
                skew_angle=r.skew_angle,
                is_skewed=r.is_skewed,
                passed=bool(r.quality_passed),
                width=int(r.width or 0),
                height=int(r.height or 0),
                noise_score=float(r.noise_score or 0),
                resolution_passed=bool(r.resolution_passed),
                failure_reasons=[] if r.quality_passed else (r.error_message or "").split("; "),
            )
        ocr_data = OCRData(**r.ocr_data) if r.ocr_data else None
        
        def signed(url: str | None) -> str | None:
            if not url:
                return None
            if url.startswith("storage-fallback://") or url.startswith("http://") or url.startswith("https://"):
                return url
            return presigned_url(url.split("/", 3)[-1])

        items.append(
            ManualReviewItem(
                evaluation_id=r.evaluation_id,
                register_number=identity.register_number if identity else None,
                subject_id=r.subject_id,
                status=r.status.value,
                overall_confidence=r.overall_confidence,
                quality_report=quality_report,
                ocr_data=ocr_data,
                s3_urls=S3Urls(
                    raw_script=signed(r.raw_s3_url),
                    enhanced_script=signed(r.enhanced_s3_url),
                    transcript=signed(r.transcript_s3_url),
                ),
                error_message=r.error_message,
                created_at=str(r.created_at) if r.created_at else None,
            )
        )
    return ManualReviewListResponse(items=items)


@router.get("/{evaluation_id}", response_model=EvaluationRecordOut)
def get_evaluation(
    evaluation_id: uuid.UUID,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_api_key),
):
    record = db.query(EvaluationRecord).filter_by(evaluation_id=evaluation_id).first()
    if record is None:
        raise HTTPException(404, "evaluation_id not found")

    quality_report = None
    if record.blur_score is not None:
        quality_report = QualityReport(
            blur_score=record.blur_score,
            brightness_score=record.brightness_score,
            contrast_score=record.contrast_score,
            skew_angle=record.skew_angle,
            is_skewed=record.is_skewed,
            passed=bool(record.quality_passed),
            width=int(record.width or 0),
            height=int(record.height or 0),
            noise_score=float(record.noise_score or 0),
            resolution_passed=bool(record.resolution_passed),
            failure_reasons=[] if record.quality_passed else (record.error_message or "").split("; "),
        )

    ocr_data = OCRData(**record.ocr_data) if record.ocr_data else None

    def signed(url: str | None) -> str | None:
        if not url:
            return None
        if url.startswith("storage-fallback://") or url.startswith("http://") or url.startswith("https://"):
            return url
        return presigned_url(url.split("/", 3)[-1])

    return EvaluationRecordOut(
        evaluation_id=record.evaluation_id,
        subject_id=record.subject_id,
        status=record.status.value,
        quality_report=quality_report,
        ocr_data=ocr_data,
        s3_urls=S3Urls(raw_script=signed(record.raw_s3_url),
                   enhanced_script=signed(record.enhanced_s3_url),
                   transcript=signed(record.transcript_s3_url)),
        overall_confidence=record.overall_confidence,
        needs_manual_review=record.needs_manual_review,
        error_message=record.error_message,
    )


@router.get("/{evaluation_id}/transcript")
def download_transcript(
    evaluation_id: uuid.UUID,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_api_key),
):
    record = db.query(EvaluationRecord).filter_by(evaluation_id=evaluation_id).first()
    if record is None or not record.transcript_s3_url:
        raise HTTPException(404, "OCR transcript not found")
    key = record.transcript_s3_url.split("/", 3)[-1]
    return {"url": presigned_url(key), "expires_in": settings.artifact_url_expiry_seconds}


@router.post("/{evaluation_id}/review", response_model=EvaluationRecordOut)
def review_evaluation(
    evaluation_id: uuid.UUID,
    review_req: ManualReviewRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    _auth: None = Depends(require_api_key),
):
    record = db.query(EvaluationRecord).filter_by(evaluation_id=evaluation_id).first()
    if record is None:
        raise HTTPException(404, "evaluation_id not found")

    action = review_req.action.lower()
    if action == "approve":
        record.status = EvaluationStatus.COMPLETED
        record.needs_manual_review = False
        record.error_message = f"Manually approved. Notes: {review_req.notes}" if review_req.notes else "Manually approved"
    elif action == "reject":
        record.status = EvaluationStatus.FAILED
        record.needs_manual_review = False
        record.error_message = f"Manually rejected. Notes: {review_req.notes}" if review_req.notes else "Manually rejected"
    elif action == "reprocess":
        record.status = EvaluationStatus.PROCESSING
        record.needs_manual_review = False
        record.error_message = None
    else:
        raise HTTPException(400, "Invalid action. Choose 'approve', 'reject', or 'reprocess'.")

    db.commit()
    db.refresh(record)
    return get_evaluation(evaluation_id=evaluation_id, db=db, _auth=None)


