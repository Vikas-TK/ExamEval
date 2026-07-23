import uuid
import pytest
from app.phase4_context.intent_analyzer import detect_question_intent
from app.phase4_context.depth_classifier import classify_answer_depth, get_expected_answer_characteristics
from app.phase4_context.concept_extractor import extract_key_concepts_and_keywords
from app.phase4_context.criteria_generator import generate_evaluation_criteria
from app.phase4_context.builder import build_single_question_context


def test_intent_analyzer_rules():
    assert detect_question_intent("Define Software Engineering.") == "Definition"
    assert detect_question_intent("Differentiate SQL and NoSQL.") == "Difference"
    assert detect_question_intent("Compare REST and GraphQL.") == "Comparison"
    assert detect_question_intent("List any two examples of domain patterns.") == "List"
    assert detect_question_intent("Write a Python program to solve Fibonacci.") == "Programming"
    assert detect_question_intent("Derive the time complexity of QuickSort.") == "Mathematical Derivation"
    assert detect_question_intent("Draw the architecture diagram of Kubernetes.") == "Diagram"


def test_depth_classifier():
    assert classify_answer_depth(1.0) == "Very Short"
    assert classify_answer_depth(2.0) == "Short"
    assert classify_answer_depth(5.0) == "Medium"
    assert classify_answer_depth(10.0) == "Detailed"
    assert classify_answer_depth(15.0) == "Comprehensive"


def test_concept_and_criteria_generator():
    concepts, keywords = extract_key_concepts_and_keywords("Define Software Engineering.", "Systematic development")
    assert isinstance(concepts, list)
    assert isinstance(keywords, list)

    criteria = generate_evaluation_criteria("Definition", "Descriptive", 2.0, "Short")
    assert "Concept Accuracy" in criteria
    assert "Correct Terminology" in criteria


def test_build_single_question_context_success():
    eval_id = uuid.uuid4()
    bp_id = uuid.uuid4()
    mapped_qa = {
        "question_id": "Q13",
        "question_number": "13",
        "question_text": "Define Software Engineering.",
        "student_answer": "Software engineering is a systematic approach to software development.",
        "question_type": "Short Answer",
        "maximum_marks": 2.0,
        "visual_elements": [],
    }

    ctx = build_single_question_context(mapped_qa, "STU-001", eval_id, bp_id)

    assert ctx.student_id == "STU-001"
    assert ctx.evaluation_id == eval_id
    assert ctx.blueprint_id == bp_id
    assert ctx.question_id == "Q13"
    assert ctx.question_number == "13"
    assert ctx.question_intent == "Definition"
    assert ctx.expected_answer_depth == "Short"
    assert ctx.maximum_marks == 2.0
    assert ctx.status == "READY_FOR_PHASE_5"
    assert "Concept Accuracy" in ctx.evaluation_criteria


def test_build_single_question_context_fault_tolerant():
    eval_id = uuid.uuid4()
    bp_id = uuid.uuid4()
    # Invalid data structure that would fail intent analysis
    mapped_qa = {
        "question_id": None,
        "question_number": None,
        "question_text": None,
    }

    ctx = build_single_question_context(mapped_qa, "STU-001", eval_id, bp_id)
    assert ctx.status in ("READY_FOR_PHASE_5", "CONTEXT_INCOMPLETE")
