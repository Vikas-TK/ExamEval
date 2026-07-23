"""
Phase 4 – AI Evaluator

Uses Qwen2.5-7B (via Ollama) to score each student answer.
No fixed rubric — model judges relevance, completeness, correctness.
Optional answer key is provided as guidance context only.
"""
from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import get_settings
from app.phase4.schemas import ScoringResult

logger = logging.getLogger(__name__)
settings = get_settings()

_SYSTEM_PROMPT = """You are an expert university exam evaluator.
Score the student's answer to the given question.
Be fair, consistent, and reward genuine understanding even if phrasing differs from a reference answer.
Always return a valid JSON object and nothing else."""


def _build_prompt(
    question_text: str,
    student_answer: str,
    maximum_marks: float,
    answer_key: str | None,
    question_type: str | None,
    has_visual: bool,
) -> str:
    parts = [
        f"Question: {question_text}",
        f"Question Type: {question_type or 'Descriptive'}",
        f"Maximum Marks: {maximum_marks}",
    ]
    if answer_key:
        parts.append(f"Reference Answer (use as guidance, not rigid match): {answer_key}")
    parts.append(f"Student's Answer: {student_answer or '[No answer written]'}")
    if has_visual:
        parts.append("Note: Student's answer included diagrams/visual elements (already noted in answer text).")
    parts.append(
        f'\nScore the student answer from 0 to {maximum_marks} (decimals allowed).\n'
        f'Return ONLY this JSON:\n'
        f'{{"score": <float>, "feedback": "<1-2 sentence explanation for faculty>", "confidence": <0.0-1.0>}}'
    )
    return "\n".join(parts)


def score_answer(
    question_text: str | None,
    student_answer: str | None,
    maximum_marks: float,
    answer_key: str | None = None,
    question_type: str | None = None,
    has_visual: bool = False,
) -> ScoringResult:
    """
    Score a single student answer using Qwen2.5-7B.
    Returns ScoringResult(score, feedback, confidence).
    Falls back to 0 marks with error message if LLM fails.
    """
    # Skip if no answer at all
    if not student_answer or not student_answer.strip():
        return ScoringResult(
            score=0.0,
            feedback="No answer provided by student.",
            confidence=1.0,
        )

    if not question_text:
        question_text = "Unnamed question"

    prompt = _build_prompt(
        question_text, student_answer, maximum_marks,
        answer_key, question_type, has_visual
    )

    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=settings.qwen_api_key,
            base_url=settings.qwen_api_base,
        )
        response = client.chat.completions.create(
            model=settings.llm_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=256,
        )
        raw = (response.choices[0].message.content or "{}").strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = "\n".join(raw.splitlines()[1:])
            raw = raw.rstrip("`").strip()

        data = json.loads(raw)
        score = float(data.get("score", 0.0))
        # Clamp score to [0, maximum_marks]
        score = max(0.0, min(score, maximum_marks))
        return ScoringResult(
            score=round(score, 2),
            feedback=str(data.get("feedback", "")),
            confidence=float(data.get("confidence", 0.8)),
        )

    except json.JSONDecodeError as exc:
        logger.warning("Evaluator JSON parse error: %s | raw=%s", exc, raw[:200])
        return ScoringResult(score=0.0, feedback=f"Scoring error (JSON parse): {exc}", confidence=0.0)
    except Exception as exc:
        logger.error("Evaluator LLM error: %s", exc)
        return ScoringResult(score=0.0, feedback=f"Scoring error: {exc}", confidence=0.0)
