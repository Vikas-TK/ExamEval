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
    # Handwritten OCR fixes for Software Engineering & CS terms
    (re.compile(r"\bSfructlredactivitie\b", re.I), "Structured activities"),
    (re.compile(r"\bSfructlred\b", re.I), "Structured"),
    (re.compile(r"\bactivitie\b", re.I), "activities"),
    (re.compile(r"\bHootevelop\b", re.I), "to develop"),
    (re.compile(r"\banol\b", re.I), "and"),
    (re.compile(r"\bmaindaln\b", re.I), "maintain"),
    (re.compile(r"\bsofware\b", re.I), "software"),
    (re.compile(r"\bCnidied\s+modelin\b", re.I), "Unified modeling"),
    (re.compile(r"\bCnidied\b", re.I), "Unified"),
    (re.compile(r"\bmodelin\b", re.I), "modeling"),
    (re.compile(r"\bLanguagp\b", re.I), "Language"),
    (re.compile(r"\bvalidation\s+ahd\b", re.I), "validation and"),
    (re.compile(r"\bahd\b", re.I), "and"),
    (re.compile(r"\bAgileConceets\b", re.I), "Agile concepts"),
    (re.compile(r"\bConceets\b", re.I), "concepts"),
    (re.compile(r"\bSeromrotes\b", re.I), "Scrum roles"),
    (re.compile(r"\batifeicts\b", re.I), "artifacts"),
    (re.compile(r"\brin\+lanning\b", re.I), "sprint planning"),
    (re.compile(r"\brin\+lanningdaily\b", re.I), "sprint planning daily"),
    (re.compile(r"\bcrum\b", re.I), "scrum"),
    (re.compile(r"\bretroplctive\b", re.I), "retrospective"),
    (re.compile(r"\bburh-douchartano\b", re.I), "burn-down chart and"),
    (re.compile(r"\bburh-dow\b", re.I), "burn-down"),
    (re.compile(r"\bchartano\b", re.I), "chart and"),

    # Common handwritten & printed OCR fixes
    (re.compile(r"\btv['’`]u\b", re.I), "two"),
    (re.compile(r"\btvu\b", re.I), "two"),
    (re.compile(r"\bqf\b", re.I), "of"),
    (re.compile(r"\bjQuer\s*y\b", re.I), "jQuery"),
    (re.compile(r"\bJava\s*Script\b", re.I), "JavaScript"),
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


def correct_ocr_text(raw_text: str, enable_llm: bool = True) -> str:
    """
    Apply deterministic post-correction rules and Qwen LLM contextual smoothing
    to transform garbled handwritten OCR outputs into meaningful, legible English text.
    """
    if not raw_text or not raw_text.strip():
        return raw_text

    text = raw_text
    # 1. Apply rule-based replacements
    for pattern, replacement in _REPLACEMENT_RULES:
        text = pattern.sub(replacement, text)

    # 2. Fix spaces before/after punctuation
    text = re.sub(r"\s+([,.:;?!])", r"\1", text)
    text = re.sub(r"([,.:;?!])([a-zA-Z])", r"\1 \2", text)

    # 3. If LLM smoothing requested and enabled
    if enable_llm:
        text = smooth_ocr_with_llm(text)

    return text.strip()


def smooth_ocr_with_llm(raw_text: str) -> str:
    """
    Pass raw OCR output to Qwen LLM for intelligent contextual spelling & word-level restoration
    of handwritten exam scripts.
    """
    try:
        from app.ocr_engine import openai_client
        if not openai_client:
            return raw_text

        system_prompt = (
            "You are an expert Qwen2.5-VL OCR post-correction and handwriting restoration engine for computer science exam scripts. "
            "Your task is to take garbled handwritten OCR outputs (e.g. 'Sfructlredactivitie Hootevelop' -> 'Structured activities to develop', "
            "'Cnidied modelin Languagp' -> 'Unified modeling Language', 'AgileConceets Seromrotes' -> 'Agile concepts, Scrum roles') "
            "and restore each misspelled or merged word into clear, meaningful, grammatically correct English technical terms.\n"
            "CRITICAL DIRECTIVES:\n"
            "1. Fix obvious handwriting misspellings, typos, and word splits/merges.\n"
            "2. Preserve original technical concepts, question numbers, and bullet structures.\n"
            "3. Output ONLY the restored clean plain text without markdown wrappers."
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
