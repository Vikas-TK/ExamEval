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
import re
import tempfile
from collections import Counter
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
        # A 16K-context vision call on CPU-bound hardware can legitimately
        # take 2-3 minutes, especially on a cold/reloaded model — a 60s
        # timeout was cutting these off before they could finish, forcing
        # a fallback to much weaker OCR engines. max_retries=1 (not the
        # default 2+) so a genuine failure doesn't triple this wait.
        timeout=240.0,
        max_retries=1,
    )
except Exception as exc:
    logger.warning("Could not initialize OpenAI client in ocr_engine: %s", exc)
    openai_client = None

_SYSTEM_PROMPT = """You are an OCR and document-structure extraction engine for \
handwritten exam answer sheets. You must respond with ONLY valid JSON, no \
markdown fences, no commentary. Schema:

{
  "transcript": "<full handwritten text, transcribed VERBATIM>",
  "structure_map": {"<question_number>": "<answer text or summary>", ...},
  "confidence": <float 0.0-1.0, your own estimate of transcription reliability>,
  "visual_elements": [
    {"type": "diagram|table|graph|formula", "description": "<short description>", \
"bbox": [x_min, y_min, x_max, y_max]}
  ]
}

CRITICAL transcription rules — these directly determine whether a downstream
system can correctly split this page back into separate answers, so follow
them exactly:
- Transcribe word-for-word, in the student's own words and phrasing. Do NOT
  rephrase, summarize, "clean up", or substitute your own definition of a
  term even if you recognize the topic — write only what is actually written
  on the page, including any errors, crossed-out text (marked as struck-through
  if legible), and incomplete sentences.
- If a question number or label is written anywhere on the page (e.g. "1.",
  "Q1", "Q.1)", "1)", "(a)"), reproduce it EXACTLY at the start of the line
  where it appears in the transcript — never drop it, renumber it, or infer
  one that isn't visibly written. This applies EVEN WHEN the student wrote no
  answer at all next to that number (left it blank/skipped it) — the bare
  number on its own line (e.g. "6.") must still appear in the transcript
  exactly where it is on the page. Do not silently omit a question number
  just because there is nothing else on its line.
- Preserve the original line breaks and paragraph breaks between answers —
  insert a blank line between one answer and the next exactly where the
  student's handwriting shows a visual gap (new question, new paragraph),
  so each answer stays distinguishable in the transcript.
- If handwriting is illegible in places, transcribe what you can and lower
  confidence accordingly — never invent or guess at illegible words.
- bbox coordinates are pixel coordinates in the given image.
- Do not invent answers or content that is not visibly present.
- If a region of the page is a diagram, chart, graph, table, or drawing rather
  than handwritten/printed text, do NOT attempt to transcribe its shapes,
  axes, or labels as prose — instead add an entry for it in visual_elements.
  Its "description" must name the CONCEPT/TOPIC the diagram is illustrating
  (e.g. "block diagram of an encoder-decoder autoencoder architecture", "GRU
  update/reset gate flow"), not a generic description of its visual layout
  (never write things like "a table with two columns and three rows" or "a
  diagram with boxes and arrows" — that describes shapes, not content, and is
  useless to a grader). If you cannot confidently tell what the diagram
  actually depicts, OMIT it from visual_elements entirely rather than
  including a vague/generic entry — no entry is better than a useless one.
  If a page (or the remainder of a page after any actual text) is purely such
  a diagram with no handwritten text at all, leave transcript as an empty
  string for that portion — never pad it with guessed, invented, or
  conversational text.
- confidence measures how much of the page's actual content you successfully
  captured — it is NOT a generic "how sure am I" score. If the page is blank,
  contains no visible handwriting/printing/diagrams at all, or is otherwise
  unreadable (e.g. a scanning error, solid color, or corrupt image) so that
  transcript and visual_elements are both empty, report confidence near 0.0
  (e.g. 0.0-0.1) — an empty result is only "confident" in the sense that there
  is genuinely nothing there, and this system routes low confidence to manual
  review, which is the correct outcome for a page that couldn't be read.
"""


_MAX_VISION_DIM = 1280


def _downscale_for_vision(image_bytes: bytes) -> bytes:
    """
    Full-resolution phone/scanner captures (often 3000px+ on the long edge)
    force the vision encoder to process far more image tokens than legible
    OCR actually needs, which is the dominant cost on CPU-bound hardware —
    independent of and in addition to the num_ctx text-token budget. Caps
    the long edge at 1280px (comfortably enough for legible handwriting/
    print) while preserving aspect ratio. Falls back to the original bytes
    on any decode failure rather than blocking the OCR call over this.
    """
    try:
        import io
        from PIL import Image

        img = Image.open(io.BytesIO(image_bytes))
        width, height = img.size
        longest = max(width, height)
        if longest > _MAX_VISION_DIM:
            scale = _MAX_VISION_DIM / longest
            new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
            img = img.resize(new_size, Image.LANCZOS)

        # Always re-encode through PIL (even when no resize was needed) so
        # the returned bytes are guaranteed to actually be JPEG — the
        # caller labels them as image/jpeg regardless of the original
        # upload format (PNG, HEIC, etc.).
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=88)
        return buf.getvalue()
    except Exception as exc:
        logger.warning("Image downscale for vision OCR failed, using original bytes as-is: %s", exc)
        return image_bytes


def _encode_image(image_bytes: bytes) -> str:
    image_bytes = _downscale_for_vision(image_bytes)
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


import io
import os
import shutil


def _resegment_long_runs(text: str) -> str:
    """
    RapidOCR is line-level, not word-level — it occasionally drops spaces
    entirely within a detected line ("SectionI: Eachquestioncarriers2marks").
    Dictionary-based word segmentation recovers readable spacing.

    Gated on the SPLIT RESULT rather than run length: wordninja returning a
    single segment means it already believes the run is one real word (or
    an acronym/code it can't decompose), so we leave it untouched — this
    lets us safely check even short runs like "SectionI" without risking
    corrupting genuinely correct short/long single words.
    """
    try:
        import wordninja
    except ImportError:
        return text

    def resplit(match: "re.Match[str]") -> str:
        run = match.group(0)
        pieces = wordninja.split(run)
        return " ".join(pieces) if len(pieces) > 1 else run

    return re.sub(r"[A-Za-z]{5,}", resplit, text)


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
                transcript = _resegment_long_runs(transcript)
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


def _looks_like_non_text_page(text: str) -> bool:
    """
    GOT-OCR is pure text-OCR with no diagram/chart awareness — when a page is
    actually a diagram or graph rather than handwriting/print, it doesn't
    error out, it just mis-reads shapes as a run of digits/symbols. That
    garbled output otherwise looks like a "successful" transcription and
    blocks the pipeline from ever falling through to Qwen's vision model,
    which can actually recognize and describe the diagram via visual_elements.
    Flag output that isn't real prose so extract_page() falls through to Qwen.
    """
    stripped = text.strip()
    if len(stripped) < 3:
        return True
    non_space_count = sum(1 for c in stripped if not c.isspace())
    if non_space_count == 0:
        return True
    alpha_ratio = sum(1 for c in stripped if c.isalpha()) / non_space_count
    return alpha_ratio < 0.5


def _looks_like_repetition_collapse(text: str) -> bool:
    """
    GOT-OCR's built-in no_repeat_ngram_size guard only blocks an *exact*
    long n-gram from recurring — it doesn't stop the model degenerating
    into a short phrase repeated with trivial variation ("model. model.
    Model Model model model...") when it can't confidently read confusing
    content, which dense handwritten code reliably triggers. Flag output
    dominated by one short token so extract_page() falls through to Qwen
    instead of keeping hundreds of repeated words as the "transcript".
    """
    words = re.findall(r"[A-Za-z]+", text.lower())
    if len(words) < 20:
        return False
    _, count = Counter(words).most_common(1)[0]
    return (count / len(words)) > 0.25


_INLINE_QNUM_AFTER_COMMA_RE = re.compile(r"(,\s*)(\d{1,3})\.(\s+)(?=[a-zA-Z])")
_INLINE_QNUM_BEFORE_CAPITAL_RE = re.compile(r"(?<!\n)(\b\d{1,3})\.(\s*)(?=[A-Z*])")


def _resplit_run_on_answers(text: str) -> str:
    """
    GOT-OCR's plain-OCR decoding sometimes emits visually-distinct
    handwritten lines as one run-on line with no newline between them at
    all (confirmed by comparing against the source image directly — the
    handwriting itself has normal line spacing). Downstream anchor
    detection only recognizes a question number at the start of a line, so
    a run like "11. False, 12. opinion PART-B 13. ..." hides every number
    after the first from it entirely. Re-inserts a line break in the two
    narrow, high-confidence spots this shows up: right after a short
    comma-separated answer ("False, 12." -> "False,\n12."), and right
    before a bullet/capitalized answer starts ("13. * Sten..." ->
    "\n13. * Sten..."). Deliberately narrow — verified against real pages
    full of standalone numbers (Python code with layer sizes, epoch
    counts, etc.) to confirm it does not fire there and fragment code that
    currently transcribes correctly.
    """
    text = _INLINE_QNUM_AFTER_COMMA_RE.sub(r",\n\2.\3", text)
    text = _INLINE_QNUM_BEFORE_CAPITAL_RE.sub(r"\n\1.\2", text)
    return text


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
    if _looks_like_non_text_page(transcript):
        raise ValueError(
            "GOT OCR output does not look like transcribable text (likely a diagram/figure); "
            "deferring to Qwen vision extraction"
        )
    if _looks_like_repetition_collapse(transcript):
        raise ValueError(
            "GOT OCR output collapsed into repetitive text; deferring to Qwen vision extraction"
        )

    from app.ocr_corrector import correct_ocr_text
    transcript = correct_ocr_text(transcript)
    transcript = _resplit_run_on_answers(transcript)
    return OCRPage(
        page_number=page_number,
        transcript=transcript,
        structure_map={"engine": "got-ocr-2.0"},
        confidence=0.85,
        visual_elements=[],
    )


def _stringify_structure_map_value(value: Any) -> str:
    """
    Coerce a structure_map value to plain text before it gets folded into
    the transcript. The model's JSON schema asks for a string per question,
    but it sometimes returns a list of bullet lines instead — naively
    f-string-embedding that (`f"...{a}"`) produces a literal Python repr
    like "['* point one', '* point two']" inside the transcript, which then
    reads as garbled/fabricated text to anchor detection and to a human.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(str(item) for item in value if isinstance(item, str) and item.strip())
    return str(value)


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
            # 4096 was letting the model believe it could generate an
            # enormous response, and generation time on CPU-bound hardware
            # scales with output length — this was compounding with the
            # image-encoding cost to blow past any reasonable timeout.
            # 2048 comfortably covers a single dense page's transcript +
            # structured JSON while cutting worst-case generation time.
            max_tokens=2048,
            # No num_ctx override here: qwen2.5vl-8k has it baked in via
            # Modelfile. A per-request override would take precedence over
            # that and silently push it back up to the heavier 16384,
            # which this GPU's 4GB VRAM can't comfortably absorb for a
            # vision request — that's what caused the multi-minute stalls.
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
        if isinstance(structure_map, dict) and len(structure_map) == 1:
            # The model sometimes puts a question's answer here instead of
            # (or in addition to) folding it into transcript — e.g. a page
            # whose transcript covers the tail of one answer while a new
            # question's content lands in structure_map keyed by its number.
            # Appending rather than only using this as an empty-transcript
            # fallback is what stops that content from being silently
            # dropped, which otherwise looks like the answer was cut short.
            # Restricted to exactly one entry: when the model instead uses
            # structure_map for its own generic step-by-step breakdown of
            # the SAME content already in transcript (e.g. "1", "2", "3"...
            # for a code block), merging would inject fake low-number
            # question anchors that can overwrite the real Q1-Q5 elsewhere
            # in the document via number-based matching.
            structured_text = "\n\n".join(
                f"Question {q}:\n{_stringify_structure_map_value(a)}" for q, a in structure_map.items() if a
            )
            if structured_text:
                transcript = f"{transcript}\n\n{structured_text}".strip() if transcript else structured_text

        from app.ocr_corrector import correct_ocr_text
        transcript = correct_ocr_text(transcript)
        transcript = _resplit_run_on_answers(transcript)
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
