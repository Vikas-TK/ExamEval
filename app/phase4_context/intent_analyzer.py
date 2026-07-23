"""
Phase 4 – Question Intent Analyzer
Identifies the examiner's pedagogical intent for each question using Rule-Based NLP & Qwen2.5-3B Fallback.
"""
from __future__ import annotations

import re
import logging
from typing import Optional

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_INTENT_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\b(define|definition|what is|meaning of|state|name)\b", re.I), "Definition"),
    (re.compile(r"\b(difference|differentiate|distinguish|versus|vs\.?)\b", re.I), "Difference"),
    (re.compile(r"\b(compare|comparison|contrast)\b", re.I), "Comparison"),
    (re.compile(r"\b(advantage|pros|merit|benefit)\b", re.I), "Advantages"),
    (re.compile(r"\b(disadvantage|cons|demerit|drawback|limitation)\b", re.I), "Disadvantages"),
    (re.compile(r"\b(list|enumerate|mention|give any)\b", re.I), "List"),
    (re.compile(r"\b(algorithm|pseudo\s*code|steps to)\b", re.I), "Algorithm"),
    (re.compile(r"\b(write a program|code|implement|function|class|java|python|c\+\+)\b", re.I), "Programming"),
    (re.compile(r"\b(draw|diagram|sketch|schematic|architecture|component)\b", re.I), "Diagram"),
    (re.compile(r"\b(flowchart|flow diagram)\b", re.I), "Flowchart"),
    (re.compile(r"\b(derive|derivation|prove|proof)\b", re.I), "Mathematical Derivation"),
    (re.compile(r"\b(calculate|compute|find the value|evaluate|numerical|solve for)\b", re.I), "Numerical Problem"),
    (re.compile(r"\b(formula|expression|equation)\b", re.I), "Formula"),
    (re.compile(r"\b(case study|scenario|real-world|application|apply|where is)\b", re.I), "Application"),
    (re.compile(r"\b(why|reason|explain why|justify)\b", re.I), "Reasoning"),
    (re.compile(r"\b(solve|problem|troubleshoot)\b", re.I), "Problem Solving"),
    (re.compile(r"\b(essay|discuss in detail|elaborate|overview)\b", re.I), "Essay"),
    (re.compile(r"\b(explain|describe|discuss|illustrate)\b", re.I), "Explanation"),
]


def detect_question_intent(question_text: str) -> str:
    """
    Detects pedagogical question intent using NLP rule-based matching with LLM fallback.
    """
    if not question_text or not question_text.strip():
        return "Explanation"

    text = question_text.strip()

    # 1. Rule-based matching
    for pattern, intent in _INTENT_RULES:
        if pattern.search(text):
            return intent

    # 2. Qwen2.5-3B Fallback when confidence is low
    try:
        from app.ocr_engine import openai_client
        if openai_client:
            prompt = (
                "You are an educational assessment question intent analyzer. "
                "Classify the intent of this question into EXACTLY ONE of: "
                "Definition, Explanation, Comparison, Advantages, Disadvantages, Difference, List, "
                "Short Answer, Essay, Case Study, Algorithm, Programming, Diagram, Flowchart, "
                "Mathematical Derivation, Numerical Problem, Formula, Application, Reasoning, Problem Solving.\n\n"
                f"Question: \"{text}\"\n"
                "Return ONLY the single intent string."
            )
            res = openai_client.chat.completions.create(
                model=settings.blueprint_qwen_model_name,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=20,
            )
            val = res.choices[0].message.content or ""
            val_clean = val.strip().strip('"').strip("'")
            if val_clean:
                return val_clean
    except Exception as exc:
        logger.warning("LLM intent detection fallback failed for question: %s", exc)

    return "Explanation"
