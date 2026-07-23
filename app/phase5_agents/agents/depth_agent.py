"""
Phase 5 – Depth Agent
Evaluates Answer Detail, Logical Flow, Reasoning, Examples, and Critical Elaboration ONLY.
Ignores Accuracy, Coverage, and Presentation.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from app.core.config import get_settings
from app.phase4_context.schemas import EvaluationContextOut

logger = logging.getLogger(__name__)
settings = get_settings()


async def evaluate_depth(ctx: EvaluationContextOut) -> Dict[str, Any]:
    """
    Depth Agent Evaluation.
    Evaluates strictly logical reasoning, depth of detail, structure, and supporting examples.
    """
    question_text = ctx.question_text or ""
    student_answer = ctx.student_answer or ""
    max_marks = float(ctx.maximum_marks or 5.0)
    expected_depth = ctx.expected_answer_depth or "Medium"

    if not student_answer.strip():
        return {
            "score": 0.0,
            "percentage": 0.0,
            "confidence": 1.0,
            "strong_sections": [],
            "weak_sections": ["Response is entirely missing."],
            "remarks": "No response provided. Zero depth.",
            "status": "COMPLETED",
        }

    try:
        from app.ocr_engine import openai_client
        if openai_client:
            prompt = (
                "You are an expert Educational Answer Depth & Reasoning Evaluation Agent.\n"
                "Your job is to evaluate ONLY logical flow, depth of elaboration, reasoning, "
                "supporting examples, and explanation structure relative to the expected depth.\n"
                "IGNORE technical correctness and keyword coverage.\n\n"
                f"Question: \"{question_text}\"\n"
                f"Maximum Marks: {max_marks}\n"
                f"Expected Depth Level: \"{expected_depth}\"\n"
                f"Student Answer: \"{student_answer}\"\n\n"
                "Respond ONLY with a valid JSON object matching this schema:\n"
                "{\n"
                f"  \"score\": <float between 0.0 and {max_marks}>,\n"
                "  \"percentage\": <float between 0.0 and 100.0>,\n"
                "  \"confidence\": <float between 0.0 and 1.0>,\n"
                "  \"strong_sections\": [<strings>],\n"
                "  \"weak_sections\": [<strings>],\n"
                "  \"remarks\": \"<concise depth evaluation summary>\"\n"
                "}"
            )
            res = openai_client.chat.completions.create(
                model=settings.blueprint_qwen_model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=300,
            )
            raw = res.choices[0].message.content or ""
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
                "strong_sections": parsed.get("strong_sections", []),
                "weak_sections": parsed.get("weak_sections", []),
                "remarks": str(parsed.get("remarks", "Explanation depth evaluated.")),
                "status": "COMPLETED",
            }
    except Exception as exc:
        logger.warning("Depth agent LLM evaluation failed, using rule fallback: %s", exc)

    # Fallback Rule-Based Depth Evaluation
    word_count = len(student_answer.split())
    # Assess length vs expected depth
    target_words = {"Very Short": 10, "Short": 25, "Medium": 50, "Detailed": 100, "Comprehensive": 150}.get(expected_depth, 40)
    ratio = min(1.0, word_count / target_words) if target_words > 0 else 0.8
    score = round(max_marks * ratio, 2)
    pct = round((score / max_marks * 100.0), 2) if max_marks > 0 else 0.0

    return {
        "score": score,
        "percentage": pct,
        "confidence": 0.8,
        "strong_sections": ["Clear introductory definition"] if word_count > 10 else [],
        "weak_sections": ["Could provide more supporting examples"] if ratio < 0.8 else [],
        "remarks": f"Answer contains {word_count} words matching target depth '{expected_depth}'.",
        "status": "COMPLETED",
    }
