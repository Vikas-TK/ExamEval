"""
Phase 6 – Feedback Consolidation & Deduplication Module
Synthesizes feedback observations from Accuracy, Completeness, and Depth reports into concise structured lists.
"""
from __future__ import annotations

from typing import Dict, List, Tuple


def consolidate_agent_feedback(
    accuracy_report: dict,
    completeness_report: dict,
    depth_report: dict,
) -> Tuple[List[str], List[str], List[str], List[str], str]:
    """
    Merges observations from Accuracy, Completeness, and Depth reports,
    removing duplicates and returning (strengths, weaknesses, missing_concepts, suggestions, final_remarks).
    """
    strengths: list[str] = []
    weaknesses: list[str] = []
    missing_concepts: list[str] = []
    suggestions: list[str] = []

    # 1. Strengths
    for c in accuracy_report.get("correct_concepts", []) or []:
        strengths.append(f"Correctly applied technical concept: {c}")
    for p in completeness_report.get("covered_points", []) or []:
        strengths.append(f"Covered required topic point: {p}")
    for s in depth_report.get("strong_sections", []) or []:
        strengths.append(f"Strong structural area: {s}")

    # 2. Weaknesses & Technical Errors
    for err in accuracy_report.get("technical_errors", []) or []:
        weaknesses.append(f"Technical error: {err}")
    for p in completeness_report.get("missing_points", []) or []:
        weaknesses.append(f"Missing required topic coverage: {p}")
    for w in depth_report.get("weak_sections", []) or []:
        weaknesses.append(f"Area needing depth: {w}")

    # 3. Missing Concepts & Keywords
    for mc in completeness_report.get("missing_concepts", []) or []:
        missing_concepts.append(str(mc))
    for mk in completeness_report.get("missing_keywords", []) or []:
        if mk not in missing_concepts:
            missing_concepts.append(str(mk))

    # 4. Improvement Suggestions
    for mc in missing_concepts[:3]:
        suggestions.append(f"Review core definition and principles of '{mc}'.")
    if depth_report.get("weak_sections"):
        suggestions.append("Elaborate with clear technical diagrams or step-by-step examples.")

    # Deduplicate while preserving order
    dedup_strengths = list(dict.fromkeys(strengths))
    dedup_weaknesses = list(dict.fromkeys(weaknesses))
    dedup_missing = list(dict.fromkeys(missing_concepts))
    dedup_suggestions = list(dict.fromkeys(suggestions))

    # Final Remarks synthesis
    acc_rem = accuracy_report.get("remarks") or ""
    cmp_rem = completeness_report.get("remarks") or ""
    dph_rem = depth_report.get("remarks") or ""
    remarks_list = [r for r in [acc_rem, cmp_rem, dph_rem] if r]
    final_remarks = " ".join(remarks_list) if remarks_list else "Consolidated evaluation completed."

    return dedup_strengths, dedup_weaknesses, dedup_missing, dedup_suggestions, final_remarks
