from __future__ import annotations

import io
import json
import logging
import re
from typing import Any

from app.ocr_engine import openai_client

from app.blueprint_schemas import BlueprintQuestion, BlueprintSection, ExamMetadata
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

_SECTION_RE = re.compile(r"(?im)^\s*((?:part|section)\s+[a-z0-9ivx]+|part\s+[a-z])\s*[:\-]?\s*(.*)$")
_QUESTION_RE = re.compile(
    r"(?m)^\s*(?:Q(?:uestion)?\.?\s*)?(\d{1,3}(?:\s*[a-z])?)[.)]\s+(.+?)"
    r"(?=\n\s*(?:Q(?:uestion)?\.?\s*)?\d{1,3}(?:\s*[a-z])?[.)]\s+|\Z)",
    re.S | re.I,
)
_MARKS_RE = re.compile(
    r"(?:\((\d+(?:\.\d+)?)\s*marks?\)|\[(\d+(?:\.\d+)?)\]|"
    r"\b(\d+(?:\.\d+)?)\s*marks?\b)", re.I
)


def _normalize_qno(value: str) -> str:
    """Strip any Q/Question prefix so question numbers compare equal regardless of source formatting."""
    return re.sub(r"(?i)^q(?:uestion)?\.?\s*", "", value.strip()).replace(" ", "").lower()

def extract_metadata(ocr: dict[str, Any]) -> ExamMetadata:
    """Extract labelled metadata from the OCR transcript."""
    text = _page_text(ocr)

    def value(label: str) -> str | None:
        match = re.search(rf"(?im)^\s*{label}\s*[:\-]\s*(.+?)\s*$", text)
        return match.group(1).strip() if match else None

    duration = value("duration") or value("time")
    marks = value("maximum marks") or value("max marks") or value("marks")
    if not duration or not marks:
        raise ValueError("OCR must contain labelled Duration and Maximum Marks metadata")
    duration_match = re.search(r"\d+", duration)
    marks_match = re.search(r"\d+(?:\.\d+)?", marks)
    if not duration_match or not marks_match:
        raise ValueError("Duration and Maximum Marks metadata must contain numeric values")
    metadata = ExamMetadata(
        exam_name=value("exam name") or value("examination") or "Examination",
        subject=value("subject") or _required("Subject"),
        subject_code=value("subject code") or value("code") or _required("Subject Code"),
        regulation=value("regulation") or _required("Regulation"),
        semester=value("semester") or _required("Semester"),
        department=value("department") or _required("Department"),
        duration_minutes=int(duration_match.group()),
        maximum_marks=float(marks_match.group()),
    )
    return metadata


def _required(label: str) -> str:
    raise ValueError(f"OCR is missing required metadata: {label}")


def _page_text(ocr: dict[str, Any]) -> str:
    pages = ocr.get("pages", [])
    return "\n".join(str(page.get("transcript", "")) for page in pages if isinstance(page, dict))


_EXPLICIT_Q_START = re.compile(
    r"(?im)^\s*(?:Q(?:uestion)?\.?\s*(\d+[a-z]?)|(\d+[a-z]?)\s*[\.\)])\s*(.*)$"
)

_IGNORE_HEADER_PATTERNS = [
    r"study\s+questions", r"answer\s+all\s+questions", r"part\s+[a-z0-9]", r"section\s+[a-z0-9]",
    r"maximum\s+marks", r"duration\s*:", r"end\s+semester", r"examination", r"subject\s+code"
]


def _is_header_or_noise(line: str) -> bool:
    line_clean = line.strip().lower()
    if not line_clean:
        return True
    for pat in _IGNORE_HEADER_PATTERNS:
        if re.search(pat, line_clean):
            return True
    return False


def _question_type(text: str) -> str:
    lowered = text.lower()
    if any(word in lowered for word in ("option a", "option b", "(a)", "(b)", "choose", "select", "mcq")):
        return "MCQ"
    if any(word in lowered for word in ("calculate", "compute", "find the value", "solve", "evaluate")):
        return "Numerical"
    if any(word in lowered for word in ("define", "state", "list", "name", "what is", "give")):
        return "Short Answer"
    if any(word in lowered for word in ("explain", "describe", "discuss", "derive", "elaborate", "compare")):
        return "Descriptive"
    if any(word in lowered for word in ("draw", "diagram", "sketch", "plot", "schematic")):
        return "Diagram"
    return "Descriptive"


_MARKS_RE = re.compile(
    r"(?:\((\d+(?:\.\d+)?)\s*(?:marks?|m)?\)|\[(\d+(?:\.\d+)?)\s*(?:marks?|m)?\]|\b(\d+(?:\.\d+)?)\s*marks?\b|\b(\d+(?:\.\d+)?)\s*m\b)",
    re.I
)
_TRAILING_NUM_RE = re.compile(r"[\(\[]\s*(\d+(?:\.\d+)?)\s*[\)\]]\s*$", re.I)


def _marks(text: str) -> float:
    match = _MARKS_RE.search(text)
    if match:
        val = next((v for v in match.groups() if v is not None), None)
        if val:
            return float(val)
    match_trailing = _TRAILING_NUM_RE.search(text.strip())
    if match_trailing:
        return float(match_trailing.group(1))
    return 5.0


def _clean_question(text: str) -> str:
    return re.sub(r"\s+", " ", _MARKS_RE.sub("", text)).strip(" .-:;\n")


def preprocess_ocr_text(text: str) -> str:
    """
    Preprocess OCR text to insert newlines before inline question numbers
    that were merged into a single line/paragraph by OCR.
    Ignores mark allocations like [28 marks], (2 marks), 10m.
    """
    from app.ocr_corrector import correct_ocr_text
    text = correct_ocr_text(text)

    pattern = re.compile(
        r"([.?!;\n]|\b\s*)(?:Q(?:uestion)?\.?\s*)?(\d{1,3})\s*([\.\)\(]|[a-zA-Z]{2,})",
        re.IGNORECASE
    )
    def replacer(match):
        prefix = match.group(1)
        q_num = match.group(2)
        following = match.group(3)

        # Skip mark allocations like "28 marks", "2 marks", "10m"
        context_after = text[match.end(2):match.end(2) + 20].lower()
        if re.match(r"\s*(?:marks?|m)\b", context_after):
            return match.group(0)

        if not prefix.strip() and not any(p in prefix for p in ".?!;\n"):
            if following.isalpha() and len(following) > 2:
                return f"{prefix}\nQ{q_num}. {following}"
            if following in ('.', ')'):
                return f"{prefix}\nQ{q_num}{following} "
            return match.group(0)

        if following in ('.', ')'):
            return f"{prefix.strip()}\nQ{q_num}. "
        elif following == '(':
            return f"{prefix.strip()}\nQ{q_num} ("
        elif following.isalpha():
            return f"{prefix.strip()}\nQ{q_num}. {following}"
        else:
            return f"{prefix.strip()}\nQ{q_num}. "

    return pattern.sub(replacer, text)


_SECTION_HEADER_RE = re.compile(
    r"(?m)^\s*((?i:Part|Section))\s*([IVXLCDM]{1,4}|[A-Z]|\d{1,2})(?![a-zA-Z])"
    r"\s*(?:[\-\:]\s*(\d+(?:\.\d+)?)\s*marks?)?.*$"
)


def _find_per_question_marks(text: str) -> float | None:
    """
    Extract the PER-QUESTION mark value from a section header/instruction
    line, distinguishing it from the section's total. A pattern like
    "(7 x 4 = 28 marks)" or "(12*0.5=6 Marks)" states count x per-question =
    total — the value we want is the per-question one (4 / 0.5), not the
    total that sits right next to the word "marks" (28 / 6), which a naive
    "\\d+ marks" search would grab. Papers use 'x', '×', or '*' interchangeably
    as the multiplication sign here.
    """
    m = re.search(r"(\d+)\s*[x×*]\s*(\d+(?:\.\d+)?)\s*=\s*\d+(?:\.\d+)?\s*marks?", text, re.I)
    if m:
        return float(m.group(2))
    m = re.search(r"(\d+(?:\.\d+)?)\s*marks?\s*each\b", text, re.I)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d+(?:\.\d+)?)\s*marks", text, re.I)
    if m:
        return float(m.group(1))
    return None


def _regex_sections(text: str) -> list[BlueprintSection]:
    text = preprocess_ocr_text(text)
    lines = text.splitlines()
    sections: list[BlueprintSection] = []

    current_section_name = "Part A"
    current_section_marks = 2.0
    current_section_instructions = None

    current_q_no = None
    current_q_lines = []
    current_questions: list[BlueprintQuestion] = []

    def save_current_question():
        nonlocal current_q_no, current_q_lines
        if current_q_no and current_q_lines:
            raw_combined = " ".join(current_q_lines)
            marks_found = _marks(raw_combined)
            # If question has no explicit mark or found mark is section total (e.g. 28 marks in Part A), cap with section mark allocation
            if current_section_marks > 0 and (marks_found == 5.0 or marks_found > (current_section_marks * 2.5)):
                marks_found = current_section_marks

            cleaned = _clean_question(raw_combined)
            # Discard phantom questions: OCR noise sometimes produces a bare
            # digit+bracket ("20)") with no real text behind it — a genuine
            # question always has actual wording, not just punctuation.
            if cleaned and re.search(r"[A-Za-z]{2,}", cleaned):
                q_num_clean = str(current_q_no).strip()
                if not q_num_clean.lower().startswith("q"):
                    q_num_clean = f"Q{q_num_clean}"
                current_questions.append(BlueprintQuestion(
                    question_id=f"q-{q_num_clean.lower()}",
                    question_number=q_num_clean,
                    question_text=cleaned,
                    maximum_marks=marks_found,
                    question_type=_question_type(cleaned),
                    question_order=len(current_questions) + 1,
                ))

    def save_current_section():
        nonlocal current_questions, current_section_name, current_section_instructions
        if current_questions:
            sections.append(BlueprintSection(
                section_id=f"section-{len(sections) + 1}",
                name=current_section_name,
                instructions=current_section_instructions,
                questions=list(current_questions),
            ))
            current_questions.clear()

    for idx, line in enumerate(lines):
        sec_match = _SECTION_HEADER_RE.match(line)
        if sec_match:
            save_current_question()
            current_q_no = None
            save_current_section()

            part_prefix = sec_match.group(1).title()
            part_letter = sec_match.group(2).upper()
            current_section_name = f"{part_prefix} {part_letter}"

            sec_marks_str = sec_match.group(3)
            if sec_marks_str:
                current_section_marks = float(sec_marks_str)
            else:
                found_marks = _find_per_question_marks(line)
                if found_marks is None:
                    # Per-question marks weren't stated on the header line
                    # itself — scan forward through any intro/instruction
                    # lines (e.g. "Short answer type questions: (7 x 4 = 28
                    # marks)" on its own line) but stop at the first real
                    # question or the next section boundary.
                    for lookahead in lines[idx + 1: idx + 6]:
                        if _EXPLICIT_Q_START.match(lookahead) or _SECTION_HEADER_RE.match(lookahead):
                            break
                        found_marks = _find_per_question_marks(lookahead)
                        if found_marks is not None:
                            break
                current_section_marks = found_marks if found_marks is not None else 2.0
            current_section_instructions = line.strip()
            continue

        match = _EXPLICIT_Q_START.match(line)
        if match:
            save_current_question()
            q_num = match.group(1) or match.group(2)
            rest_of_line = match.group(3) or ""
            current_q_no = q_num
            current_q_lines = [rest_of_line] if rest_of_line.strip() else []
        elif current_q_no is not None:
            if not _is_header_or_noise(line):
                current_q_lines.append(line.strip())

    save_current_question()
    save_current_section()

    return sections


def _qwen_fallback(text: str) -> list[BlueprintSection]:
    client = openai_client
    system_prompt = (
        "You are an expert document structure parser specializing in question paper blueprints. "
        "Your primary task is to extract question papers into structured JSON while preserving complete question context, "
        "correct numbering, and mark allocations.\n\n"
        "CRITICAL PARSING RULES:\n"
        "1. QUESTION BOUNDARY RECOGNITION: Identify a NEW question ONLY when an explicit question pattern is found (e.g., '1.', 'Q1', 'Q.1', 'Question 1'). "
        "Combine all multi-line text, continuous paragraphs, and wrapped lines into a SINGLE question_text.\n"
        "2. NOISE & HEADER FILTERING: Ignore instruction blocks, study references, metadata, or section titles.\n"
        "3. QUESTION NUMBERING & MARKS: Extract question_number exactly (e.g., 'Q1') and explicit mark values.\n"
        "4. QUESTION TYPE CLASSIFICATION: Classify each question accurately ('MCQ', 'Descriptive', 'Short Answer', 'Numerical', 'Diagram').\n"
        "5. VERBATIM TEXT ONLY: question_text must be copied exactly as printed. NEVER fill in blanks (e.g. '___________', "
        "'________') with the answer, NEVER answer the question, and NEVER add explanation not present in the source — "
        "a blank stays a blank, character for character.\n\n"
        "Return ONLY a JSON object with format: {\"sections\":[{\"name\":\"Part A\",\"questions\":[{\"question_number\":\"Q1\",\"question_text\":\"...\",\"maximum_marks\":5,\"question_type\":\"Descriptive\"}]}]}"
    )
    response = client.chat.completions.create(
        model=settings.qwen_model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ],
        temperature=0.0, max_tokens=4096,
    )
    raw = response.choices[0].message.content or ""
    if raw.startswith("```"):
        raw = "\n".join(raw.splitlines()[1:-1])
    data = json.loads(raw)
    sections = []
    for section_index, section in enumerate(data.get("sections", []), start=1):
        questions = []
        for order, question in enumerate(section.get("questions", []), start=1):
            number = str(question.get("question_number", f"Q{order}"))
            questions.append(BlueprintQuestion(
                question_id=f"section-{section_index}-{number.replace(' ', '')}",
                question_number=number,
                question_text=str(question.get("question_text", "")).strip(),
                maximum_marks=float(question.get("maximum_marks", 5)),
                question_type=_question_type(str(question.get("question_text", ""))),
                question_order=order,
            ))
        if questions:
            sections.append(BlueprintSection(
                section_id=f"section-{section_index}",
                name=str(section.get("name", f"Part {chr(64 + section_index)}")),
                instructions=section.get("instructions"),
                questions=questions,
            ))
    return sections


_FOOTER_MARKERS_RE = re.compile(
    r"(?im)^.*(?:staff\s*i\s*/\s*c|\bIQAC\b|(?<![a-z])PAC(?![a-z])|course\s+outcome|"
    r"CO\d+\s*:|cos?\s*/\s*level|levels?\s*:\s*understanding|bloom'?s?\s+taxonomy).*$"
)


def _strip_header_and_footer(text: str) -> str:
    """
    Institutional headers (college name, address, accreditation, date, reg
    no) and footers (staff sign-off, CO/PO Bloom's-taxonomy mapping tables)
    are packed with short numbers — dates, subject codes, pincodes — that
    the question-number detector (preprocess_ocr_text) mistakes for real
    question markers, slicing that noise into fake questions like "Q04."
    from a date or "Q21." from a subject code. Truncating to just the exam
    body — from the first real Part/Section heading through to the first
    footer marker — removes the noise source instead of trying to out-guess
    every possible false-positive number pattern within it.
    """
    body = text

    header_match = _SECTION_HEADER_RE.search(body)
    if not header_match:
        # No formal "Part X" heading found; fall back to the generic
        # "answer all/any questions" instruction as a weaker start signal.
        instr_match = re.search(r"(?im)^.*answer\s+(?:all|any)\s+.*question.*$", body)
        if instr_match:
            body = body[instr_match.start():]
    else:
        body = body[header_match.start():]

    footer_match = _FOOTER_MARKERS_RE.search(body)
    if footer_match:
        body = body[:footer_match.start()]

    return body


def extract_sections(ocr: dict[str, Any]) -> list[BlueprintSection]:
    text = _page_text(ocr)
    text = _strip_header_and_footer(text)
    sections = _regex_sections(text)
    if sections:
        return sections
    try:
        return _qwen_fallback(text)
    except Exception as exc:
        logger.warning("Qwen blueprint fallback failed: %s", exc)

    # Line/paragraph fallback so layout extraction never fails
    lines = [line.strip() for line in text.splitlines() if len(line.strip()) > 3]
    questions: list[BlueprintQuestion] = []
    for idx, line in enumerate(lines, start=1):
        questions.append(BlueprintQuestion(
            question_id=f"question-{idx}",
            question_number=str(idx),
            question_text=line,
            maximum_marks=5.0,
            question_type=_question_type(line),
            question_order=idx,
        ))

    if not questions:
        questions.append(BlueprintQuestion(
            question_id="question-1",
            question_number="1",
            question_text="Question Paper Document Content",
            maximum_marks=100.0,
            question_type="DESCRIPTIVE",
            question_order=1,
        ))

    return [BlueprintSection(section_id="section-1", name="Part A", instructions=None, questions=questions)]


def parse_answer_key(data: bytes, filename: str) -> dict[str, str]:
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix == "txt":
        text = data.decode("utf-8-sig")
    elif suffix == "docx":
        from docx import Document
        text = "\n".join(paragraph.text for paragraph in Document(io.BytesIO(data)).paragraphs)
    elif suffix == "pdf":
        from pypdf import PdfReader
        text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)
    else:
        raise ValueError("Answer key must be TXT, DOCX, or PDF")
    answers: dict[str, str] = {}
    matches = list(_QUESTION_RE.finditer(text))
    for index, match in enumerate(matches):
        number, answer = match.groups()
        answers[_normalize_qno(number)] = answer.strip()
    return answers


def attach_answer_key(sections: list[BlueprintSection], answers: dict[str, str]) -> list[BlueprintSection]:
    for section in sections:
        for question in section.questions:
            question.faculty_answer = answers.get(_normalize_qno(question.question_number))
    return sections


def validate_blueprint(metadata: ExamMetadata, sections: list[BlueprintSection]) -> None:
    questions = [question for section in sections for question in section.questions]
    if not questions:
        raise ValueError("Blueprint must contain at least one question")