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


def _is_objective_or_tf_question(question_text: str | None, question_type: str | None) -> bool:
    q_type = (question_type or "").lower()
    q_text = (question_text or "").lower()
    if any(t in q_type for t in ["true/false", "true or false", "t/f", "mcq", "multiple choice", "objective", "binary"]):
        return True
    if any(phrase in q_text for phrase in ["true or false", "say true or false", "state true or false", "true/false", "t/f"]):
        return True
    return False


def _build_system_prompt(persona: str) -> str:
    return (
        f"{persona}, evaluating a student's exam answer. "
        "Be balanced, fair, and moderate in awarding marks.\n"
        "CRITICAL EVALUATION & CONSISTENCY RULES:\n"
        "1. STRICT FEEDBACK-SCORE CONSISTENCY: Your assigned score MUST strictly align with your written feedback. "
        "If your feedback states, explains, or implies that the student's answer is incorrect, wrong, or false, "
        "the score MUST be 0 (0.0). NEVER award partial or non-zero marks when your feedback indicates the answer is wrong.\n"
        "2. OBJECTIVE & TRUE/FALSE QUESTIONS: Objective, True/False, Multiple Choice, and binary factual questions "
        "are strictly all-or-nothing. If the student selects or states an incorrect choice (e.g., stating 'True' when the statement is false), "
        "the score MUST be 0.0. Absolutely NO partial marks are allowed for an incorrect objective answer.\n"
        "3. DESCRIPTIVE QUESTIONS: Be fair and reward genuine understanding even if phrasing differs, "
        "aiming for a realistic middle-ground score when core concepts are shown. But if the core statement is factually wrong, award 0 marks.\n"
        "4. SCORE FORMAT: Scores MUST be either a whole number or a whole number plus exactly .5 (half-mark increments only) "
        "— e.g. 0, 0.5, 1, 3.5 are valid; 3.25, 3.7 are NOT. Never use any decimal other than .5.\n"
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
    is_tf_obj = _is_objective_or_tf_question(question_text, question_type)
    parts = [
        f"Question: {question_text}",
        f"Question Type: {question_type or ('True/False Objective' if is_tf_obj else 'Descriptive')}",
        f"Maximum Marks: {max_marks_str}",
    ]
    if answer_key:
        parts.append(f"Reference Answer (use as guidance, not rigid match): {answer_key}")
    parts.append(f"Student's Answer: {student_answer or '[No answer written]'}")
    if has_visual:
        parts.append("Note: Student's answer included diagrams/visual elements (already noted in answer text).")
    
    if is_tf_obj:
        parts.append(
            "\nSPECIAL RULE FOR THIS QUESTION: This is a True/False or objective question. "
            "Evaluation is strictly all-or-nothing. If the student's answer/choice is incorrect or false, "
            "the score MUST be 0.0. Do NOT award any partial credit."
        )

    parts.append(
        f'\nScore the student answer from 0 to {max_marks_str}, in whole numbers or half-mark (.5) '
        f'increments only — no other decimals.\n'
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
    Returns ScoringResult(score, feedback, confidence) with an integer/half-mark score.
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
        feedback = str(data.get("feedback", ""))

        # ─── Post-processing Consistency Guardrail ───
        # Ensure score strictly matches written feedback, especially for True/False and objective questions.
        feedback_lower = feedback.lower()
        is_tf_obj = _is_objective_or_tf_question(question_text, question_type)

        negative_indicators = [
            "not ", "incorrect", "false", "wrong", "is false", "is incorrect",
            "should be false", "should be true", "is not used", "is wrong",
            "does not", "cannot be", "erroneous", "statement is false"
        ]

        if is_tf_obj and score > 0.0:
            if any(ind in feedback_lower for ind in negative_indicators):
                logger.info(
                    "Guardrail zeroed score for objective/True-False question with negative feedback: "
                    "score was %s, feedback='%s'", score, feedback
                )
                score = 0.0
        elif score > 0.0:
            explicit_zero_phrases = ["is incorrect", "completely wrong", "factually wrong", "answer is false", "statement is false"]
            if any(phrase in feedback_lower for phrase in explicit_zero_phrases) and ("correct" not in feedback_lower or "is incorrect" in feedback_lower):
                logger.info(
                    "Guardrail zeroed score due to feedback-score mismatch: "
                    "score was %s, feedback='%s'", score, feedback
                )
                score = 0.0

        # Clamp score to [0, maximum_marks]
        score = max(0.0, min(score, float(maximum_marks)))
        return ScoringResult(
            score=float(score),
            feedback=feedback,
            confidence=float(data.get("confidence", 0.8)),
        )

    except json.JSONDecodeError as exc:
        logger.warning("Evaluator JSON parse error: %s | raw=%s", exc, raw[:200])
        return ScoringResult(score=0.0, feedback=f"Scoring error (JSON parse): {exc}", confidence=0.0)
    except Exception as exc:
        logger.error("Evaluator LLM error: %s", exc)
        return ScoringResult(score=0.0, feedback=f"Scoring error: {exc}", confidence=0.0)
