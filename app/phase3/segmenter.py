"""
Phase 3 – Answer Segmentation Engine

Step 3: Segment the flat OCR text into answer blocks,
one block per detected question anchor.
Preserves paragraphs, lists, visual elements, and multi-page answers.
Never merges answers across different questions.
"""
from __future__ import annotations

import logging
from typing import Any

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
) -> list[AnswerBlock]:
    """
    Slice flat_text at every anchor boundary to produce AnswerBlocks.

    Args:
        flat_text: Full OCR text across all pages.
        anchors:   Sorted list of QuestionAnchor objects.
        ocr_data:  Full OCR JSON (for visual_elements lookup).
        page_map:  (char_start, char_end, page_number) tuples.

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

    logger.info("Segmented %d answer blocks from %d anchors.", len(blocks), len(anchors))
    return blocks
