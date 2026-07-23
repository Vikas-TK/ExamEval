"""
Phase 1-3 OCR Contextual Post-Correction Engine.

Slightly modifies OCR words based on context to eliminate OCR errors from scanned 
handwriting and printed question papers (e.g. 'tv'u' -> 'two', 'qf' -> 'of', 
'manipolation' -> 'manipulation', 'I-commerce' -> 'E-commerce', 'Notatiom' -> 'Notation', 
'seruer' -> 'server', 'simplig' -> 'simplify') without altering original meaning or student intent.
"""
from __future__ import annotations

import re
import logging
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_REPLACEMENT_RULES: list[tuple[re.Pattern[str], str]] = [
    # Question paper OCR fixes
    (re.compile(r"\btv['’`]u\b", re.I), "two"),
    (re.compile(r"\btvu\b", re.I), "two"),
    (re.compile(r"\bqf\b", re.I), "of"),
    (re.compile(r"\bjQuer\s*y\b", re.I), "jQuery"),
    (re.compile(r"\bJava\s*Script\b", re.I), "JavaScript"),
    
    # Common handwritten OCR fixes
    (re.compile(r"\bI-commerce\b", re.I), "E-commerce"),
    (re.compile(r"\bi-commerce\b", re.I), "E-commerce"),
    (re.compile(r"\bmanipolation\b", re.I), "manipulation"),
    (re.compile(r"\bNotatiom\b", re.I), "Notation"),
    (re.compile(r"\bseruer\b", re.I), "server"),
    (re.compile(r"\btext\s*-\s*based\b", re.I), "text-based"),
    (re.compile(r"\binterch\s*ange\b", re.I), "interchange"),
    (re.compile(r"\blightweighta\b", re.I), "lightweight"),
    (re.compile(r"\bused\s+to\s+simplig\b", re.I), "used to simplify"),
    (re.compile(r"\bsimplig\b", re.I), "simplify"),
    (re.compile(r"\bdata\s+interchange\s+data\s+between\b", re.I), "data interchange format between"),
    (re.compile(r"\bdata\s+interchange\s+data\b", re.I), "data interchange format"),
    (re.compile(r"\bd\s+ocument\b", re.I), "document"),
    (re.compile(r"\bm\s+anipulation\b", re.I), "manipulation"),
    (re.compile(r"\be\s+vent\b", re.I), "event"),
    (re.compile(r"\ba\s+nimation\b", re.I), "animation"),
]


def correct_ocr_text(raw_text: str, enable_llm: bool = False) -> str:
    """
    Apply deterministic dictionary post-correction rules to fix common handwritten
    and printed OCR mistakes while preserving exact meaning and question anchors.
    """
    if not raw_text or not raw_text.strip():
        return raw_text

    text = raw_text
    # 1. Apply rule-based replacements
    for pattern, replacement in _REPLACEMENT_RULES:
        text = pattern.sub(replacement, text)

    # 2. Fix spaces before punctuation
    text = re.sub(r"\s+([,.:;?!])", r"\1", text)
    text = re.sub(r"([,.:;?!])([a-zA-Z])", r"\1 \2", text)

    # 3. If LLM smoothing requested and enabled
    if enable_llm:
        text = smooth_ocr_with_llm(text)

    return text.strip()


def smooth_ocr_with_llm(raw_text: str) -> str:
    """
    Pass raw text to local LLM (Qwen2.5-7B) for intelligent contextual spelling
    and grammar error correction without altering student answer meaning or structure.
    """
    try:
        from app.ocr_engine import openai_client
        if not openai_client:
            return raw_text

        system_prompt = (
            "You are an expert OCR post-correction system for handwritten exam scripts. "
            "Slightly correct obvious OCR spelling mistakes, split merged words, or broken letters "
            "(e.g. 'tv'u' -> 'two', 'qf' -> 'of', 'manipolation' -> 'manipulation', 'I-commerce' -> 'E-commerce', "
            "'Notatiom' -> 'Notation', 'seruer' -> 'server') based on context. "
            "CRITICAL DIRECTIVES:\n"
            "1. DO NOT rephrase sentences or add missing concepts.\n"
            "2. DO NOT delete question numbers or bullet points.\n"
            "3. Return ONLY the corrected plain text."
        )

        response = openai_client.chat.completions.create(
            model=settings.qwen_model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": raw_text}
            ],
            temperature=0.0,
            max_tokens=2048,
        )
        corrected = response.choices[0].message.content or raw_text
        if corrected.startswith("```"):
            corrected = "\n".join(corrected.splitlines()[1:-1])
        return corrected.strip()
    except Exception as exc:
        logger.warning("LLM OCR smoothing fallback skipped: %s", exc)
        return raw_text
