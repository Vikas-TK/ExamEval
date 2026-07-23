"""
Phase 4 – Expected Answer Depth & Classification Classifier
Classifies expected answer depth and structure based on marks and question type.
"""
from __future__ import annotations


def classify_answer_depth(maximum_marks: float, question_intent: str = "Explanation") -> str:
    """
    Classifies expected answer depth:
      - <= 1 Mark: Very Short
      - <= 3 Marks: Short
      - <= 7 Marks: Medium
      - <= 12 Marks: Detailed
      - > 12 Marks: Comprehensive
    """
    m = float(maximum_marks)

    if m <= 1.5:
        return "Very Short"
    elif m <= 3.5:
        return "Short"
    elif m <= 7.5:
        return "Medium"
    elif m <= 12.5:
        return "Detailed"
    else:
        return "Comprehensive"


def get_expected_answer_characteristics(
    question_intent: str,
    depth: str,
    question_type: str = "Descriptive"
) -> list[str]:
    """Generates expected answer characteristics based on intent and depth."""
    chars = [question_intent, f"{depth} Depth Response"]

    if question_intent == "Definition":
        chars.extend(["Technical Terminology", "Concise Explanation", "Accuracy"])
    elif question_intent in ("Comparison", "Difference"):
        chars.extend(["Comparative Points", "Tabular or Structured Contrast", "Key Differences"])
    elif question_intent == "Programming":
        chars.extend(["Syntax Correctness", "Algorithm Logic", "Edge Case Handling", "Code Structure"])
    elif question_intent in ("Diagram", "Flowchart"):
        chars.extend(["Visual Labeling", "Component Relationships", "Clear Diagrammatic Layout"])
    elif question_intent in ("Mathematical Derivation", "Numerical Problem"):
        chars.extend(["Formula Selection", "Intermediate Derivation Steps", "Final Numerical Accuracy"])
    else:
        chars.extend(["Conceptual Accuracy", "Logical Flow", "Relevant Examples"])

    return list(dict.fromkeys(chars))
