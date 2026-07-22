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


def _pages_from_upload(raw_bytes: bytes, filename: str) -> List[bytes]:
    """
    Returns a list of per-page raw image bytes. PDFs are split into
    pages via pdf2image; single images are returned as a 1-page list.
    """
    if filename.lower().endswith(".pdf"):
        from pdf2image import convert_from_bytes
        pil_pages = convert_from_bytes(
            raw_bytes, dpi=300, first_page=1, last_page=settings.max_pdf_pages
        )
        pages = []
        for pil_img in pil_pages:
            import io
            buf = io.BytesIO()
            pil_img.save(buf, format="PNG")
            pages.append(buf.getvalue())
        return pages
    return [raw_bytes]


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
        # quality gate + record-level scores; all pages are still OCR'd
        # and stored below. (Splitting quality gating per-page is a
        # natural Phase 2 extension.)
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

        raw_name = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1] or "upload.bin"
        raw_url = storage.upload_image(raw_bytes, str(evaluation_id), "original", raw_name)
        record.raw_s3_url = raw_url

        if not quality_report.passed:
            record.status = EvaluationStatus.NEEDS_REVIEW
            record.needs_manual_review = True
            record.error_message = "; ".join(quality_report.failure_reasons)
            db.commit()
            logger.info("Evaluation %s failed quality gate: %s", evaluation_id, record.error_message)
            return

        ocr_pages = []
        confidences = []
        for idx, page_bytes in enumerate(pages_raw, start=1):
            try:
                image = image_processor.bytes_to_image(page_bytes)
                enhanced = image_processor.enhance_image(image)
                enhanced_bytes = image_processor.image_to_bytes(enhanced)
            except Exception as exc:  # noqa: BLE001
                logger.error("Enhancement failed on page %s of %s: %s", idx, evaluation_id, exc)
                enhanced_bytes = page_bytes  # fall back to raw page rather than dropping it

            enhanced_url = storage.upload_image(
                enhanced_bytes, str(evaluation_id), "enhanced", f"{idx}.png"
            )
            if idx == 1:
                record.enhanced_s3_url = enhanced_url

            ocr_page = ocr_engine.extract_page(enhanced_bytes, page_number=idx)
            ocr_pages.append(ocr_page.model_dump())
            confidences.append(ocr_page.confidence)

        overall_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        record.ocr_data = {"pages": ocr_pages}
        record.overall_confidence = overall_confidence
        transcript = "\n\n".join(
            f"Page {page['page_number']}\n{page['transcript']}" for page in ocr_pages
        )
        record.transcript_s3_url = storage.upload_transcript(
            transcript.encode("utf-8"), str(evaluation_id)
        )

        if overall_confidence < settings.ocr_confidence_threshold:
            record.status = EvaluationStatus.NEEDS_REVIEW
            record.needs_manual_review = True
        else:
            record.status = EvaluationStatus.COMPLETED
            record.needs_manual_review = False

        db.commit()
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
        db.close()


def _mark_failed(db: Session, record: EvaluationRecord, reason: str) -> None:
    record.status = EvaluationStatus.FAILED
    record.error_message = reason
    record.needs_manual_review = True
    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Could not persist FAILED status for %s", record.evaluation_id)
    logger.error("Evaluation %s marked FAILED: %s", record.evaluation_id, reason)
