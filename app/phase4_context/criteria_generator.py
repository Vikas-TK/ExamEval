"""
Phase 4 – Evaluation Criteria Generator
Generates structured evaluation criteria for Phase 5 AI Evaluation Agents (Accuracy, Completeness, Depth).
"""
from __future__ import annotations

from typing import List


def generate_evaluation_criteria(
    question_intent: str,
    question_type: str = "Descriptive",
    maximum_marks: float = 5.0,
    expected_depth: str = "Medium"
) -> List[str]:
    """
    Generates structured evaluation criteria array based on intent, question type, and depth.
    """
    criteria: list[str] = ["Concept Accuracy", "Technical Correctness"]

    if question_intent == "Definition":
        criteria.extend(["Correct Terminology", "Concise Explanation"])
    elif question_intent in ("Comparison", "Difference"):
        criteria.extend(["Comparative Structure", "Key Differentiating Factors", "Completeness of Contrast"])
    elif question_intent in ("Algorithm", "Programming"):
        criteria.extend(["Syntax & Code Logic", "Algorithmic Efficiency", "Correctness & Edge Cases"])
    elif question_intent in ("Diagram", "Flowchart"):
        criteria.extend(["Visual Labeling", "Component Layout & Flow", "Structural Integrity"])
    elif question_intent in ("Mathematical Derivation", "Numerical Problem", "Formula"):
        criteria.extend(["Formula Selection", "Intermediate Step Accuracy", "Final Numerical Result"])
    elif question_intent in ("Case Study", "Application", "Problem Solving"):
        criteria.extend(["Problem Analysis", "Logical Reasoning", "Practical Application"])
    else: # Explanation, Essay
        criteria.extend(["Logical Flow & Organization", "Coverage of Core Principles", "Supporting Examples"])

    if expected_depth in ("Detailed", "Comprehensive"):
        criteria.append("Depth of Technical Elaboration")

    return list(dict.fromkeys(criteria))
