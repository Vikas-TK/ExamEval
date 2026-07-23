"""
pipeline.py

The background task triggered right after the 202 response. Everything
here operates ONLY on evaluation_id - never register_number.
"""
from __future__ import annotations

import logging
import uuid
from typing import List

from sqlalchemy.orm import Session

from app import image_processor, ocr_engine, storage
from app.config import get_settings
from app.database import SessionLocal
from app.models import EvaluationRecord, EvaluationStatus

logger = logging.getLogger(__name__)
settings = get_settings()


import glob
import os
import shutil
from typing import List, Optional


def _find_poppler_path() -> Optional[str]:
    """Dynamically locates Poppler binary directory on Windows if not in system PATH."""
    if shutil.which("pdftoppm"):
        return None

    candidate_paths = [
        r"C:\poppler\Library\bin",
        r"C:\poppler\bin",
        r"C:\Program Files\Poppler\Library\bin",
        r"C:\Program Files\Poppler\bin",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "poppler", "Library", "bin"),
    ]

    winget_dir = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Packages")
    if os.path.exists(winget_dir):
        found = glob.glob(os.path.join(winget_dir, "**", "pdftoppm.exe"), recursive=True)
        if found:
            return os.path.dirname(found[0])

    for path in candidate_paths:
        if os.path.exists(os.path.join(path, "pdftoppm.exe")):
            return path

    return None


def _fallback_pdf_extract(raw_bytes: bytes) -> List[bytes]:
    """Fallback mechanism using pypdf to extract embedded images directly from PDF pages if Poppler is missing."""
    import io
    from pypdf import PdfReader
    pages = []
    try:
        reader = PdfReader(io.BytesIO(raw_bytes))
        for page in reader.pages[:settings.max_pdf_pages]:
            page_images = []
            for img in page.images:
                page_images.append(img.data)
            if page_images:
                pages.append(page_images[0])
    except Exception as exc:
        logger.warning("pypdf image extraction fallback failed: %s", exc)
    return pages


def _pages_from_upload(raw_bytes: bytes, filename: str) -> List[bytes]:
    """
    Returns a list of per-page raw image bytes. PDFs are split into
    pages via pdf2image; single images are returned as a 1-page list.
    """
    if filename.lower().endswith(".pdf"):
        poppler_path = _find_poppler_path()
        try:
            from pdf2image import convert_from_bytes
            kwargs = {"dpi": 300, "first_page": 1, "last_page": settings.max_pdf_pages}
            if poppler_path:
                kwargs["poppler_path"] = poppler_path
            pil_pages = convert_from_bytes(raw_bytes, **kwargs)
            pages = []
            for pil_img in pil_pages:
                import io
                buf = io.BytesIO()
                pil_img.save(buf, format="PNG")
                pages.append(buf.getvalue())
            return pages
        except Exception as exc:
            logger.warning("pdf2image conversion failed (poppler_path=%s): %s. Attempting pypdf fallback...", poppler_path, exc)
            fallback_pages = _fallback_pdf_extract(raw_bytes)
            if fallback_pages:
                return fallback_pages
            raise exc
    return [raw_bytes]


def _commit_with_retry(db: Session, record: EvaluationRecord) -> Session:
    """
    Attempts db.commit(). If the DB connection was dropped (e.g. Supabase PgBouncer timeout),
    automatically rolls back, creates a fresh session, copies updated record attributes,
    and commits. Returns the active session.
    """
    try:
        db.commit()
        return db
    except Exception as exc:
        logger.warning("Database commit error (%s). Re-establishing fresh session for %s...", exc, record.evaluation_id)
        try:
            db.rollback()
            db.close()
        except Exception:
            pass

        new_db = SessionLocal()
        try:
            fresh_record = new_db.query(EvaluationRecord).filter_by(evaluation_id=record.evaluation_id).first()
            if fresh_record:
                fields = [
                    "blur_score", "brightness_score", "contrast_score", "skew_angle", "is_skewed",
                    "quality_passed", "width", "height", "noise_score", "resolution_passed",
                    "ocr_data", "needs_manual_review", "overall_confidence", "raw_s3_url",
                    "enhanced_s3_url", "transcript_s3_url", "error_message", "status"
                ]
                for field in fields:
                    val = getattr(record, field, None)
                    if val is not None:
                        setattr(fresh_record, field, val)
                new_db.commit()
            return new_db
        except Exception as retry_exc:
            logger.exception("Retry commit failed for %s: %s", record.evaluation_id, retry_exc)
            new_db.rollback()
            return new_db


def process_evaluation(evaluation_id: uuid.UUID, raw_bytes: bytes, filename: str) -> None:
    """
    Synchronous pipeline body, meant to be run inside a FastAPI
    BackgroundTask (or swapped into a Celery task with the same
    signature for real production load).
    """
    db: Session = SessionLocal()
    try:
        record = db.query(EvaluationRecord).filter_by(evaluation_id=evaluation_id).first()
        if record is None:
            logger.error("No EvaluationRecord found for %s — aborting pipeline", evaluation_id)
            return

        try:
            pages_raw = _pages_from_upload(raw_bytes, filename)
        except Exception as exc:  # noqa: BLE001
            _mark_failed(db, record, f"could not split/decode upload: {exc}")
            return

        # Phase 1 scope: evaluate/enhance/OCR the first page for the
        # quality gate + record-level scores
        try:
            first_image = image_processor.bytes_to_image(pages_raw[0])
        except Exception as exc:  # noqa: BLE001
            _mark_failed(db, record, f"could not decode page 1: {exc}")
            return

        quality_report = image_processor.validate_quality(first_image)
        record.blur_score = quality_report.blur_score
        record.brightness_score = quality_report.brightness_score
        record.contrast_score = quality_report.contrast_score
        record.skew_angle = quality_report.skew_angle
        record.is_skewed = quality_report.is_skewed
        record.quality_passed = quality_report.passed
        record.width = quality_report.width
        record.height = quality_report.height
        record.noise_score = quality_report.noise_score
        record.resolution_passed = quality_report.resolution_passed

        subj_code = str(record.subject_id or "GENERAL")
        raw_name = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1] or "upload.bin"
        try:
            raw_url = storage.upload_subject_file(
                data=raw_bytes,
                subject_code=subj_code,
                academic_year="2025-2026",
                semester="SEM",
                category="answer-sheets",
                filename=f"RAW_{str(evaluation_id)[:8]}_{raw_name}",
            )
            record.raw_s3_url = raw_url
        except Exception as exc:
            logger.warning("Raw image storage upload failed for evaluation %s: %s", evaluation_id, exc)
            record.raw_s3_url = f"storage-fallback://original/{evaluation_id}/{raw_name}"

        ocr_pages = []
        confidences = []
        for idx, page_bytes in enumerate(pages_raw, start=1):
            try:
                image = image_processor.bytes_to_image(page_bytes)
                enhanced = image_processor.enhance_image(image)
                enhanced_bytes = image_processor.image_to_bytes(enhanced)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Enhancement failed on page %s of %s: %s", idx, evaluation_id, exc)
                enhanced_bytes = page_bytes  # fall back to raw page rather than dropping it

            try:
                enhanced_url = storage.upload_subject_file(
                    data=enhanced_bytes,
                    subject_code=subj_code,
                    academic_year="2025-2026",
                    semester="SEM",
                    category="answer-sheets",
                    filename=f"ANS_{subj_code}_STU_{str(evaluation_id)[:8]}_P{idx}.png",
                )
            except Exception as exc:
                logger.warning("Enhanced image storage upload failed on page %s of %s: %s", idx, evaluation_id, exc)
                enhanced_url = f"storage-fallback://enhanced/{evaluation_id}/{idx}.png"

            if idx == 1:
                record.enhanced_s3_url = enhanced_url

            try:
                ocr_page = ocr_engine.extract_page(enhanced_bytes, page_number=idx, evaluation_id=str(evaluation_id))
            except Exception as exc:
                logger.exception("OCR extraction exception for evaluation_id=%s page=%s: %s", evaluation_id, idx, exc)
                from app.schemas import OCRPage
                ocr_page = OCRPage(
                    page_number=idx,
                    transcript="",
                    structure_map={"error": str(exc)},
                    confidence=0.0,
                    visual_elements=[],
                )

            ocr_pages.append(ocr_page.model_dump())
            confidences.append(ocr_page.confidence)

        overall_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        # Requirement 3: Commit OCR results to the database immediately after OCR extraction
        record.ocr_data = {"pages": ocr_pages}
        record.overall_confidence = overall_confidence
        db = _commit_with_retry(db, record)
        logger.info("Durable OCR extraction results committed for evaluation %s", evaluation_id)

        # Storage transcript upload (wrapped in try/except)
        try:
            transcript = "\n\n".join(
                f"Page {page['page_number']}\n{page['transcript']}" for page in ocr_pages
            )
            record.transcript_s3_url = storage.upload_transcript(
                transcript.encode("utf-8"), str(evaluation_id)
            )
        except Exception as exc:
            logger.warning("Transcript upload failed for evaluation %s: %s", evaluation_id, exc)
            record.transcript_s3_url = f"storage-fallback://transcripts/{evaluation_id}/transcript.txt"

        # Requirement 4 & 5: Check normalized threshold & set status
        threshold = settings.normalized_ocr_threshold
        if not quality_report.passed:
            record.status = EvaluationStatus.NEEDS_REVIEW
            record.needs_manual_review = True
            record.error_message = "; ".join(quality_report.failure_reasons)
        elif overall_confidence < threshold:
            record.status = EvaluationStatus.NEEDS_REVIEW
            record.needs_manual_review = True
            msg = f"OCR confidence ({overall_confidence:.2f}) below threshold ({threshold:.2f})"
            record.error_message = f"{record.error_message}; {msg}" if record.error_message else msg
        else:
            record.status = EvaluationStatus.COMPLETED
            record.needs_manual_review = False

        db = _commit_with_retry(db, record)
        logger.info("Evaluation %s finished with status=%s confidence=%.2f",
                     evaluation_id, record.status, overall_confidence)

    except Exception as exc:  # noqa: BLE001 - last-resort guard so the record never hangs in PROCESSING
        logger.exception("Unhandled pipeline error for %s", evaluation_id)
        try:
            record = db.query(EvaluationRecord).filter_by(evaluation_id=evaluation_id).first()
            if record:
                _mark_failed(db, record, str(exc))
        except Exception:  # noqa: BLE001
            db.rollback()
    finally:
        try:
            db.close()
        except Exception:
            pass


def _mark_failed(db: Session, record: EvaluationRecord, reason: str) -> None:
    record.status = EvaluationStatus.FAILED
    record.error_message = reason
    record.needs_manual_review = True
    db = _commit_with_retry(db, record)
    logger.error("Evaluation %s marked FAILED: %s", record.evaluation_id, reason)
