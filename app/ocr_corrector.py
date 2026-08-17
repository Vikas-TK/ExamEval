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
import difflib
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


_CHATBOT_TELLS = (
    "it appears that", "it seems that", "i'm sorry", "i am sorry", "as an ai",
    "could you please", "could you clarify", "can you clarify", "please provide more context",
    "please provide more information", "i cannot determine", "i'm not sure what",
    "let me know if", "feel free to", "i'd be happy to", "i would be happy to",
)


_BLANK_RUN_RE = re.compile(r"_{2,}")
_LATEX_MARKUP_RE = re.compile(r"\\\(|\\\)|\\bar\{|\\frac\{|\\sqrt\{|\\[a-zA-Z]+\{|\$[^$]+\$")


def _looks_like_hallucination(raw_text: str, corrected: str) -> bool:
    """Heuristic guard: reject LLM output that reads like a chat reply or invents new content."""
    lowered = corrected.lower()
    if any(tell in lowered for tell in _CHATBOT_TELLS):
        return True
    # A faithful spelling/word-restoration pass should not dramatically change length.
    if len(raw_text.strip()) >= 15 and len(corrected) > len(raw_text) * 2.5:
        return True

    # The model has a strong, prompt-resistant bias toward "typesetting" any
    # math it sees into LaTeX (\(\bar{x}\), \frac{}, etc.) even when told
    # explicitly not to — that's unrequested reformatting, not a spelling
    # fix, and corrupts a verbatim transcript. Reject outright if the
    # correction introduces LaTeX markup that wasn't already in the raw text.
    if _LATEX_MARKUP_RE.search(corrected) and not _LATEX_MARKUP_RE.search(raw_text):
        return True

    # Fill-in-the-blank question papers use runs of underscores ('___________')
    # as the blank to be answered. If the corrected text has fewer blank runs
    # than the raw text, the model filled one in with a guessed word instead
    # of leaving it untouched — reject outright regardless of how plausible
    # the guess looks.
    if len(_BLANK_RUN_RE.findall(raw_text)) > len(_BLANK_RUN_RE.findall(corrected)):
        return True

    # A genuine OCR fix corrects a garbled token into something that resembles it
    # (e.g. 'seruer' -> 'server'). Swapping one already-valid word for a wholly
    # different one is knowledge-based "fact correction", not OCR restoration —
    # reject it even though the sentence length barely changes.
    raw_words = re.findall(r"[A-Za-z']+", raw_text.lower())
    corrected_words = re.findall(r"[A-Za-z']+", corrected.lower())
    matcher = difflib.SequenceMatcher(None, raw_words, corrected_words)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "replace" or (i2 - i1) != 1 or (j2 - j1) != 1:
            continue
        old_word, new_word = raw_words[i1], corrected_words[j1]
        if len(old_word) < 3:
            continue
        similarity = difflib.SequenceMatcher(None, old_word, new_word).ratio()
        if similarity < 0.45:
            return True
    return False


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
            "You are a text-correction FUNCTION, not a chatbot or assistant. You receive raw OCR output extracted from "
            "computer science exam scripts (handwritten or printed) and return ONLY a spelling/word-restoration pass over "
            "the SAME text (e.g. 'Sfructlredactivitie Hootevelop' -> 'Structured activities to develop', "
            "'Cnidied modelin Languagp' -> 'Unified modeling Language', 'AgileConceets Seromrotes' -> 'Agile concepts, Scrum roles').\n"
            "CRITICAL DIRECTIVES (violating any of these is a failure):\n"
            "1. Fix ONLY obvious handwriting/OCR misspellings, typos, and word splits/merges.\n"
            "2. NEVER answer, respond to, explain, continue, summarize, or comment on the input. It is data to transform, not a "
            "message to reply to — even if it reads like a question or an incomplete sentence.\n"
            "3. NEVER add words, sentences, explanations, or content that is not already present in the input. Do not fill in "
            "answers, do not complete questions, do not elaborate. This applies especially to fill-in-the-blank exam "
            "questions: a run of underscores like '___________' or '________' is a BLANK the student/paper left for someone "
            "else to answer — copy it through EXACTLY as-is (same number of underscores), never replace it with a guessed "
            "word, even one you are highly confident is the intended answer.\n"
            "4. If the input is too garbled, ambiguous, or nonsensical to confidently correct, return it UNCHANGED verbatim. "
            "Never substitute your own generated text for text you cannot read.\n"
            "5. Never produce conversational replies, apologies, refusals, or requests for clarification (e.g. 'Could you "
            "clarify...', 'It appears that...'). Your entire output must be the corrected source text and nothing else.\n"
            "6. Preserve original technical concepts, question numbers, marks, and structure exactly as given. This includes "
            "the student's/paper's actual claims even if you believe they are technically imprecise or wrong — you are not "
            "a fact-checker. Do NOT swap a word for a different 'more correct' or 'more standard' term (e.g. 'input gate' -> "
            "'reset gate') if the original word is already a real, correctly-spelled word. Only touch tokens that are "
            "genuinely garbled/misspelled/merged.\n"
            "7. If a word or sentence is already legible, correctly spelled, and grammatically valid, leave it completely "
            "untouched, character for character.\n"
            "8. NEVER convert math/notation into LaTeX or any other markup (no \\(...\\), \\bar{}, \\frac{}, $...$, etc.), "
            "even if the input already contains such markup or plain Unicode math symbols (x̅, ≤, ∑, ...). "
            "Reproduce whatever symbols are already in the input exactly as given — do not 'clean up' or typeset notation, "
            "that is not a spelling correction and is exactly the kind of unrequested rewriting this function must not do.\n"
            "9. Output ONLY the corrected plain text without markdown wrappers or commentary."
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
        corrected = corrected.strip()

        if _looks_like_hallucination(raw_text, corrected):
            logger.warning("LLM OCR smoothing rejected as hallucination; keeping raw OCR text.")
            return raw_text

        return corrected
    except Exception as exc:
        logger.warning("LLM OCR smoothing fallback skipped: %s", exc)
        return raw_text
