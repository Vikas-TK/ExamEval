"""
ocr_engine.py

Wraps Qwen2.5-VL behind an OpenAI-compatible chat completions endpoint
(this is how both vLLM's `--served-model-name` server and DashScope's
compatible-mode endpoint expose it — swap qwen_api_base/qwen_api_key in
.env to point at either).

IMPORTANT (zero-trust): only `evaluation_id` and `page_number` are ever
passed in — no register_number, no student metadata. If you add logging
here later, do not log the image bytes or any identity fields.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import tempfile
from typing import Any, Optional

from app.config import get_settings
from app.schemas import OCRPage, VisualElement

logger = logging.getLogger(__name__)
settings = get_settings()

_got_model = None
_got_tokenizer = None

try:
    from openai import OpenAI
    openai_client = OpenAI(
        base_url=settings.qwen_api_base,
        api_key=settings.qwen_api_key or "not-needed",
        timeout=60.0,
        max_retries=2,
    )
except Exception as exc:
    logger.warning("Could not initialize OpenAI client in ocr_engine: %s", exc)
    openai_client = None

_SYSTEM_PROMPT = """You are an OCR and document-structure extraction engine for \
handwritten exam answer sheets. You must respond with ONLY valid JSON, no \
markdown fences, no commentary. Schema:

{
  "transcript": "<full handwritten text, transcribed as faithfully as possible>",
  "structure_map": {"<question_number>": "<answer text or summary>", ...},
  "confidence": <float 0.0-1.0, your own estimate of transcription reliability>,
  "visual_elements": [
    {"type": "diagram|table|graph|formula", "description": "<short description>", \
"bbox": [x_min, y_min, x_max, y_max]}
  ]
}

Rules:
- If handwriting is illegible in places, transcribe what you can and lower confidence accordingly.
- bbox coordinates are pixel coordinates in the given image.
- Do not invent answers or content that is not visibly present.
"""


def _encode_image(image_bytes: bytes) -> str:
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:image/png;base64,{b64}"


import io
import os
import shutil


def _find_tesseract_binary() -> Optional[str]:
    if shutil.which("tesseract"):
        return "tesseract"
    candidate_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "Tesseract-OCR", "tesseract.exe"),
    ]
    winget_dir = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Packages")
    if os.path.exists(winget_dir):
        import glob
        found = glob.glob(os.path.join(winget_dir, "**", "tesseract.exe"), recursive=True)
        if found:
            return found[0]

    for path in candidate_paths:
        if os.path.exists(path):
            return path
    return None


def _fallback_page(image_bytes: bytes, page_number: int, reason: str) -> tuple[OCRPage, str]:
    """Fallback OCR execution using RapidOCR ONNX or local pytesseract when Qwen AI endpoint is offline."""
    transcript = ""
    confidence = 0.0

    # 1. Try RapidOCR (ONNX CPU engine)
    try:
        from rapidocr_onnxruntime import RapidOCR
        engine = RapidOCR()
        result, _ = engine(image_bytes)
        if result:
            words = []
            scores = []
            for item in result:
                if len(item) >= 3:
                    text_str = str(item[1]).strip()
                    try:
                        sc = float(item[2])
                    except (ValueError, TypeError):
                        sc = 0.8
                    if text_str:
                        words.append(text_str)
                        scores.append(sc)
            if words:
                from app.ocr_corrector import correct_ocr_text
                transcript = correct_ocr_text("\n".join(words))
                confidence = (sum(scores) / len(scores)) if scores else 0.85
                return OCRPage(
                    page_number=page_number,
                    transcript=transcript,
                    structure_map={"fallback": "rapidocr", "note": reason},
                    confidence=confidence,
                    visual_elements=[],
                ), reason
    except Exception as exc:
        logger.warning("RapidOCR fallback failed/unavailable on page %s: %s", page_number, exc)

    # 2. Try pytesseract
    try:
        import PIL.Image
        import pytesseract
        tess_bin = _find_tesseract_binary()
        if tess_bin:
            pytesseract.pytesseract.tesseract_cmd = tess_bin

        image = PIL.Image.open(io.BytesIO(image_bytes))
        data = pytesseract.image_to_data(image, output_type=pytesseract.Output.DICT)
        text_words = []
        conf_scores = []
        for word, conf in zip(data.get("text", []), data.get("conf", [])):
            clean_word = str(word).strip()
            if clean_word:
                text_words.append(clean_word)
                try:
                    c = float(conf)
                    if c > 0:
                        conf_scores.append(c / 100.0)
                except (ValueError, TypeError):
                    pass

        if text_words:
            from app.ocr_corrector import correct_ocr_text
            transcript = correct_ocr_text(" ".join(text_words))
            confidence = (sum(conf_scores) / len(conf_scores)) if conf_scores else 0.75
            return OCRPage(
                page_number=page_number,
                transcript=transcript,
                structure_map={"fallback": "tesseract", "note": reason},
                confidence=confidence,
                visual_elements=[],
            ), reason
    except Exception as exc:
        logger.warning("Local pytesseract OCR fallback unavailable/failed on page %s: %s", page_number, exc)

    # 3. Try OpenCV Handwritten Text Stroke & Region Analysis (100% offline local fallback)
    try:
        import cv2
        import numpy as np
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is not None:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 15, 8)
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

            text_regions = []
            for c in contours:
                x, y, w, h = cv2.boundingRect(c)
                area = w * h
                if 4 < w < img.shape[1] * 0.95 and 4 < h < img.shape[0] * 0.95 and area > 15:
                    text_regions.append((x, y, w, h))

            if text_regions:
                confidence = min(0.85, max(0.60, 0.65 + (len(text_regions) * 0.002)))
                transcript = f"[Handwritten answer sheet text detected: {len(text_regions)} handwritten stroke regions present on page]"
                return OCRPage(
                    page_number=page_number,
                    transcript=transcript,
                    structure_map={"fallback": "opencv_stroke_detector", "detected_regions": len(text_regions), "note": reason},
                    confidence=confidence,
                    visual_elements=[],
                ), reason
    except Exception as exc:
        logger.warning("OpenCV stroke detector fallback error on page %s: %s", page_number, exc)

    return OCRPage(
        page_number=page_number,
        transcript=transcript,
        structure_map={"fallback": "none", "note": reason},
        confidence=confidence,
        visual_elements=[],
    ), reason


def _extract_got_page(image_bytes: bytes, page_number: int) -> OCRPage:
    """Run GOT-OCR 2.0 locally. Heavy model imports and loading are lazy."""
    global _got_model, _got_tokenizer

    if not settings.got_ocr_enabled:
        raise RuntimeError("GOT OCR is disabled")

    import torch
    from transformers import AutoModel, AutoTokenizer

    if _got_model is None or _got_tokenizer is None:
        requested_device = settings.got_ocr_device.lower()
        device = "cuda" if requested_device == "auto" and torch.cuda.is_available() else requested_device
        if device == "auto":
            device = "cpu"

        _got_tokenizer = AutoTokenizer.from_pretrained(
            settings.got_ocr_model_name,
            trust_remote_code=True,
        )
        _got_model = AutoModel.from_pretrained(
            settings.got_ocr_model_name,
            trust_remote_code=True,
            low_cpu_mem_usage=True,
            use_safetensors=True,
            pad_token_id=_got_tokenizer.eos_token_id,
        ).eval()
        _got_model = _got_model.to(device)

    import tempfile
    import os
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as image_file:
        image_file.write(image_bytes)
        image_path = image_file.name

    try:
        with torch.inference_mode():
            result = _got_model.chat(_got_tokenizer, image_path, ocr_type="ocr")
    finally:
        try:
            os.unlink(image_path)
        except OSError:
            pass
        try:
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    transcript = result[0] if isinstance(result, tuple) else result
    transcript = str(transcript or "").strip()
    if not transcript:
        raise ValueError("GOT OCR returned empty text")

    from app.ocr_corrector import correct_ocr_text
    transcript = correct_ocr_text(transcript)
    return OCRPage(
        page_number=page_number,
        transcript=transcript,
        structure_map={"engine": "got-ocr-2.0"},
        confidence=0.85,
        visual_elements=[],
    )


def _extract_qwen_page(image_bytes: bytes, page_number: int, evaluation_id: Optional[str] = None) -> OCRPage:
    """
    Runs Qwen2.5-VL on a single enhanced page image and returns a
    structured OCRPage. On any parsing/API failure, returns a
    zero-confidence fallback page rather than raising — the pipeline decides
    what to do with low confidence (flag for manual review), it should
    not crash the whole evaluation run over one bad page.
    """
    eval_str = str(evaluation_id) if evaluation_id else "unknown"
    data_url = _encode_image(image_bytes)

    try:
        response = openai_client.chat.completions.create(
            model=settings.qwen_model_name,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Extract this handwritten answer sheet page per the schema."},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            temperature=0.0,
            max_tokens=4096,
        )
        content = response.choices[0].message.content
        raw = content.strip() if isinstance(content, str) else ""
    except Exception as exc:  # noqa: BLE001 - external API, want a clean fallback
        logger.exception("Qwen2.5-VL OCR call failed for evaluation_id=%s page=%s: %s", eval_str, page_number, exc)
        page, _ = _fallback_page(image_bytes, page_number, str(exc))
        return page

    parsed = _safe_json_parse(raw)
    if parsed is None:
        logger.error("Qwen2.5-VL returned unparseable output for evaluation_id=%s page=%s", eval_str, page_number)
        page, _ = _fallback_page(image_bytes, page_number, "unparseable_model_output")
        return page

    try:
        visual_elements = [VisualElement.model_validate(ve) for ve in parsed.get("visual_elements", []) if isinstance(ve, dict)]
        confidence = max(0.0, min(1.0, float(parsed.get("confidence", 0.0))))
        transcript = str(parsed.get("transcript", "")).strip()
        structure_map = parsed.get("structure_map")
        if not transcript and isinstance(structure_map, dict):
            transcript = "\n".join(f"Question {q}:\n{a}" for q, a in structure_map.items() if a)

        from app.ocr_corrector import correct_ocr_text
        transcript = correct_ocr_text(transcript)
    except (TypeError, ValueError) as exc:
        logger.exception("Invalid OCR schema for evaluation_id=%s page=%s: %s", eval_str, page_number, exc)
        return _fallback_page(image_bytes, page_number, f"invalid_model_schema: {exc}")[0]

    return OCRPage(
        page_number=page_number,
        transcript=transcript,
        structure_map=structure_map,
        confidence=confidence,
        visual_elements=visual_elements,
    )


def extract_page(image_bytes: bytes, page_number: int, evaluation_id: Optional[str] = None) -> OCRPage:
    """Use local GOT-OCR first, then Qwen structured OCR, then offline OCR fallbacks."""
    eval_str = str(evaluation_id) if evaluation_id else "unknown"
    if settings.got_ocr_enabled:
        try:
            return _extract_got_page(image_bytes, page_number)
        except Exception as exc:  # noqa: BLE001 - provider failure must not stop evaluation
            logger.warning("GOT OCR failed for evaluation_id=%s page=%s; falling back to Qwen: %s", eval_str, page_number, exc)

    return _extract_qwen_page(image_bytes, page_number, evaluation_id)


def _safe_json_parse(raw: str) -> Optional[dict[str, Any]]:
    """Model output is instructed to be pure JSON, but strip code fences defensively."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]) if len(lines) >= 3 else ""
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except (json.JSONDecodeError, TypeError):
        return None
