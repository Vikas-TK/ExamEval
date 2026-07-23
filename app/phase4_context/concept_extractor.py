"""
Phase 4 – Key Concept & Keyword Extractor
Extracts primary concepts, technical terminology, named entities, algorithms, and formulas.
"""
from __future__ import annotations

import re
import logging
from typing import Tuple, List

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "of", "in", "to", "for",
    "with", "on", "at", "by", "from", "up", "about", "into", "through", "during",
    "what", "how", "why", "where", "which", "who", "whom", "explain", "describe",
    "discuss", "list", "define", "state", "mention", "give", "write", "differentiate"
}


def extract_key_concepts_and_keywords(
    question_text: str,
    student_answer: str = ""
) -> Tuple[List[str], List[str]]:
    """
    Extracts key concepts and important keywords from question text and student answer.
    Fault-tolerant: Returns empty lists on failure rather than crashing.
    """
    if not question_text or not question_text.strip():
        return [], []

    try:
        combined = f"{question_text} {student_answer}".strip()

        # 1. NLP Rule-based token extraction
        words = re.findall(r"\b[A-Za-z0-9+#.\-]{3,}\b", combined)
        keywords = [
            w for w in words
            if w.lower() not in _STOP_WORDS and not w.isdigit()
        ]
        # Unique preserving order
        unique_keywords = list(dict.fromkeys(keywords))[:12]

        # Extract capitalized technical terms or multi-word phrases (e.g. "Data Structures", "jQuery", "JSON")
        phrases = re.findall(r"\b[A-Z][a-zA-Z0-9+#.\-]*(?:\s+[A-Z][a-zA-Z0-9+#.\-]*)*\b", question_text)
        primary_concepts = [p for p in phrases if p.lower() not in _STOP_WORDS and len(p) > 2]
        if not primary_concepts:
            primary_concepts = unique_keywords[:4]

        # LLM enrichment if Qwen is available
        try:
            from app.ocr_engine import openai_client
            if openai_client:
                prompt = (
                    "Extract 3-5 primary domain concepts and key technical terms from this question:\n"
                    f"Question: \"{question_text}\"\n"
                    "Return ONLY a comma-separated list of concepts."
                )
                res = openai_client.chat.completions.create(
                    model=settings.blueprint_qwen_model_name,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.0,
                    max_tokens=60,
                )
                raw = res.choices[0].message.content or ""
                llm_concepts = [c.strip() for c in raw.split(",") if c.strip() and len(c.strip()) > 2]
                if llm_concepts:
                    primary_concepts = list(dict.fromkeys(llm_concepts + primary_concepts))[:6]
        except Exception as exc:
            logger.debug("LLM concept enrichment skipped: %s", exc)

        return primary_concepts, unique_keywords

    except Exception as exc:
        logger.warning("Concept extraction failed: %s", exc)
        return [], []
