"""
Phase 5 – Accuracy Agent
Evaluates Technical Correctness, Concepts, Definitions, Formulas, Code Logic, and Terminology ONLY.
Ignores Coverage, Depth, and Presentation.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from app.core.config import get_settings
from app.phase4_context.schemas import EvaluationContextOut

logger = logging.getLogger(__name__)
settings = get_settings()


async def evaluate_accuracy(ctx: EvaluationContextOut) -> Dict[str, Any]:
    """
    Accuracy Agent Evaluation.
    Evaluates strictly technical correctness and accuracy against Key Concepts.
    """
    question_text = ctx.question_text or ""
    student_answer = ctx.student_answer or ""
    max_marks = float(ctx.maximum_marks or 5.0)
    key_concepts = ctx.key_concepts or []

    # If student answer is empty
    if not student_answer.strip():
        return {
            "score": 0.0,
            "percentage": 0.0,
            "confidence": 1.0,
            "correct_concepts": [],
            "incorrect_concepts": key_concepts,
            "technical_errors": ["No answer provided by student."],
            "remarks": "Blank response. Zero technical accuracy.",
            "status": "COMPLETED",
        }

    # Attempt LLM evaluation
    try:
        from app.ocr_engine import openai_client
        if openai_client:
            prompt = (
                "You are an expert Educational Technical Accuracy Evaluation Agent.\n"
                "Your job is to evaluate ONLY technical correctness, concept accuracy, definitions, "
                "formulas, code logic, and technical terminology in the student's answer.\n"
                "IGNORE coverage, answer length, depth, and presentation.\n"
                "STRICT RULE: A concept that is simply ABSENT from the answer is NOT a technical error "
                "and must NOT appear in technical_errors or incorrect_concepts — that is a coverage gap, "
                "which is scored by a different agent. Only flag a concept as incorrect if the student "
                "actually stated it and got it WRONG. A short or incomplete answer that contains zero "
                "wrong statements should score close to full marks here.\n\n"
                f"Question: \"{question_text}\"\n"
                f"Maximum Marks: {max_marks}\n"
                f"Key Concepts: {json.dumps(key_concepts)}\n"
                f"Student Answer: \"{student_answer}\"\n\n"
                "Respond ONLY with a valid JSON object matching this schema:\n"
                "{\n"
                f"  \"score\": <float between 0.0 and {max_marks}>,\n"
                "  \"percentage\": <float between 0.0 and 100.0>,\n"
                "  \"confidence\": <float between 0.0 and 1.0>,\n"
                "  \"correct_concepts\": [<strings>],\n"
                "  \"incorrect_concepts\": [<strings>],\n"
                "  \"technical_errors\": [<strings>],\n"
                "  \"remarks\": \"<concise technical evaluation summary>\"\n"
                "}"
            )
            res = openai_client.chat.completions.create(
                model=settings.blueprint_qwen_model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=300,
            )
            raw = res.choices[0].message.content or ""
            # Strip code fences if present
            raw_clean = raw.strip()
            if raw_clean.startswith("```"):
                lines = raw_clean.splitlines()
                raw_clean = "\n".join(lines[1:-1]) if len(lines) >= 3 else ""

            parsed = json.loads(raw_clean)
            score = max(0.0, min(max_marks, float(parsed.get("score", 0.0))))
            pct = (score / max_marks * 100.0) if max_marks > 0 else 0.0
            return {
                "score": round(score, 2),
                "percentage": round(pct, 2),
                "confidence": max(0.0, min(1.0, float(parsed.get("confidence", 0.9)))),
                "correct_concepts": parsed.get("correct_concepts", []),
                "incorrect_concepts": parsed.get("incorrect_concepts", []),
                "technical_errors": parsed.get("technical_errors", []),
                "remarks": str(parsed.get("remarks", "Technical accuracy evaluated.")),
                "status": "COMPLETED",
            }
    except Exception as exc:
        logger.warning("Accuracy agent LLM evaluation failed, using rule fallback: %s", exc)

    # Fallback Rule-Based Accuracy Evaluation
    found_concepts = [c for c in key_concepts if c.lower() in student_answer.lower()]
    missing_concepts = [c for c in key_concepts if c.lower() not in student_answer.lower()]
    ratio = (len(found_concepts) / len(key_concepts)) if key_concepts else 0.8
    score = round(max_marks * ratio, 2)
    pct = round((score / max_marks * 100.0), 2) if max_marks > 0 else 0.0

    return {
        "score": score,
        "percentage": pct,
        "confidence": 0.8,
        "correct_concepts": found_concepts,
        "incorrect_concepts": missing_concepts,
        "technical_errors": [],
        "remarks": f"Extracted {len(found_concepts)}/{len(key_concepts)} correct technical concepts.",
        "status": "COMPLETED",
    }
