"""
Phase 4 – AI Evaluator

Uses a local Qwen model (via Ollama) to score each student answer.
No fixed rubric — model judges relevance, completeness, correctness.
Optional answer key is provided as guidance context only.
"""
from __future__ import annotations

import json
import logging

from app.core.config import get_settings
from app.phase4.schemas import ScoringResult

logger = logging.getLogger(__name__)
settings = get_settings()

# ─── Persona inference ─────────────────────────────────────────────────────────
# Grading with a subject-matter-expert persona ("You are a senior software
# engineer...") rather than a generic "exam evaluator" measurably improves
# how well the model recognizes domain-correct answers phrased differently
# from a reference key. Keyword-matched against the question text first
# (cheap, no extra model call, no added latency) since a single exam can mix
# topics; falls back to the blueprint's subject when no keyword hits.
_PERSONA_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("scrum", "agile", "waterfall", "sdlc", "software process", "requirement",
      "use case", "uml", "software engineering", "reengineering", "testing",
      "black-box", "white-box", "backlog", "software development"),
     "You are a senior software engineer and software architect"),
    (("algorithm", "data structure", "sorting", "tree", "graph", "linked list",
      "complexity", "recursion", "stack", "queue", "hashing"),
     "You are an expert in algorithms and data structures"),
    (("sql", "database", "dbms", "normalization", "transaction", "query",
      "schema", "relational"),
     "You are a senior database engineer"),
    (("network", "tcp", "udp", "osi", "router", "protocol", "ip address",
      "socket", "bandwidth"),
     "You are a computer networks engineer"),
    (("operating system", "process", "thread", "deadlock", "scheduling",
      "memory management", "kernel", "semaphore", "paging"),
     "You are an operating systems engineer"),
    (("cloud", "kubernetes", "docker", "microservice", "distributed system",
      "aws", "azure", "container", "load balanc"),
     "You are a cloud solutions architect"),
    (("machine learning", "neural network", "model training", "dataset",
      "regression", "classification", "deep learning", "ai model"),
     "You are a machine learning engineer"),
    (("python", "programming", "function", "variable", "loop", "syntax",
      "code", "compile", "debug"),
     "You are a senior software developer"),
]


def _infer_persona(question_text: str | None, subject: str | None) -> str:
    text = (question_text or "").lower()
    for keywords, persona in _PERSONA_KEYWORDS:
        if any(kw in text for kw in keywords):
            return persona
    if subject:
        return f"You are a subject-matter expert in {subject}"
    return "You are an expert university exam evaluator"


def _fmt_marks(value: float) -> str:
    """Renders whole numbers without a trailing '.0' but keeps genuine fractions (e.g. 0.5, 1.5)."""
    return str(int(value)) if float(value).is_integer() else str(value)


def _round_to_half(value: float) -> float:
    """Quantizes to the nearest 0.5 — exam marks here are only ever whole numbers or half-marks."""
    return round(value * 2) / 2


def _build_system_prompt(persona: str) -> str:
    return (
        f"{persona}, evaluating a student's exam answer. "
        "Be balanced, fair, and moderate in awarding marks. "
        "Be somewhat lenient and reward genuine understanding even if phrasing differs from a "
        "reference answer or uses equivalent terminology, but DO NOT award overly high or maximum marks "
        "unless the answer is fully comprehensive, detailed, and flawless. "
        "Do not be excessively strict, but do not give top scores easily — always aim for a balanced, "
        "realistic middle-ground score that reflects actual core understanding without inflating it. "
        "Scores MUST be either a whole number or a whole number plus exactly .5 (half-mark "
        "increments only) — e.g. 0, 0.5, 1, 3.5 are valid; 3.25, 3.7, 3.33 are NOT. Never use any "
        "decimal other than .5. "
        "Always return a valid JSON object and nothing else."
    )


def _build_prompt(
    question_text: str,
    student_answer: str,
    maximum_marks: float,
    answer_key: str | None,
    question_type: str | None,
    has_visual: bool,
) -> str:
    max_marks_str = _fmt_marks(maximum_marks)
    parts = [
        f"Question: {question_text}",
        f"Question Type: {question_type or 'Descriptive'}",
        f"Maximum Marks: {max_marks_str}",
    ]
    if answer_key:
        parts.append(f"Reference Answer (use as guidance, not rigid match): {answer_key}")
    parts.append(f"Student's Answer: {student_answer or '[No answer written]'}")
    if has_visual:
        parts.append("Note: Student's answer included diagrams/visual elements (already noted in answer text).")
    parts.append(
        f'\nScore the student answer from 0 to {max_marks_str}, in whole numbers or half-mark (.5) '
        f'increments only — no other decimals. Aim for a balanced, moderate middle-ground score reflecting actual depth.\n'
        f'Return ONLY this JSON:\n'
        f'{{"score": <number, whole or ending in .5>, "feedback": "<1-2 sentence explanation for faculty>", "confidence": <0.0-1.0>}}'
    )
    return "\n".join(parts)


def score_answer(
    question_text: str | None,
    student_answer: str | None,
    maximum_marks: float,
    answer_key: str | None = None,
    question_type: str | None = None,
    has_visual: bool = False,
    subject: str | None = None,
) -> ScoringResult:
    """
    Score a single student answer using the locally configured Qwen model.
    Returns ScoringResult(score, feedback, confidence) with an integer score.
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

    persona = _infer_persona(question_text, subject)
    system_prompt = _build_system_prompt(persona)
    prompt = _build_prompt(
        question_text, student_answer, maximum_marks,
        answer_key, question_type, has_visual
    )

    raw = "{}"
    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=settings.qwen_api_key,
            base_url=settings.qwen_api_base,
            timeout=30.0,
            max_retries=1,
        )
        response = client.chat.completions.create(
            model=settings.evaluation_llm_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.1,
            max_tokens=256,
            extra_body={"options": {"num_ctx": settings.qwen_num_ctx}},
        )
        raw = (response.choices[0].message.content or "{}").strip()
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = "\n".join(raw.splitlines()[1:])
            raw = raw.rstrip("`").strip()

        data = json.loads(raw)
        score = _round_to_half(float(data.get("score", 0.0)))
        # Clamp score to [0, maximum_marks] — maximum_marks itself may be a
        # half-mark value (e.g. 0.5 per question in an MCQ section), so this
        # must stay a float rather than truncating via int().
        score = max(0.0, min(score, float(maximum_marks)))
        return ScoringResult(
            score=float(score),
            feedback=str(data.get("feedback", "")),
            confidence=float(data.get("confidence", 0.8)),
        )

    except json.JSONDecodeError as exc:
        logger.warning("Evaluator JSON parse error: %s | raw=%s", exc, raw[:200])
        return ScoringResult(score=0.0, feedback=f"Scoring error (JSON parse): {exc}", confidence=0.0)
    except Exception as exc:
        logger.error("Evaluator LLM error: %s", exc)
        return ScoringResult(score=0.0, feedback=f"Scoring error: {exc}", confidence=0.0)
