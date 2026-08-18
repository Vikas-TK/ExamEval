"""
Regression test for blueprint generation's either/or sub-question handling.

_EXPLICIT_Q_START's fused `\\d+[a-z]?` capture only catches a sub-letter
glued directly onto the digits ("19a)"). A paper printed as "19. a) ..." /
"19. b) ..." — number, punctuation, space, then the letter — put both
sub-parts through with the identical question_id/question_number ("Q19"),
differing only by question_order. Phase 3's mapper then attached the
student's one answer to both blueprint entries, producing a duplicate
mapped row for what is really two distinct alternatives. See
app/blueprint_engine.py's save_current_question()/_leading_subletter().
"""
from __future__ import annotations

from app.blueprint_engine import _regex_sections


def test_either_or_subparts_get_distinct_question_ids():
    text = (
        "Part D (10 Marks)\n"
        "19. a) Demonstrate the implementation of a Denoising Autoencoder for "
        "image reconstruction using an appropriate dataset.\n"
        "OR\n"
        "19. b) Develop a deep learning model using the VGG16 pre-trained "
        "architecture for image classification.\n"
    )

    sections = _regex_sections(text)
    questions = [q for s in sections for q in s.questions]

    assert len(questions) == 2
    ids = {q.question_id for q in questions}
    numbers = {q.question_number for q in questions}
    assert ids == {"q-q19(a)", "q-q19(b)"}
    assert numbers == {"Q19(a)", "Q19(b)"}
    a = next(q for q in questions if q.question_number == "Q19(a)")
    b = next(q for q in questions if q.question_number == "Q19(b)")
    assert "Denoising Autoencoder" in a.question_text
    assert "VGG16" in b.question_text


def test_normal_sequential_questions_unaffected():
    """Ordinary back-to-back questions (no repeated base number) must not
    be mistaken for an either/or pair or get letters appended."""
    text = (
        "Part A (2 Marks)\n"
        "1. What is a perceptron?\n"
        "2. Define an autoencoder.\n"
        "3. What does LSTM stand for?\n"
    )

    sections = _regex_sections(text)
    questions = [q for s in sections for q in s.questions]

    assert [q.question_number for q in questions] == ["Q1", "Q2", "Q3"]
    assert all("(" not in q.question_number for q in questions)
