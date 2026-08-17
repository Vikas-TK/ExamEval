"""
Phase 5 – Completeness Agent
Evaluates Topic Coverage, Key Concept Coverage, Keywords, Expected Structure, and Missing Points ONLY.
Ignores Technical Correctness, Depth, and Grammar.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from app.core.config import get_settings
from app.phase4_context.schemas import EvaluationContextOut

logger = logging.getLogger(__name__)
settings = get_settings()


async def evaluate_completeness(ctx: EvaluationContextOut) -> Dict[str, Any]:
    """
    Completeness Agent Evaluation.
    Evaluates strictly answer coverage, required keywords, and missing concepts.
    """
    question_text = ctx.question_text or ""
    student_answer = ctx.student_answer or ""
    max_marks = float(ctx.maximum_marks or 5.0)
    keywords = ctx.keywords or []
    key_concepts = ctx.key_concepts or []
    expected_coverage = ctx.expected_coverage or ""

    if not student_answer.strip():
        return {
            "score": 0.0,
            "percentage": 0.0,
            "confidence": 1.0,
            "covered_points": [],
            "missing_points": ["Entire answer is missing."],
            "missing_keywords": keywords,
            "missing_concepts": key_concepts,
            "remarks": "No response provided. Completeness is 0%.",
            "status": "COMPLETED",
        }

    try:
        from app.ocr_engine import openai_client
        if openai_client:
            prompt = (
                "You are an expert Educational Completeness & Topic Coverage Evaluation Agent.\n"
                "Your job is to evaluate ONLY topic coverage, required keywords, expected answer structure, "
                "and identify missing concepts in the student's answer.\n"
                "IGNORE technical correctness, depth, and presentation.\n"
                "STRICT RULE: A keyword or concept counts as COVERED if it (or a clear paraphrase) is "
                "mentioned ANYWHERE in the student's answer, even if the surrounding explanation is "
                "factually wrong or misused — correctness is judged by a different agent, not you. "
                "Only list something under missing_points / missing_keywords / missing_concepts if it "
                "is genuinely absent from the answer text. Example: if the answer text contains the word "
                "'SYN' anywhere, 'SYN' is covered, even if the student misuses it.\n\n"
                f"Question: \"{question_text}\"\n"
                f"Maximum Marks: {max_marks}\n"
                f"Expected Coverage: \"{expected_coverage}\"\n"
                f"Target Keywords: {json.dumps(keywords)}\n"
                f"Student Answer: \"{student_answer}\"\n\n"
                "Respond ONLY with a valid JSON object matching this schema:\n"
                "{\n"
                f"  \"score\": <float between 0.0 and {max_marks}>,\n"
                "  \"percentage\": <float between 0.0 and 100.0>,\n"
                "  \"confidence\": <float between 0.0 and 1.0>,\n"
                "  \"covered_points\": [<strings>],\n"
                "  \"missing_points\": [<strings>],\n"
                "  \"missing_keywords\": [<strings>],\n"
                "  \"missing_concepts\": [<strings>],\n"
                "  \"remarks\": \"<concise completeness evaluation summary>\"\n"
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
                "covered_points": parsed.get("covered_points", []),
                "missing_points": parsed.get("missing_points", []),
                "missing_keywords": parsed.get("missing_keywords", []),
                "missing_concepts": parsed.get("missing_concepts", []),
                "remarks": str(parsed.get("remarks", "Completeness evaluated.")),
                "status": "COMPLETED",
            }
    except Exception as exc:
        logger.warning("Completeness agent LLM evaluation failed, using rule fallback: %s", exc)

    # Fallback Rule-Based Completeness Evaluation
    found_keywords = [k for k in keywords if k.lower() in student_answer.lower()]
    missing_keywords = [k for k in keywords if k.lower() not in student_answer.lower()]
    ratio = (len(found_keywords) / len(keywords)) if keywords else 0.75
    score = round(max_marks * ratio, 2)
    pct = round((score / max_marks * 100.0), 2) if max_marks > 0 else 0.0

    return {
        "score": score,
        "percentage": pct,
        "confidence": 0.8,
        "covered_points": found_keywords,
        "missing_points": missing_keywords[:3],
        "missing_keywords": missing_keywords,
        "missing_concepts": [c for c in key_concepts if c.lower() not in student_answer.lower()],
        "remarks": f"Answer covers {len(found_keywords)} out of {len(keywords)} required keywords.",
        "status": "COMPLETED",
    }
