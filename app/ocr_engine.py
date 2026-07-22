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
from typing import Any, Optional

from openai import OpenAI

from app.config import get_settings
from app.schemas import OCRPage, VisualElement

logger = logging.getLogger(__name__)
settings = get_settings()

openai_client = OpenAI(
    base_url=settings.qwen_api_base,
    api_key=settings.qwen_api_key or "not-needed",
    timeout=60.0,
    max_retries=2,
)

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


def _fallback_page(page_number: int, reason: str) -> tuple[OCRPage, str]:
    return OCRPage(
        page_number=page_number,
        transcript="",
        structure_map=None,
        confidence=0.0,
        visual_elements=[],
    ), reason


def extract_page(image_bytes: bytes, page_number: int) -> OCRPage:
    """
    Runs Qwen2.5-VL on a single enhanced page image and returns a
    structured OCRPage. On any parsing/API failure, returns a
    zero-confidence page rather than raising — the pipeline decides
    what to do with low confidence (flag for manual review), it should
    not crash the whole evaluation run over one bad page.
    """
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
        logger.error("Qwen2.5-VL call failed on page %s: %s", page_number, exc)
        page, _ = _fallback_page(page_number, str(exc))
        return page

    parsed = _safe_json_parse(raw)
    if parsed is None:
        logger.error("Qwen2.5-VL returned unparseable output on page %s", page_number)
        page, _ = _fallback_page(page_number, "unparseable_model_output")
        return page

    try:
        visual_elements = [VisualElement.model_validate(ve) for ve in parsed.get("visual_elements", [])]
        confidence = max(0.0, min(1.0, float(parsed.get("confidence", 0.0))))
        transcript = str(parsed.get("transcript", ""))
    except (TypeError, ValueError) as exc:
        logger.error("Invalid OCR schema on page %s: %s", page_number, exc)
        return _fallback_page(page_number, "invalid_model_schema")[0]

    return OCRPage(
        page_number=page_number,
        transcript=transcript,
        structure_map=parsed.get("structure_map"),
        confidence=confidence,
        visual_elements=visual_elements,
    )


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
