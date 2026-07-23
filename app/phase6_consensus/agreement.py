"""
Phase 6 – Agreement Analysis Module
Calculates Agreement Level and Confidence metrics among Accuracy, Completeness, and Depth reports.
"""
from __future__ import annotations

from typing import List, Tuple


def calculate_agreement_and_confidence(
    percentages: List[float],
    confidences: List[float]
) -> Tuple[str, float]:
    """
    Calculates Agreement Level and Confidence.
    Thresholds based on max percentage difference among active agents:
      <= 10% -> High Agreement
      10% - 20% -> Medium Agreement
      > 20% -> Low Agreement
    """
    if not percentages:
        return "MANUAL_REVIEW_REQUIRED", 0.0

    if len(percentages) == 1:
        avg_conf = confidences[0] if confidences else 0.8
        return "Single Agent (Partial)", round(avg_conf * 0.8, 2)

    diff = max(percentages) - min(percentages)

    if diff <= 10.0:
        level = "High Agreement"
        factor = 1.0
    elif diff <= 20.0:
        level = "Medium Agreement"
        factor = 0.85
    else:
        level = "Low Agreement"
        factor = 0.70

    avg_agent_conf = (sum(confidences) / len(confidences)) if confidences else 0.9
    overall_confidence = round(max(0.0, min(1.0, avg_agent_conf * factor)), 2)

    return level, overall_confidence
