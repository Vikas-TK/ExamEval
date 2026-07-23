"""
Phase 3 – Blueprint Mapping Engine

Step 4: Map segmented AnswerBlocks to blueprint questions.
Strategy:
  1. Exact match on normalized question number (Q1 == Q1).
  2. Fuzzy numeric match (strip non-digits, compare).
  3. Sequential fallback when answer count == blueprint question count.
  4. Unmatched blocks → UNMAPPED; blueprint questions with no block → SKIPPED.

No rubrics. No expected-answer scoring. Pure structural mapping only.
"""
from __future__ import annotations

import logging
import re
import uuid
from typing import Any

from app.phase3.schemas import AnswerBlock, BlueprintQuestion, MappedQA

logger = logging.getLogger(__name__)


def _extract_blueprint_questions(blueprint: dict[str, Any]) -> list[BlueprintQuestion]:
    """Flatten all sections → questions from the blueprint JSON."""
    questions: list[BlueprintQuestion] = []
    for section in blueprint.get("sections", []):
        section_name = section.get("name", "General")
        for q in section.get("questions", []):
            questions.append(BlueprintQuestion(
                question_id=q.get("question_id", ""),
                question_number=str(q.get("question_number", "")),
                question_text=q.get("question_text"),
                maximum_marks=float(q.get("maximum_marks", 0)),
                question_type=str(q.get("question_type", "Descriptive")),
                section_name=section_name,
                question_order=int(q.get("question_order", 0)),
            ))
    questions.sort(key=lambda q: q.question_order)
    return questions


def _strip_digits(label: str) -> str:
    """Extract only the digit portion of a label for fuzzy matching."""
    return re.sub(r"[^0-9]", "", label)


def _normalize_qno(label: str) -> str:
    """Normalize to canonical comparable token: Q13, Q14, Q15, PART A, etc."""
    stripped = str(label).strip().upper()
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

    if re.match(r"^(PART|SECTION)\s+[A-Z]", stripped):
        return stripped

    return f"Q{stripped}" if len(stripped) <= 3 and not stripped.startswith("Q") else stripped


def map_answers_to_blueprint(
    blocks: list[AnswerBlock],
    blueprint: dict[str, Any],
    evaluation_id: uuid.UUID,
    blueprint_id: uuid.UUID,
) -> list[MappedQA]:
    """
    Map AnswerBlocks to blueprint questions, returning one MappedQA per blueprint question.

    Fault-tolerant: a failed mapping for one question does NOT stop others.
    """
    bp_questions = _extract_blueprint_questions(blueprint)

    if not bp_questions:
        logger.warning("Blueprint has no questions; returning empty mapping.")
        return []

    # Build lookup: normalized_qno → BlueprintQuestion
    bp_index: dict[str, BlueprintQuestion] = {
        _normalize_qno(bq.question_number): bq for bq in bp_questions
    }
    bp_digit_index: dict[str, BlueprintQuestion] = {
        _strip_digits(bq.question_number): bq
        for bq in bp_questions
        if _strip_digits(bq.question_number)
    }

    # Build answer block lookup: normalized_qno → AnswerBlock
    block_index: dict[str, AnswerBlock] = {}
    for block in blocks:
        key = _normalize_qno(block.anchor.normalized)
        block_index[key] = block

    # Try sequential fallback if no overlap detected
    sequential_ok = False
    overlap = set(bp_index.keys()) & set(block_index.keys())
    if not overlap and len(blocks) == len(bp_questions):
        sequential_ok = True
        logger.info("No label overlap; using sequential mapping (%d blocks → %d questions).",
                    len(blocks), len(bp_questions))

    mapped_qas: list[MappedQA] = []

    for seq_idx, bq in enumerate(bp_questions):
        try:
            block: AnswerBlock | None = None
            anchor_text: str | None = None
            anchor_confidence: float = 0.0

            norm_key = _normalize_qno(bq.question_number)

            # 1. Exact normalized match
            if norm_key in block_index:
                block = block_index[norm_key]
            # 2. Fuzzy digit match
            elif _strip_digits(bq.question_number) and _strip_digits(bq.question_number) in bp_digit_index:
                dkey = _strip_digits(bq.question_number)
                for bk, blk in block_index.items():
                    if _strip_digits(bk) == dkey:
                        block = blk
                        break
            # 3. Sequential fallback
            elif sequential_ok and seq_idx < len(blocks):
                block = blocks[seq_idx]

            if block is not None:
                anchor_text = block.anchor.raw_label
                anchor_confidence = block.anchor.confidence
                student_answer = block.raw_text or None
                visual_elements = block.visual_elements
                mapping_status = "MAPPED"
            else:
                student_answer = None
                visual_elements = []
                mapping_status = "SKIPPED" if True else "UNMAPPED"  # blank = SKIPPED by policy

            mapped_qas.append(MappedQA(
                evaluation_id=evaluation_id,
                blueprint_id=blueprint_id,
                question_id=bq.question_id,
                question_number=bq.question_number,
                question_text=bq.question_text,
                maximum_marks=bq.maximum_marks,
                question_type=bq.question_type,
                section_name=bq.section_name,
                student_answer=student_answer,
                answer_length=len(student_answer) if student_answer else 0,
                visual_elements=visual_elements,
                anchor_text=anchor_text,
                anchor_confidence=anchor_confidence,
                mapping_status=mapping_status,
                question_sequence=seq_idx + 1,
            ))

        except Exception as exc:
            logger.error("Mapping failed for question %s: %s — marking UNMAPPED.", bq.question_number, exc)
            mapped_qas.append(MappedQA(
                evaluation_id=evaluation_id,
                blueprint_id=blueprint_id,
                question_id=bq.question_id,
                question_number=bq.question_number,
                question_text=bq.question_text,
                maximum_marks=bq.maximum_marks,
                question_type=bq.question_type,
                section_name=bq.section_name,
                student_answer=None,
                answer_length=0,
                visual_elements=[],
                anchor_text=None,
                anchor_confidence=0.0,
                mapping_status="UNMAPPED",
                question_sequence=seq_idx + 1,
            ))

    logger.info("Mapping complete: %d/%d questions mapped.",
                sum(1 for m in mapped_qas if m.mapping_status == "MAPPED"),
                len(mapped_qas))
    return mapped_qas
