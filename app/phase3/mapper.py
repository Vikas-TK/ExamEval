"""
Phase 3 – Blueprint Mapping Engine

Step 4: Map segmented AnswerBlocks to blueprint questions.
Strategy:
  1. Exact match on normalized question number (Q1 == Q1) — i.e. the number
     the student actually wrote next to their answer, when present.
  2. Fuzzy numeric match (strip non-digits, compare).
  3. Content-based semantic match via local LLM, when no number is present
     anywhere on the page (matches answer wording to question wording).
  4. Positional fallback only as a last resort, if the LLM match is
     unavailable/fails.
  5. Unmatched blocks → UNMAPPED; blueprint questions with no block → SKIPPED.

No rubrics. No expected-answer scoring. Pure structural mapping only.
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from typing import Any

from app.core.config import get_settings
from app.phase3.schemas import AnswerBlock, BlueprintQuestion, MappedQA

logger = logging.getLogger(__name__)
settings = get_settings()


def _llm_semantic_match(
    blocks: list[AnswerBlock], bp_questions: list[BlueprintQuestion]
) -> dict[int, str]:
    """
    When answers carry no question-number label at all, ask the local LLM to
    match each answer block to the blueprint question it most likely answers,
    based on content/meaning — not paragraph position. Returns
    {block_index: question_id}. Empty dict on any failure so callers can fall
    back to positional matching rather than crash the mapping step.
    """
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=settings.qwen_api_key,
            base_url=settings.qwen_api_base,
            timeout=30.0,
            max_retries=1,
        )

        q_lines = "\n".join(
            f"{i}: [{bq.question_id}] {bq.question_text or bq.question_number}"
            for i, bq in enumerate(bp_questions)
        )
        a_lines = "\n".join(
            f"{i}: {(block.raw_text or '')[:220]}"
            for i, block in enumerate(blocks)
        )
        system = (
            "You match exam answer paragraphs to the question they answer, using content and "
            "meaning only — the answer sheet has no visible question numbers next to the answers. "
            "Each answer maps to at most one question; leave a question unmatched if no answer "
            "addresses it, and leave an answer unmatched if it fits no question well. "
            "Return ONLY a JSON object of the form {\"<answer_index>\": \"<question_id>\", ...} "
            "using the indices and question_ids given below — no commentary, no markdown fences."
        )
        user = f"QUESTIONS:\n{q_lines}\n\nANSWERS:\n{a_lines}"
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.0,
            max_tokens=1024,
            extra_body={"options": {"num_ctx": settings.qwen_num_ctx}},
        )
        raw = (response.choices[0].message.content or "{}").strip()
        if raw.startswith("```"):
            raw = "\n".join(raw.splitlines()[1:-1])
        mapping = json.loads(raw)

        # Small local models often echo back the question's list index
        # instead of the literal question_id we asked for — accept either.
        valid_ids = {bq.question_id for bq in bp_questions}
        by_index0 = {str(i): bq.question_id for i, bq in enumerate(bp_questions)}
        by_index1 = {str(i + 1): bq.question_id for i, bq in enumerate(bp_questions)}

        resolved: dict[int, str] = {}
        for k, v in mapping.items():
            if not str(k).isdigit() or int(k) >= len(blocks):
                continue
            v = str(v)
            if v in valid_ids:
                resolved[int(k)] = v
            elif v in by_index0:
                resolved[int(k)] = by_index0[v]
            elif v in by_index1:
                resolved[int(k)] = by_index1[v]
        return resolved
    except Exception as exc:
        logger.warning("Semantic content-matching fallback failed: %s", exc)
        return {}


def _extract_blueprint_questions(blueprint: dict[str, Any]) -> list[BlueprintQuestion]:
    """
    Flatten all sections → questions from the blueprint JSON, preserving
    section grouping (Part A fully, then Part B fully, then Part C, ...).

    question_order is assigned locally per-section by the blueprint parser
    (1, 2, 3... restarting at each new Part), NOT globally across the whole
    paper. Sorting the flattened list by question_order alone therefore ties
    Q1 (Part A), Q11 (Part B), Q15 (Part C) all at "1" and lets a stable sort
    interleave them in whatever order they were appended — which is exactly
    the Q1 → Q11 → Q15 → Q2 → Q12 → Q16 jump this was producing. Sorting by
    (section_appearance_index, question_order) keeps each section's block
    intact while still respecting the intended order within it.
    """
    questions: list[BlueprintQuestion] = []
    section_rank: dict[str, int] = {}
    for section in blueprint.get("sections", []):
        section_name = section.get("name", "General")
        section_rank.setdefault(section_name, len(section_rank))
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
    questions.sort(key=lambda q: (section_rank.get(q.section_name, 0), q.question_order))
    return questions


_NOISE_FRAGMENT_RE = re.compile(r"^\s*[\d\s\.\-\)]*\s*marks?\s*[\d\s\.\-\)]*$", re.I)


def _looks_like_answer(text: str | None) -> bool:
    """
    Filters out non-answer fragments (mark allocations like "- 2 Marks",
    stray punctuation, near-empty scraps) before they're offered as
    semantic-match/positional candidates — one such fragment occupying a
    slot shifts every real answer after it by one position.
    """
    stripped = (text or "").strip()
    if len(stripped) < 15:
        return False
    if not re.search(r"[A-Za-z]{3,}", stripped):
        return False
    if _NOISE_FRAGMENT_RE.match(stripped):
        return False
    return True


_STOPWORDS = {
    "a", "an", "the", "is", "are", "was", "were", "what", "who", "which",
    "define", "explain", "describe", "discuss", "give", "list", "state",
    "name", "of", "and", "or", "to", "in", "on", "for", "with", "by",
    "from", "its", "it", "this", "that", "these", "those", "short",
    "answer", "note", "write", "about", "differentiate", "compare",
    "advantages", "disadvantages", "each", "any", "two", "three",
}


def _tokenize(text: str | None) -> set[str]:
    return {
        w for w in re.findall(r"[a-zA-Z]{3,}", (text or "").lower())
        if w not in _STOPWORDS
    }


def _lexical_match(
    blocks: list[AnswerBlock], bp_questions: list[BlueprintQuestion]
) -> dict[int, str]:
    """
    Fast, deterministic content match using keyword overlap between each
    answer and each question — no model call, no latency. Exam definitional
    answers ("Use Case: A description of...") typically restate the term
    from the question itself, which this catches directly. Greedily assigns
    the highest-overlap pairs first so no answer or question is used twice.
    Returns {block_index: question_id} for high-confidence matches only;
    anything left unmatched should go to the (slower) LLM semantic match.
    """
    q_tokens = [(bq, _tokenize(bq.question_text or bq.question_number)) for bq in bp_questions]
    scored: list[tuple[int, int, str]] = []  # (overlap_score, block_idx, question_id)
    for bidx, block in enumerate(blocks):
        b_tokens = _tokenize(block.raw_text)
        if not b_tokens:
            continue
        for bq, qtok in q_tokens:
            if not qtok:
                continue
            overlap = len(b_tokens & qtok)
            if overlap > 0:
                scored.append((overlap, bidx, bq.question_id))

    scored.sort(key=lambda t: -t[0])
    used_blocks: set[int] = set()
    used_questions: set[str] = set()
    result: dict[int, str] = {}
    for score, bidx, qid in scored:
        if bidx in used_blocks or qid in used_questions:
            continue
        result[bidx] = qid
        used_blocks.add(bidx)
        used_questions.add(qid)
    return result


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
    # (blocks with no real label — e.g. paragraph-fallback / section-split
    # anchors — are excluded here since they'd all collide on the same
    # empty key; they're handled separately below via semantic matching)
    block_index: dict[str, AnswerBlock] = {}
    for block in blocks:
        if not block.anchor.normalized:
            continue
        key = _normalize_qno(block.anchor.normalized)
        block_index[key] = block

    # Pass 1: direct number-based matching only (exact + fuzzy digit).
    # This must run per-question BEFORE any semantic matching so that a
    # well-labeled question elsewhere in the paper (e.g. Q11 in Part B)
    # never causes unlabeled questions in another section (e.g. Q1-Q10 in
    # Part A) to be skipped — each question is resolved independently.
    direct_matches: dict[str, AnswerBlock] = {}
    unmatched_questions: list[BlueprintQuestion] = []
    for bq in bp_questions:
        norm_key = _normalize_qno(bq.question_number)
        block = block_index.get(norm_key)
        if block is None:
            dkey = _strip_digits(bq.question_number)
            if dkey:
                for bk, blk in block_index.items():
                    if _strip_digits(bk) == dkey:
                        block = blk
                        break
        if block is not None:
            direct_matches[bq.question_id] = block
        else:
            unmatched_questions.append(bq)

    # Pass 2: content-based semantic match, scoped to ONLY the questions
    # still unresolved and the blocks not already claimed by pass 1 (labeled
    # blocks stay reserved for their exact question even if unused elsewhere).
    # Junk fragments (mark allocations, stray headers, near-empty text) are
    # dropped here rather than passed as candidates — one bogus fragment
    # occupying a slot shifts every subsequent match by one.
    used_block_ids = {id(b) for b in direct_matches.values()}
    leftover_blocks = [
        b for b in blocks
        if id(b) not in used_block_ids and _looks_like_answer(b.raw_text)
    ]

    qid_to_block: dict[str, AnswerBlock] = {}

    # Pass 2a: fast keyword-overlap match (no model call). Handles the common
    # case where a definitional answer restates the term from its question.
    lexical_map = _lexical_match(leftover_blocks, unmatched_questions)
    for bidx, qid in lexical_map.items():
        qid_to_block[qid] = leftover_blocks[bidx]
    if lexical_map:
        logger.info("Keyword-overlap matching resolved %d/%d remaining questions.",
                    len(lexical_map), len(unmatched_questions))

    # Pass 2b: LLM semantic match for whatever keyword overlap couldn't resolve.
    still_unmatched = [bq for bq in unmatched_questions if bq.question_id not in qid_to_block]
    still_leftover = [b for i, b in enumerate(leftover_blocks) if i not in lexical_map]

    semantic_map: dict[int, str] = {}
    if still_unmatched and still_leftover:
        semantic_map = _llm_semantic_match(still_leftover, still_unmatched)
        if semantic_map:
            logger.info("Content-based semantic mapping resolved %d/%d remaining questions.",
                        len(semantic_map), len(still_unmatched))
            for idx, qid in semantic_map.items():
                if 0 <= idx < len(still_leftover):
                    qid_to_block[qid] = still_leftover[idx]
        else:
            logger.info("Semantic match unavailable for %d remaining questions; will fall back to position within leftovers.",
                        len(still_unmatched))

    # Pass 3 (last resort): positional pairing, but scoped strictly to the
    # leftover questions/blocks in their own relative order — never across
    # the whole document — so it can't jump a Part-A question onto Part-B text.
    if not semantic_map and still_leftover:
        for i, bq in enumerate(still_unmatched):
            if i < len(still_leftover):
                qid_to_block.setdefault(bq.question_id, still_leftover[i])

    mapped_qas: list[MappedQA] = []

    for seq_idx, bq in enumerate(bp_questions):
        try:
            anchor_text: str | None = None
            anchor_confidence: float = 0.0

            block = direct_matches.get(bq.question_id) or qid_to_block.get(bq.question_id)

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
