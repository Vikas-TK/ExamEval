"""
Phase 6 – Weighted Consensus Rules & Mark Calculation Module
Redistributes agent weights on partial agent failure and calculates final normalized marks and status.
"""
from __future__ import annotations

from typing import Dict, Tuple, Optional


def calculate_weighted_marks_and_status(
    accuracy_score: Optional[float],
    accuracy_status: str,
    completeness_score: Optional[float],
    completeness_status: str,
    depth_score: Optional[float],
    depth_status: str,
    maximum_marks: float,
) -> Tuple[float, float, float, str]:
    """
    Calculates Weighted Score, Final Marks, Percentage, and Evaluation Status.
    Redistributes default weights (Accuracy: 0.50, Completeness: 0.30, Depth: 0.20)
    proportionally if individual agents failed.
    """
    weights: Dict[str, float] = {}
    scores: Dict[str, float] = {}

    if accuracy_status == "COMPLETED" and accuracy_score is not None:
        weights["accuracy"] = 0.50
        scores["accuracy"] = accuracy_score

    if completeness_status == "COMPLETED" and completeness_score is not None:
        weights["completeness"] = 0.30
        scores["completeness"] = completeness_score

    if depth_status == "COMPLETED" and depth_score is not None:
        weights["depth"] = 0.20
        scores["depth"] = depth_score

    # All agents failed fallback
    if not weights:
        return 0.0, 0.0, 0.0, "MANUAL_REVIEW_REQUIRED"

    # Normalize weights to sum to 1.0
    total_w = sum(weights.values())
    norm_weights = {k: v / total_w for k, v in weights.items()}

    weighted_score = sum(scores[k] * norm_weights[k] for k in norm_weights)
    max_m = max(0.1, float(maximum_marks))
    final_marks = round(max(0.0, min(max_m, weighted_score)), 2)
    percentage = round((final_marks / max_m * 100.0), 2)

    # Evaluation Status thresholds
    if percentage >= 90.0:
        status_label = "Excellent"
    elif percentage >= 80.0:
        status_label = "Very Good"
    elif percentage >= 70.0:
        status_label = "Good"
    elif percentage >= 50.0:
        status_label = "Average"
    elif percentage >= 35.0:
        status_label = "Needs Improvement"
    else:
        status_label = "Fail"

    return round(weighted_score, 2), final_marks, percentage, status_label
