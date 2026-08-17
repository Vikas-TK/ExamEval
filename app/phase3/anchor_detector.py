"""
Phase 3 – Question Anchor Detector

Step 2: Detect question anchors from student OCR text.
Primary detection uses compiled regex patterns.
Fallback invokes Qwen2.5-3B via the local Ollama endpoint when confidence is low.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any

from app.core.config import get_settings
from app.phase3.schemas import QuestionAnchor

logger = logging.getLogger(__name__)
settings = get_settings()

# ─── Anchor Pattern Registry ──────────────────────────────────────────────────
#  Ordered from most explicit → least explicit.
#  Each tuple: (pattern, normalized_prefix, base_confidence)
_ANCHOR_PATTERNS: list[tuple[re.Pattern[str], float]] = [
    # 1. "Q1", "Q.1", "Q 1", "Question 1", "Ans 1", "Answer 1", "Ans. 1", "Q.13", "Q13"
    (re.compile(r"(?i)(?:^|\n)\s*(?:Q(?:uestion)?|Ans(?:wer)?)\.?\s*(\d{1,3}[a-z]?)\b", re.M), 0.95),
    # 2. Standalone line-start numbering: "1.", "1)", "1:", "1 -", "13.", "18.", "18.1"
    (re.compile(r"(?:^|\n)\s*(\d{1,3}(?:\.\d{1,2})?[a-z]?)\s*[\.\):\-\s]\s*", re.M), 0.90),
    # 3. Parenthesized top-level numbering: "(19)", "(16)" — some long-answer
    #    headings get transcribed with the digit wrapped in parens instead of
    #    followed by "." or ")"; Pattern 2 can't match this shape at all
    #    since it requires the digit first, not wrapped.
    (re.compile(r"(?:^|\n)\s*\((\d{1,3})\)\s*", re.M), 0.90),
    # 4. Compound top-level "OR"-alternative numbering: "19(a)", "13(b)" — an
    #    "answer 19(a) OR 19(b)" style choice question in its own right, not
    #    a bare sub-part of a preceding question, so the whole thing (digit
    #    + choice letter) must be captured as one anchor. Must come before
    #    Pattern 5 below: without this, "19(a)" only matches Pattern 5's
    #    bare "(a)", losing the "19" and leaving a dangling lettered anchor
    #    that has nothing real to be a sub-part of.
    (re.compile(r"(?:^|\n)\s*(\d{1,3}\s*\([a-z]\))\s+", re.M | re.I), 0.90),
    # 5. Sub-questions: (a), (b), (i), (ii)
    (re.compile(r"(?:^|\n)\s*(?:\d{1,3}\s*)?\(([a-z]|[ivx]+)\)\s+", re.M | re.I), 0.85),
    # 6. Part A / Section A — accepts a hyphen or colon between the word and
    #    the letter too ("Part-D", "Part: A"), not just whitespace, since
    #    handwritten/OCR'd headers commonly use a hyphen there. This match
    #    is what lets _apply_sequence_guard reset its per-section numbering
    #    floor; missing it silently breaks every later Part's real anchors
    #    whenever a student answers sections out of increasing order.
    (re.compile(r"(?i)(?:^|\n)\s*(Part\s*[-:]?\s*[A-Z]|Section\s*[-:]?\s*[A-Z])\b", re.M), 0.80),
]

# Noise patterns — anchors matching these are discarded
_NOISE_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"\bRoll\s*No\b", re.I),
    re.compile(r"\bReg(?:istration)?\s*No\b", re.I),
    re.compile(r"\bPage\s*\d+\b", re.I),
    re.compile(r"\bDate\b.*\d{2}[/-]\d{2}", re.I),
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),  # ISO date
    re.compile(r"\bMarks?\s*[:=]\s*\d+\b", re.I),
]

_LOW_CONFIDENCE_THRESHOLD = 0.85

# A bare numeric anchor ("13", "13a", "18.1", "19(a)") — used to tell a real
# top-level question number apart from a sub-numbered continuation of the
# one just accepted (group 2 = decimal sub-part, group 3 = trailing letter
# sub-part, group 4 = parenthesized "OR"-alternative choice letter).
_NUMERIC_LABEL_RE = re.compile(r"^(\d{1,3})(?:\.(\d{1,2})|([a-z])|\s*\(([a-z])\))?$", re.I)
# A bare letter/roman sub-part label ("a", "ii") with no digits at all.
_ROMAN_OR_LETTER_RE = re.compile(r"^[a-z]{1,4}$", re.I)
# How close (in characters) a lettered/roman sub-part must sit to the anchor
# it belongs to before it's trusted — a real "13(a)", "13(b)" pair appears
# together at the top of that answer; a "(i)", "(ii)" bullet list deep inside
# a multi-page essay does not.
_SUBPART_PROXIMITY_CHARS = 500


def _is_noise(text: str) -> bool:
    return any(p.search(text) for p in _NOISE_PATTERNS)


def _normalize_label(raw: str) -> str:
    """Normalise detected anchor to a canonical Q-prefixed label (e.g. Q13, Q14)."""
    stripped = raw.strip().upper()
    stripped = re.sub(r"^[.\s:;\-\)]+", "", stripped)
    stripped = re.sub(r"[.\s:;\-]+$", "", stripped)
    if re.match(r"^Q\d+([A-Z]|\([A-Z0-9]+\))?$", stripped):
        return stripped
    stripped = re.sub(r"^(?:Q(?:UESTION)?|ANS(?:WER)?)\.?\s*", "", stripped).strip()
    stripped = re.sub(r"(\d+)\s*\(\s*([A-Z0-9]+)\s*\)", r"\1(\2)", stripped)
    if stripped.endswith(")") and "(" not in stripped:
        stripped = stripped[:-1].strip()

    if re.match(r"^\d+([A-Z]|\([A-Z0-9]+\))?$", stripped):
        return f"Q{stripped}"

    if stripped.isdigit():
        return f"Q{stripped}"

    if re.match(r"^(PART|SECTION)\s*[-:]?\s*[A-Z]", stripped):
        return stripped

    return f"Q{stripped}" if len(stripped) <= 3 and not stripped.startswith("Q") else stripped


def _regex_detect(flat_text: str, page_map: list[tuple[int, int, int]]) -> list[QuestionAnchor]:
    """
    Run all anchor regex patterns over flat_text and return deduplicated anchors.
    page_map: list of (char_start, char_end, page_number) per page.
    """
    anchors: list[QuestionAnchor] = []
    seen_offsets: set[int] = set()

    def page_for_offset(offset: int) -> int:
        for start, end, pg in page_map:
            if start <= offset < end:
                return pg
        return 1

    for pattern, base_conf in _ANCHOR_PATTERNS:
        for match in pattern.finditer(flat_text):
            offset = match.start()
            context = flat_text[max(0, offset - 20): offset + len(match.group()) + 30]
            if _is_noise(context):
                continue
            if offset in seen_offsets:
                continue
            seen_offsets.add(offset)
            target = match.group(1) if match.groups() and match.group(1) else match.group()
            raw_label = target.strip()
            anchors.append(QuestionAnchor(
                raw_label=raw_label,
                normalized=_normalize_label(raw_label),
                char_offset=offset,
                page_number=page_for_offset(offset),
                confidence=base_conf,
                detection_method="regex",
            ))

    anchors.sort(key=lambda a: a.char_offset)
    return _apply_sequence_guard(anchors)


def _apply_sequence_guard(anchors: list[QuestionAnchor]) -> list[QuestionAnchor]:
    """
    Reject standalone-number and lettered-subpart anchors that are almost
    certainly internal list/step markers inside a long essay answer rather
    than real question boundaries — e.g. a Q13 essay's own "1. Take input...",
    "2. Separate frames..." working-process list, misread as fresh Q1/Q2
    anchors that collide with the real (much earlier) Part-A Q1/Q2.

    Kept deliberately simple: exam question numbers only go up within a
    section, so any bare numeric anchor that is NOT higher than the highest
    one already accepted in the current section is almost always an internal
    list marker, not a new question — except a sub-numbered continuation of
    the number just accepted ("18.1", "18.2", "13a", "13b"), which is kept if
    it sits close to its parent. Lettered/roman sub-parts ("(a)", "(ii)") are
    only trusted close to the anchor they immediately follow for the same
    reason. Explicit "Q13"/"Question 13" style anchors are numeric-shaped
    too and go through the same check — deliberately, since an in-answer
    reference like that is rare and treating it uniformly avoids needing to
    track which regex pattern produced each anchor.
    """
    accepted: list[QuestionAnchor] = []
    section_max_num = 0
    last_accepted_offset = -10 ** 9

    for anchor in anchors:
        norm = (anchor.normalized or "").upper()
        label = anchor.raw_label.strip()

        if norm.startswith("PART") or norm.startswith("SECTION"):
            accepted.append(anchor)
            section_max_num = 0
            last_accepted_offset = anchor.char_offset
            continue

        numeric_match = _NUMERIC_LABEL_RE.match(label)
        if numeric_match:
            num = int(numeric_match.group(1))
            has_subpart = bool(numeric_match.group(2)) or bool(numeric_match.group(3))
            # A parenthesized "OR"-choice letter ("19(a)", "19(b)") is a
            # top-level anchor in its own right, not a continuation of an
            # already-open number — it's accepted like a fresh top-level
            # number (group 4 set, num == section_max_num covers the second
            # alternative appearing after the first was already accepted).
            is_choice_form = bool(numeric_match.group(4))
            close_enough = (anchor.char_offset - last_accepted_offset) <= _SUBPART_PROXIMITY_CHARS
            if has_subpart and num == section_max_num and close_enough:
                accepted.append(anchor)
                last_accepted_offset = anchor.char_offset
            elif not has_subpart and (
                section_max_num == 0
                or num > section_max_num
                or (is_choice_form and num == section_max_num)
            ):
                accepted.append(anchor)
                section_max_num = num
                last_accepted_offset = anchor.char_offset
            # else: internal list/step marker inside the current answer — drop it
            continue

        if _ROMAN_OR_LETTER_RE.match(label):
            if (anchor.char_offset - last_accepted_offset) <= _SUBPART_PROXIMITY_CHARS:
                accepted.append(anchor)
                last_accepted_offset = anchor.char_offset
            # else: bullet/list marker far from any real anchor — drop it
            continue

        # Anything else (shouldn't normally occur) — keep as-is.
        accepted.append(anchor)

    return accepted


def looks_like_new_question(text: str, current_max_num: int) -> tuple[bool, int]:
    """
    Best-effort check for whether `text` (a paragraph's own opening line)
    looks like a genuine new question boundary rather than a continuation of
    the answer it was found inside — reusing the same anchor patterns and
    monotonic-sequence philosophy as detect_anchors()/_apply_sequence_guard().

    Used by the segmenter to decide whether a paragraph break inside an
    already-anchored answer block is a real missed question (rare) or just a
    section heading / numbered step within one long multi-page answer (the
    common case for high-mark descriptive questions).

    Returns (is_new_question, updated_max_num) — updated_max_num is
    unchanged from current_max_num when is_new_question is False, so callers
    can thread it through consecutive paragraphs in one pass.
    """
    probe = "\n" + text.lstrip("\n")
    for pattern, _ in _ANCHOR_PATTERNS[:5]:  # numeric/Q-prefixed/paren-numeric/choice-form/sub-part only — not Part/Section
        m = pattern.match(probe)
        if not m:
            continue
        target = m.group(1) if m.groups() and m.group(1) else m.group()
        label = target.strip()
        if _is_noise(probe[: len(m.group()) + 30]):
            continue

        numeric_match = _NUMERIC_LABEL_RE.match(label)
        if numeric_match:
            num = int(numeric_match.group(1))
            has_subpart = bool(numeric_match.group(2)) or bool(numeric_match.group(3))
            is_choice_form = bool(numeric_match.group(4))
            if has_subpart:
                return False, current_max_num
            if current_max_num == 0 or num > current_max_num or (is_choice_form and num == current_max_num):
                return True, num
            return False, current_max_num

        if _ROMAN_OR_LETTER_RE.match(label):
            # No cheap proximity signal once already inside one long
            # block's paragraph stream — treat as a continuation.
            return False, current_max_num

    return False, current_max_num


def _llm_fallback_detect(flat_text: str) -> list[QuestionAnchor]:
    """Call Qwen2.5-3B via local Ollama to detect ambiguous anchors."""
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=settings.qwen_api_key,
            base_url=settings.qwen_api_base,
            timeout=30.0,
            max_retries=1,
        )
        system = (
            "You are a question anchor detector. Given OCR text from a student answer script, "
            "identify every question number/label in order. Ignore roll numbers, dates, marks, page numbers. "
            "Return ONLY a JSON array of strings, e.g. [\"Q1\",\"Q2\",\"Part A\"]."
        )
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": flat_text[:4000]},
            ],
            temperature=0.0,
            max_tokens=512,
        )
        raw = response.choices[0].message.content or "[]"
        if raw.startswith("```"):
            raw = "\n".join(raw.splitlines()[1:-1])
        labels: list[str] = json.loads(raw)
        anchors: list[QuestionAnchor] = []
        for label in labels:
            if not label.strip():
                continue
            offset = flat_text.find(label)
            anchors.append(QuestionAnchor(
                raw_label=label,
                normalized=_normalize_label(label),
                char_offset=max(offset, 0),
                page_number=1,
                confidence=0.70,
                detection_method="llm_fallback",
            ))
        return anchors
    except Exception as exc:
        logger.warning("LLM anchor fallback failed: %s", exc)
        return []


def detect_anchors(
    ocr_data: dict[str, Any],
) -> tuple[str, list[tuple[int, int, int]], list[QuestionAnchor]]:
    """
    Main anchor detection entry point.

    Args:
        ocr_data: OCR JSON {"pages": [{"page_number": int, "transcript": str, "visual_elements": [...]}]}

    Returns:
        (flat_text, page_map, anchors)
        flat_text: concatenated transcript across all pages
        page_map: list of (char_start, char_end, page_number)
        anchors: detected & sorted question anchors
    """
    pages: list[dict[str, Any]] = ocr_data.get("pages", [])
    segments: list[str] = []
    page_map: list[tuple[int, int, int]] = []
    cursor = 0

    for page in pages:
        pg_num = page.get("page_number", 1)
        text = str(page.get("transcript", ""))
        start = cursor
        segments.append(text)
        cursor += len(text) + 1  # +1 for separator newline
        page_map.append((start, cursor, pg_num))

    flat_text = "\n".join(segments)

    anchors = _regex_detect(flat_text, page_map)

    # Determine average confidence
    avg_conf = (sum(a.confidence for a in anchors) / len(anchors)) if anchors else 0.0

    if not anchors or avg_conf < _LOW_CONFIDENCE_THRESHOLD:
        logger.info("Anchor confidence low (%.2f); invoking LLM fallback.", avg_conf)
        llm_anchors = _llm_fallback_detect(flat_text)
        if llm_anchors:
            # Merge: prefer regex results, supplement with LLM labels not already found
            existing_labels = {a.normalized for a in anchors}
            for la in llm_anchors:
                if la.normalized not in existing_labels:
                    anchors.append(la)
                    existing_labels.add(la.normalized)
            anchors.sort(key=lambda a: a.char_offset)

    if not anchors:
        logger.info("No labeled anchors found at all; falling back to paragraph-boundary segmentation.")
        anchors = _paragraph_fallback_detect(flat_text)

    logger.info("Detected %d question anchors (avg_conf=%.2f).", len(anchors), avg_conf)
    return flat_text, page_map, anchors


def _paragraph_fallback_detect(flat_text: str) -> list[QuestionAnchor]:
    """
    Last-resort segmentation when neither regex nor the LLM found any
    question-number labels in the transcript (e.g. the model paraphrased
    answers without preserving original numbering). Splits on blank-line
    boundaries and treats each non-trivial paragraph as one answer block,
    in document order. These anchors carry no real label — the mapper
    matches them purely by sequence position against blueprint questions.
    """
    anchors: list[QuestionAnchor] = []
    offset = 0
    for para in re.split(r"\n\s*\n", flat_text):
        stripped = para.strip()
        if len(stripped) < 3 or _is_noise(stripped):
            offset += len(para) + 2
            continue
        start = flat_text.find(para, offset)
        if start == -1:
            start = offset
        anchors.append(QuestionAnchor(
            raw_label="",
            normalized="",
            char_offset=start,
            page_number=1,
            confidence=0.5,
            detection_method="paragraph_fallback",
        ))
        offset = start + len(para)

    return anchors
