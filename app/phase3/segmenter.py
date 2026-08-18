"""
Phase 3 – Answer Segmentation Engine

Step 3: Segment the flat OCR text into answer blocks,
one block per detected question anchor.
Preserves paragraphs, lists, visual elements, and multi-page answers.
Never merges answers across different questions.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from app.phase3.anchor_detector import looks_like_new_question
from app.phase3.schemas import AnswerBlock, QuestionAnchor

logger = logging.getLogger(__name__)


def _collect_visual_elements(
    ocr_data: dict[str, Any],
    char_start: int,
    char_end: int,
    page_map: list[tuple[int, int, int]],
) -> list[dict[str, Any]]:
    """
    Collect visual elements (diagrams, tables, formulas) from OCR pages
    that fall within the answer block character range.
    """
    pages: list[dict[str, Any]] = ocr_data.get("pages", [])
    elements: list[dict[str, Any]] = []
    for page in pages:
        pg_num = page.get("page_number", 1)
        # Find this page's char range
        for start, end, pn in page_map:
            if pn != pg_num:
                continue
            # Only include elements if this page overlaps with the answer block
            if end < char_start or start > char_end:
                continue
            for ve in page.get("visual_elements", []):
                elements.append({**ve, "page_number": pg_num})
    return elements


def segment_answers(
    flat_text: str,
    anchors: list[QuestionAnchor],
    ocr_data: dict[str, Any],
    page_map: list[tuple[int, int, int]],
    blueprint_question_numbers: set[str] | None = None,
) -> list[AnswerBlock]:
    """
    Slice flat_text at every anchor boundary to produce AnswerBlocks.

    Args:
        flat_text: Full OCR text across all pages.
        anchors:   Sorted list of QuestionAnchor objects.
        ocr_data:  Full OCR JSON (for visual_elements lookup).
        page_map:  (char_start, char_end, page_number) tuples.
        blueprint_question_numbers: normalized real blueprint question
            numbers, passed through to looks_like_new_question so an
            out-of-order question missed by detect_anchors can still be
            recognized when re-checked at the paragraph level.

    Returns:
        List of AnswerBlock, one per anchor, with raw_text and visual_elements.
    """
    if not anchors:
        logger.warning("No anchors found; returning single empty AnswerBlock.")
        return []

    blocks: list[AnswerBlock] = []

    for i, anchor in enumerate(anchors):
        # The answer text starts after the anchor label ends
        answer_start = anchor.char_offset + len(anchor.raw_label)

        # Answer ends at the start of the next anchor (or end of text)
        if i + 1 < len(anchors):
            answer_end = anchors[i + 1].char_offset
        else:
            answer_end = len(flat_text)

        raw_text = flat_text[answer_start:answer_end].strip()

        from app.ocr_corrector import correct_ocr_text
        raw_text = correct_ocr_text(raw_text)

        # Skip blank pages / empty segments gracefully
        if not raw_text and not ocr_data.get("pages"):
            logger.debug("Empty answer block for anchor '%s'; marking as empty.", anchor.normalized)

        visual_elements = _collect_visual_elements(
            ocr_data, answer_start, answer_end, page_map
        )

        # Determine which pages this answer spans
        page_numbers: list[int] = []
        for start, end, pg in page_map:
            if start < answer_end and end > answer_start:
                page_numbers.append(pg)

        blocks.append(AnswerBlock(
            anchor=anchor,
            raw_text=raw_text,
            visual_elements=visual_elements,
            page_numbers=sorted(set(page_numbers)),
        ))

    blocks = _split_section_header_blocks(blocks, blueprint_question_numbers)

    logger.info("Segmented %d answer blocks from %d anchors.", len(blocks), len(anchors))
    return blocks


def _split_section_header_blocks(
    blocks: list[AnswerBlock],
    blueprint_question_numbers: set[str] | None = None,
) -> list[AnswerBlock]:
    """
    Split a block into one sub-block per paragraph whenever it looks like it
    swallowed more than one answer. Two distinct cases produce this:

    1. A "Part A" / "Section A" anchor marks a section boundary, not a single
       question — if no individual question numbers were written within that
       section, everything up to the next anchor lands in one block. Here
       EVERY paragraph is unlabeled (the section anchor isn't a real answer
       to anything), left for the semantic/lexical content matcher.

    2. A real question-numbered anchor (e.g. "5.") whose next 1-2 questions
       lost their number to OCR/handwriting noise — the answer for Q5 keeps
       absorbing Q6's and Q7's text until the next anchor it CAN detect
       (e.g. "8."). Here only paragraphs that themselves look like a genuine
       new question boundary (see looks_like_new_question) get split off as
       unlabeled leftovers; everything else — section headings, numbered
       working-steps, closing paragraphs — stays part of THIS answer. A long
       multi-page descriptive answer routinely has several blank-line
       paragraphs of its own and must not be shredded down to just the
       first one.
    """
    expanded: list[AnswerBlock] = []
    for block in blocks:
        norm = (block.anchor.normalized or "").upper()
        is_section_header = norm.startswith("PART") or norm.startswith("SECTION")

        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", block.raw_text) if p.strip()]
        if len(paragraphs) <= 1:
            expanded.append(block)
            continue

        if is_section_header:
            for para in paragraphs:
                expanded.append(AnswerBlock(
                    anchor=QuestionAnchor(
                        raw_label="",
                        normalized="",
                        char_offset=block.anchor.char_offset,
                        page_number=block.anchor.page_number,
                        confidence=0.5,
                        detection_method="section_split",
                    ),
                    raw_text=para,
                    visual_elements=block.visual_elements,
                    page_numbers=block.page_numbers,
                ))
            continue

        # Real numbered anchor: group paragraphs, starting a new (unlabeled)
        # group only when a paragraph genuinely looks like the next question.
        digits = re.sub(r"^Q", "", norm)
        current_max_num = int(digits) if digits.isdigit() else 0

        groups: list[tuple[QuestionAnchor, list[str]]] = [(block.anchor, [paragraphs[0]])]
        for para in paragraphs[1:]:
            is_new, current_max_num = looks_like_new_question(para, current_max_num, blueprint_question_numbers)
            if is_new:
                groups.append((
                    QuestionAnchor(
                        raw_label="",
                        normalized="",
                        char_offset=block.anchor.char_offset,
                        page_number=block.anchor.page_number,
                        confidence=0.5,
                        detection_method="section_split",
                    ),
                    [para],
                ))
            else:
                groups[-1][1].append(para)

        for anchor, parts in groups:
            expanded.append(AnswerBlock(
                anchor=anchor,
                raw_text="\n\n".join(parts),
                visual_elements=block.visual_elements,
                page_numbers=block.page_numbers,
            ))

    return expanded
