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
# Extracts just the leading number/sub-part token from a structure_map key
# that has question text baked in too, e.g. "14. GAN" -> "14",
# "1a): Denoising Autoencoder" -> "1a". Unlike _NUMERIC_LABEL_RE this does
# NOT anchor with $, since the key is allowed to have trailing garbage —
# only the token immediately after this prefix is trusted.
_LEADING_LABEL_TOKEN_RE = re.compile(r"^(\d{1,3}(?:\.\d{1,2})?[a-z]?)\b", re.I)


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


def _regex_detect(
    flat_text: str,
    page_map: list[tuple[int, int, int]],
    blueprint_question_numbers: set[str] | None = None,
) -> list[QuestionAnchor]:
    """
    Run all anchor regex patterns over flat_text and return deduplicated,
    UNGUARDED anchors (sorted by position). Callers run the result through
    _apply_sequence_guard() themselves, after merging in any structure_map
    recovery candidates — see detect_anchors() — so the guard's monotonic/
    blueprint-aware logic sees the full picture in one pass rather than
    guarding regex anchors in isolation and structure_map anchors separately.
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
            # match.end() (the WHOLE match, not match.end(1)) is the correct
            # position for the segmenter to start slicing the answer from —
            # several patterns consume trailing separator punctuation/
            # whitespace ("16. ", "(a) ") *after* the captured group, and
            # that separator needs to be skipped too, not just the digits.
            anchors.append(QuestionAnchor(
                raw_label=raw_label,
                normalized=_normalize_label(raw_label),
                char_offset=offset,
                label_end_offset=match.end(),
                page_number=page_for_offset(offset),
                confidence=base_conf,
                detection_method="regex",
            ))

    anchors.sort(key=lambda a: a.char_offset)
    return _apply_sequence_guard(anchors, blueprint_question_numbers)


def _apply_sequence_guard(
    anchors: list[QuestionAnchor],
    blueprint_question_numbers: set[str] | None = None,
) -> list[QuestionAnchor]:
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

    A student is free to answer optional/choice questions within one Part in
    any order (a section offering "answer any two of 16/17/18" has no
    "expected" order) — writing 18 before 16 would otherwise permanently
    lock 16 out, since it never exceeds the running max. When the caller
    supplies the real blueprint question numbers, a bare number that exactly
    matches one of them — and hasn't already been claimed by an earlier
    anchor in this document — is also accepted, on top of (never instead of)
    the ordering rule above. This can't reopen the door for internal list
    markers: a Q13 essay's own "1. Take input..." would need the real
    blueprint Q1 to still be unclaimed, but Q1's real anchor is always
    detected earlier in the document (Part A comes first), so it's already
    claimed by the time Q13's essay is reached.
    """
    accepted: list[QuestionAnchor] = []
    section_max_num = 0
    last_accepted_offset = -10 ** 9
    claimed: set[str] = set()

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
            is_unclaimed_blueprint_number = (
                blueprint_question_numbers is not None
                and norm in blueprint_question_numbers
                and norm not in claimed
            )
            if has_subpart and num == section_max_num and close_enough:
                accepted.append(anchor)
                last_accepted_offset = anchor.char_offset
            elif not has_subpart and (
                section_max_num == 0
                or num > section_max_num
                or (is_choice_form and num == section_max_num)
                or is_unclaimed_blueprint_number
            ):
                accepted.append(anchor)
                section_max_num = max(section_max_num, num)
                last_accepted_offset = anchor.char_offset
                claimed.add(norm)
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


def looks_like_new_question(
    text: str,
    current_max_num: int,
    blueprint_question_numbers: set[str] | None = None,
) -> tuple[bool, int]:
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
            # Same rescue as _apply_sequence_guard: a real, out-of-order
            # blueprint question number (e.g. 16 appearing after 18 within
            # one "answer any two" Part) is still recognized as a genuine
            # new question even though it doesn't exceed current_max_num.
            is_unclaimed_blueprint_number = (
                blueprint_question_numbers is not None
                and _normalize_label(label) in blueprint_question_numbers
            )
            if (
                current_max_num == 0
                or num > current_max_num
                or (is_choice_form and num == current_max_num)
                or is_unclaimed_blueprint_number
            ):
                return True, max(current_max_num, num)
            return False, current_max_num

        if _ROMAN_OR_LETTER_RE.match(label):
            # No cheap proximity signal once already inside one long
            # block's paragraph stream — treat as a continuation.
            return False, current_max_num

    return False, current_max_num


def _apply_sequence_guard(
    anchors: list[QuestionAnchor],
    blueprint_question_numbers: set[str] | None = None,
) -> list[QuestionAnchor]:
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

    A student is free to answer optional/choice questions within one Part in
    any order (a section offering "answer any two of 16/17/18" has no
    "expected" order) — writing 18 before 16 would otherwise permanently
    lock 16 out, since it never exceeds the running max. When the caller
    supplies the real blueprint question numbers, a bare number that exactly
    matches one of them — and hasn't already been claimed by an earlier
    anchor in this document — is also accepted, on top of (never instead of)
    the ordering rule above. This can't reopen the door for internal list
    markers: a Q13 essay's own "1. Take input..." would need the real
    blueprint Q1 to still be unclaimed, but Q1's real anchor is always
    detected earlier in the document (Part A comes first), so it's already
    claimed by the time Q13's essay is reached.
    """
    accepted: list[QuestionAnchor] = []
    section_max_num = 0
    last_accepted_offset = -10 ** 9
    claimed: set[str] = set()

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
            is_unclaimed_blueprint_number = (
                blueprint_question_numbers is not None
                and norm in blueprint_question_numbers
                and norm not in claimed
            )
            if has_subpart and num == section_max_num and close_enough:
                accepted.append(anchor)
                last_accepted_offset = anchor.char_offset
            elif not has_subpart and (
                section_max_num == 0
                or num > section_max_num
                or (is_choice_form and num == section_max_num)
                or is_unclaimed_blueprint_number
            ):
                accepted.append(anchor)
                section_max_num = max(section_max_num, num)
                last_accepted_offset = anchor.char_offset
                claimed.add(norm)
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


def _stringify_structure_map_value(value: Any) -> str:
    """
    Coerce a structure_map value to plain text. The schema asks the OCR
    model for one string per question, but it sometimes returns a list of
    bullet lines instead — mirrors the same normalization in
    app/ocr_engine.py, duplicated (not imported) to avoid pulling that
    module's OpenAI-client init into anchor_detector, and applied here too
    so an OCR record persisted before that fix landed can still be
    recovered from without needing a re-OCR.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "\n".join(str(item) for item in value if isinstance(item, str) and item.strip())
    return ""


def _find_snippet_position(value: str, flat_text: str, search_from: int, search_to: int) -> int | None:
    """
    Locate roughly where `value`'s text begins within flat_text[search_from:search_to].

    structure_map and transcript are both produced by the same OCR call but
    aren't always word-for-word identical — a word can be dropped or altered
    near the start of one but not the other (e.g. transcript: "We use LSTM...",
    structure_map: "We LSTM..."). An exact-prefix match is too brittle for
    that. Try a handful of phrase windows of decreasing length, and skip up
    to 2 leading words in case the very first word is where they diverge —
    prefer the longest, most specific match that's actually found.
    """
    words = value.strip().split()
    for skip in (0, 1, 2):
        for n in (8, 5, 3):
            phrase_words = words[skip: skip + n]
            if len(phrase_words) < n:
                continue
            phrase = " ".join(phrase_words)
            if len(phrase) < 12:
                continue
            pos = flat_text.find(phrase, search_from, search_to)
            if pos != -1:
                return pos
    return None


def _base_number(label: str) -> int | None:
    """Extract just the leading digit run from a label, ignoring any
    decimal/letter sub-part suffix — "19", "19b", "19.1" all give 19."""
    m = _NUMERIC_LABEL_RE.match(label.strip())
    return int(m.group(1)) if m else None


def _harvest_structure_map_anchors(
    ocr_data: dict[str, Any],
    flat_text: str,
    page_map: list[tuple[int, int, int]],
    exclude_base_numbers: set[int],
) -> list[QuestionAnchor]:
    """
    Recover question anchors the regex patterns found zero evidence of, by
    reading each page's `structure_map` (already returned by the OCR step
    alongside `transcript`, but otherwise only merged into the transcript
    text in a narrow len==1 case — see app/ocr_engine.py). The vision model
    sometimes correctly identifies a question's number as a structure_map
    key while dropping that same number from the free-form transcript body
    (e.g. transcribing a whole page of answers with no inline "13.", "14.",
    "15." labels, yet still keying them correctly in structure_map).

    Rather than trust a structure_map key's position blindly (it carries no
    real offset), locate the value text's own position within the page's
    character range in flat_text via substring search — the answer content
    itself is almost always present verbatim in the transcript even when its
    label isn't, so this gives an exact, verifiable position rather than a
    guess. Keys whose value can't be found at all are skipped rather than
    given a fabricated position.

    exclude_base_numbers skips any key whose BASE number (ignoring a
    decimal/letter sub-part suffix) the regex detector already found
    evidence for — compared by number, not exact normalized string, because
    a structure_map key can label the same question at a different
    granularity than the regex anchor already covering it (e.g. regex found
    a plain "19", structure_map separately offers "19b" for the exact same
    physical answer) — comparing only exact normalized strings would miss
    that collision and let structure_map carve a spurious second split out
    of content already claimed as one whole answer by the regex anchor.
    This is purely a gap-filler for question numbers with NO other
    evidence; it never competes with or overrides an already-detected
    anchor. Callers must still run the combined anchor list through
    _apply_sequence_guard(), which is what rejects a page's own internal
    step-list keys (e.g. a long answer's structure_map coming back as
    {"1": ..., "2": ...} for its own numbered steps) the same way it already
    rejects the equivalent regex-detected false positives.
    """
    candidates: list[QuestionAnchor] = []
    for page in ocr_data.get("pages", []):
        structure_map = page.get("structure_map")
        if not isinstance(structure_map, dict):
            continue
        pg_num = page.get("page_number", 1)
        page_range = next(((s, e) for s, e, p in page_map if p == pg_num), None)
        if page_range is None:
            continue
        page_start, page_end = page_range
        search_from = page_start

        for key, value in structure_map.items():
            if not isinstance(key, str):
                continue
            key_stripped = key.strip()
            if not key_stripped:
                continue
            # Prefer an exact clean label ("13", "17.", "18.1", "13a", "a"),
            # the same shape _apply_sequence_guard already knows how to
            # validate. When the key has question text baked in too (e.g.
            # "14. GAN", "1a): Denoising Autoencoder"), extract just its
            # leading numeric/sub-part token instead of rejecting the whole
            # key outright — the guard still validates whatever comes out
            # of this against the document's real question sequence, so an
            # implausible extraction (e.g. OCR dropping a digit and turning
            # "19a)" into "1a)") gets rejected there, not here.
            exact = key_stripped.rstrip(".")
            if _NUMERIC_LABEL_RE.match(exact) or _ROMAN_OR_LETTER_RE.match(exact):
                raw_label = exact
            else:
                token_match = _LEADING_LABEL_TOKEN_RE.match(key_stripped)
                if not token_match:
                    continue
                raw_label = token_match.group(1)
            normalized = _normalize_label(raw_label)
            base_num = _base_number(raw_label)
            if base_num is not None and base_num in exclude_base_numbers:
                continue
            value_text = _stringify_structure_map_value(value)
            if not value_text.strip():
                continue
            pos = _find_snippet_position(value_text, flat_text, search_from, page_end)
            if pos is None:
                continue
            candidates.append(QuestionAnchor(
                raw_label=raw_label,
                normalized=normalized,
                char_offset=pos,
                label_end_offset=pos,  # zero-width: the answer text already
                                       # starts right here, there's no
                                       # separate label token to skip past.
                page_number=pg_num,
                confidence=0.75,
                detection_method="structure_map",
            ))
            search_from = pos + 20

    return candidates


def looks_like_new_question(
    text: str,
    current_max_num: int,
    blueprint_question_numbers: set[str] | None = None,
) -> tuple[bool, int]:
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
            # Same rescue as _apply_sequence_guard: a real, out-of-order
            # blueprint question number (e.g. 16 appearing after 18 within
            # one "answer any two" Part) is still recognized as a genuine
            # new question even though it doesn't exceed current_max_num.
            is_unclaimed_blueprint_number = (
                blueprint_question_numbers is not None
                and _normalize_label(label) in blueprint_question_numbers
            )
            if (
                current_max_num == 0
                or num > current_max_num
                or (is_choice_form and num == current_max_num)
                or is_unclaimed_blueprint_number
            ):
                return True, max(current_max_num, num)
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
            offset = max(flat_text.find(label), 0)
            anchors.append(QuestionAnchor(
                raw_label=label,
                normalized=_normalize_label(label),
                char_offset=offset,
                label_end_offset=offset + len(label),
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
    blueprint_question_numbers: set[str] | None = None,
) -> tuple[str, list[tuple[int, int, int]], list[QuestionAnchor]]:
    """
    Main anchor detection entry point.

    Args:
        ocr_data: OCR JSON {"pages": [{"page_number": int, "transcript": str, "visual_elements": [...]}]}
        blueprint_question_numbers: normalized (see _normalize_label) real
            question numbers from the blueprint, when available. Lets a
            genuine out-of-order question (e.g. 16 answered after 18 within
            one "answer any two" Part) still be recognized as a real anchor
            even though it doesn't exceed the running max — see
            _apply_sequence_guard. Optional: anchor detection works the same
            as before when omitted.

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

    anchors = _regex_detect(flat_text, page_map, blueprint_question_numbers)

    # This average is deliberately computed on regex-only anchors, BEFORE
    # structure_map recovery below — it decides whether the (slow, real LLM
    # call) fallback is warranted, and that question is about whether regex
    # itself struggled. structure_map anchors carry a lower fixed confidence
    # (0.75 < the 0.85 threshold) as a mark of provenance, not uncertainty;
    # letting them dilute this average would mean successfully recovering
    # several anchors via structure_map routinely triggers ANOTHER expensive
    # fallback call right after, on a document regex+structure_map already
    # handled — the opposite of what this recovery path is for.
    regex_avg_conf = (sum(a.confidence for a in anchors) / len(anchors)) if anchors else 0.0

    # Recover anchors the regex found zero evidence of at all (e.g. a whole
    # page transcribed with its question-number labels dropped, even though
    # the model still keyed them correctly elsewhere) using each page's
    # structure_map, already sitting in ocr_data at no extra cost — then run
    # the combined set through the same sequence guard used for regex
    # anchors (now also blueprint-aware), so a page's own internal step-list
    # keys get rejected exactly like the equivalent regex false positives
    # already are.
    existing_base_numbers = {n for n in (_base_number(a.raw_label) for a in anchors) if n is not None}
    structure_map_anchors = _harvest_structure_map_anchors(ocr_data, flat_text, page_map, existing_base_numbers)
    anchors = sorted(anchors + structure_map_anchors, key=lambda a: a.char_offset)
    anchors = _apply_sequence_guard(anchors, blueprint_question_numbers)

    if not anchors or regex_avg_conf < _LOW_CONFIDENCE_THRESHOLD:
        logger.info("Regex anchor confidence low (%.2f); invoking LLM fallback.", regex_avg_conf)
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

    final_avg_conf = (sum(a.confidence for a in anchors) / len(anchors)) if anchors else 0.0
    logger.info("Detected %d question anchors (avg_conf=%.2f).", len(anchors), final_avg_conf)
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
            label_end_offset=start,
            page_number=1,
            confidence=0.5,
            detection_method="paragraph_fallback",
        ))
        offset = start + len(para)

    return anchors
