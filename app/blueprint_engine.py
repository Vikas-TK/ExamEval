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
_QUESTION_RE = re.compile(r"(?m)^\s*(\d{1,3}(?:\s*[a-z])?)[.)]\s+(.+?)(?=\n\s*\d{1,3}(?:\s*[a-z])?[.)]\s+|\Z)", re.S | re.I)
_MARKS_RE = re.compile(
    r"(?:\((\d+(?:\.\d+)?)\s*marks?\)|\[(\d+(?:\.\d+)?)\]|"
    r"\b(\d+(?:\.\d+)?)\s*marks?\b)", re.I
)

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


def _question_type(text: str) -> str:
    lowered = text.lower()
    if any(word in lowered for word in ("choose", "select", "mcq", "option a", "option b")):
        return "MCQ"
    if any(word in lowered for word in ("define", "state", "list", "name")):
        return "SHORT_ANSWER"
    if any(word in lowered for word in ("explain", "describe", "discuss", "derive")):
        return "DESCRIPTIVE"
    if any(word in lowered for word in ("draw", "diagram", "plot")):
        return "DIAGRAM"
    return "OTHER"


def _marks(text: str) -> float:
    match = _MARKS_RE.search(text)
    return float(next(value for value in match.groups() if value)) if match else 1.0


def _clean_question(text: str) -> str:
    return re.sub(r"\s+", " ", _MARKS_RE.sub("", text)).strip(" -:;\n")


def _regex_sections(text: str) -> list[BlueprintSection]:
    section_matches = list(_SECTION_RE.finditer(text))
    if not section_matches:
        section_matches = [None]
    sections: list[BlueprintSection] = []
    for index, match in enumerate(section_matches):
        start = match.end() if match else 0
        end = section_matches[index + 1].start() if match and index + 1 < len(section_matches) else len(text)
        body = text[start:end]
        name = (match.group(1) if match else "General")
        instructions = (match.group(2) or "").strip() if match else None
        questions: list[BlueprintQuestion] = []
        for order, question_match in enumerate(_QUESTION_RE.finditer(body), start=1):
            number, raw_text = question_match.groups()
            cleaned = _clean_question(raw_text)
            if not cleaned:
                continue
            questions.append(BlueprintQuestion(
                question_id=f"{name.lower().replace(' ', '-')}-{number.replace(' ', '')}",
                question_number=number.replace(" ", ""),
                question_text=cleaned,
                maximum_marks=_marks(raw_text),
                question_type=_question_type(cleaned),
                question_order=order,
            ))
        if questions:
            sections.append(BlueprintSection(
                section_id=f"section-{len(sections) + 1}", name=name.strip(),
                instructions=instructions or None, questions=questions,
            ))
    return sections


def _qwen_fallback(text: str) -> list[BlueprintSection]:
    client = openai_client
    prompt = ("Extract exam sections and questions from this OCR transcript. Return only JSON in "
              "the form {\"sections\":[{\"name\":str,\"instructions\":str|null,"
              "\"questions\":[{\"question_number\":str,\"question_text\":str,"
              "\"maximum_marks\":number,\"question_type\":str}]}]}.\n\n" + text)
    response = client.chat.completions.create(
        model=settings.blueprint_qwen_model_name,
        messages=[{"role": "user", "content": prompt}],
        temperature=0, max_tokens=4096,
    )
    raw = response.choices[0].message.content or ""
    if raw.startswith("```"):
        raw = "\n".join(raw.splitlines()[1:-1])
    data = json.loads(raw)
    sections = []
    for section_index, section in enumerate(data.get("sections", []), start=1):
        questions = []
        for order, question in enumerate(section.get("questions", []), start=1):
            number = str(question["question_number"])
            questions.append(BlueprintQuestion(
                question_id=f"section-{section_index}-{number.replace(' ', '')}",
                question_number=number, question_text=str(question["question_text"]).strip(),
                maximum_marks=float(question.get("maximum_marks", 1)),
                question_type=str(question.get("question_type", "OTHER")), question_order=order,
            ))
        if questions:
            sections.append(BlueprintSection(section_id=f"section-{section_index}",
                                             name=str(section.get("name", f"Section {section_index}")),
                                             instructions=section.get("instructions"), questions=questions))
    return sections


def extract_sections(ocr: dict[str, Any]) -> list[BlueprintSection]:
    sections = _regex_sections(_page_text(ocr))
    if sections:
        return sections
    try:
        return _qwen_fallback(_page_text(ocr))
    except Exception as exc:
        logger.warning("Qwen blueprint fallback failed: %s", exc)
        raise ValueError("Could not extract any questions from question paper OCR") from exc


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
        answers[number.replace(" ", "").lower()] = answer.strip()
    return answers


def attach_answer_key(sections: list[BlueprintSection], answers: dict[str, str]) -> list[BlueprintSection]:
    for section in sections:
        for question in section.questions:
            question.faculty_answer = answers.get(question.question_number.lower())
    return sections


def validate_blueprint(metadata: ExamMetadata, sections: list[BlueprintSection]) -> None:
    questions = [question for section in sections for question in section.questions]
    if not questions:
        raise ValueError("Blueprint must contain at least one question")
    total = sum(question.maximum_marks for question in questions)
    instructions = " ".join((section.instructions or "") for section in sections).lower()
    if "answer any" not in instructions and total > metadata.maximum_marks * 1.1:
        raise ValueError(f"Question marks ({total:g}) exceed maximum marks ({metadata.maximum_marks:g})")