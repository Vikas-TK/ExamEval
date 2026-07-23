"""
Phase 4 – Evaluation Context Builder
Assembles EvaluationContext objects for every mapped question with fault tolerance.
"""
from __future__ import annotations

import uuid
import logging
from typing import Any, Dict

from app.phase4_context.intent_analyzer import detect_question_intent
from app.phase4_context.depth_classifier import classify_answer_depth, get_expected_answer_characteristics
from app.phase4_context.concept_extractor import extract_key_concepts_and_keywords
from app.phase4_context.criteria_generator import generate_evaluation_criteria
from app.phase4_context.schemas import EvaluationContextOut

logger = logging.getLogger(__name__)


def build_single_question_context(
    mapped_qa: Dict[str, Any],
    student_id: str,
    evaluation_id: uuid.UUID,
    blueprint_id: uuid.UUID
) -> EvaluationContextOut:
    """
    Builds structured EvaluationContextOut for one mapped question.
    Fault-tolerant: If processing fails, sets status to CONTEXT_INCOMPLETE without raising.
    """
    q_id = str(mapped_qa.get("question_id") or mapped_qa.get("question_number") or "Q0")
    q_num = str(mapped_qa.get("question_number") or "0")
    q_text = str(mapped_qa.get("question_text") or "")
    stu_answer = str(mapped_qa.get("student_answer") or mapped_qa.get("raw_text") or "")
    q_type = str(mapped_qa.get("question_type") or "Descriptive")
    max_marks = float(mapped_qa.get("maximum_marks") or 5.0)
    visuals = mapped_qa.get("visual_elements") or []

    try:
        intent = detect_question_intent(q_text)
        depth = classify_answer_depth(max_marks, intent)
        characteristics = get_expected_answer_characteristics(intent, depth, q_type)
        concepts, keywords = extract_key_concepts_and_keywords(q_text, stu_answer)
        criteria = generate_evaluation_criteria(intent, q_type, max_marks, depth)

        return EvaluationContextOut(
            context_id=uuid.uuid4(),
            student_id=student_id,
            evaluation_id=evaluation_id,
            blueprint_id=blueprint_id,
            question_id=q_id,
            question_number=q_num,
            question_text=q_text,
            question_intent=intent,
            question_type=q_type,
            maximum_marks=max_marks,
            expected_answer_depth=depth,
            student_answer=stu_answer,
            expected_answer_characteristics=characteristics,
            expected_structure=f"Structured {depth} response addressing {intent}",
            expected_coverage=f"Coverage of key concepts: {', '.join(concepts[:3]) if concepts else 'Core topic'}",
            expected_detail=f"Detail level appropriate for {max_marks} marks ({depth})",
            key_concepts=concepts,
            keywords=keywords,
            subject_domain="Computer Science & Engineering",
            difficulty_level="Medium",
            evaluation_criteria=criteria,
            visual_elements=visuals if isinstance(visuals, list) else [],
            status="READY_FOR_PHASE_5",
        )
    except Exception as exc:
        logger.error("Failed to build evaluation context for question '%s': %s", q_num, exc)
        # Mark CONTEXT_INCOMPLETE for this question without stopping remaining questions
        return EvaluationContextOut(
            context_id=uuid.uuid4(),
            student_id=student_id,
            evaluation_id=evaluation_id,
            blueprint_id=blueprint_id,
            question_id=q_id,
            question_number=q_num,
            question_text=q_text,
            question_intent="Explanation",
            question_type=q_type,
            maximum_marks=max_marks,
            expected_answer_depth="Medium",
            student_answer=stu_answer,
            expected_answer_characteristics=["General Answer"],
            expected_structure="General Response",
            expected_coverage="Basic Coverage",
            expected_detail="Standard Detail",
            key_concepts=[],
            keywords=[],
            subject_domain="General",
            difficulty_level="Medium",
            evaluation_criteria=["Concept Accuracy"],
            visual_elements=[],
            status="CONTEXT_INCOMPLETE",
        )
