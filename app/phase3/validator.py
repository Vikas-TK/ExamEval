"""
Phase 3 – Validation Engine

Step 6: Validate the Q&A mapping against the blueprint.
Produces a ValidationReport with status VALID / INVALID / WARNING.
Stores warnings rather than aborting on soft failures.
"""
from __future__ import annotations

import logging

from app.phase3.schemas import BlueprintQuestion, MappedQA, ValidationReport

logger = logging.getLogger(__name__)


def validate_mapping(
    mapped_qas: list[MappedQA],
    bp_questions: list[BlueprintQuestion],
) -> tuple[list[MappedQA], ValidationReport]:
    """
    Validate the Q&A mapping.

    Returns:
        (annotated_mapped_qas, ValidationReport)
    """
    errors: list[str] = []
    warnings: list[str] = []

    bp_question_ids = {bq.question_id for bq in bp_questions}
    seen_question_ids: set[str] = set()

    mapped_count = 0
    unmapped_count = 0
    skipped_count = 0

    annotated: list[MappedQA] = []

    for mqa in mapped_qas:
        local_warnings: list[str] = []
        local_errors: list[str] = []
        q_validation = "VALID"

        # 1. Every mapped answer must reference a valid blueprint question
        if mqa.question_id not in bp_question_ids:
            msg = f"Q{mqa.question_number}: question_id '{mqa.question_id}' not in blueprint."
            local_errors.append(msg)
            errors.append(msg)
            q_validation = "INVALID"

        # 2. No duplicate mappings
        if mqa.question_id in seen_question_ids:
            msg = f"Q{mqa.question_number}: duplicate mapping detected."
            local_warnings.append(msg)
            warnings.append(msg)
            if q_validation == "VALID":
                q_validation = "WARNING"
        seen_question_ids.add(mqa.question_id)

        # 3. Maximum marks consistency
        bp_match = next((bq for bq in bp_questions if bq.question_id == mqa.question_id), None)
        if bp_match and abs(mqa.maximum_marks - bp_match.maximum_marks) > 0.01:
            msg = (f"Q{mqa.question_number}: marks mismatch — "
                   f"mapped={mqa.maximum_marks}, blueprint={bp_match.maximum_marks}.")
            local_warnings.append(msg)
            warnings.append(msg)
            if q_validation == "VALID":
                q_validation = "WARNING"

        # 4. Skipped vs blank
        if mqa.mapping_status == "SKIPPED":
            skipped_count += 1
            note = f"Q{mqa.question_number}: no answer found — marked SKIPPED."
            local_warnings.append(note)
            warnings.append(note)
        elif mqa.mapping_status == "UNMAPPED":
            unmapped_count += 1
            msg = f"Q{mqa.question_number}: could not be mapped — UNMAPPED."
            local_errors.append(msg)
            errors.append(msg)
            q_validation = "INVALID"
        else:
            mapped_count += 1
            # Empty student_answer on a MAPPED record → warning
            if not mqa.student_answer:
                note = f"Q{mqa.question_number}: MAPPED but student answer is empty."
                local_warnings.append(note)
                warnings.append(note)
                if q_validation == "VALID":
                    q_validation = "WARNING"

        # Update the MappedQA with per-question validation details
        annotated.append(mqa.model_copy(update={
            "validation_status": q_validation,
            # We'll pass these through to storage via the repository
        }))

    # 5. Every blueprint question must appear in the mapping
    mapped_qids = {m.question_id for m in mapped_qas}
    for bq in bp_questions:
        if bq.question_id not in mapped_qids:
            msg = f"Blueprint question '{bq.question_number}' has no mapping record."
            errors.append(msg)

    # Determine overall status
    if errors:
        overall = "INVALID"
    elif warnings:
        overall = "WARNING"
    else:
        overall = "VALID"

    report = ValidationReport(
        validation_status=overall,
        total_blueprint_questions=len(bp_questions),
        mapped_count=mapped_count,
        unmapped_count=unmapped_count,
        skipped_count=skipped_count,
        errors=errors,
        warnings=warnings,
    )

    logger.info("Validation complete: %s | mapped=%d skipped=%d unmapped=%d errors=%d warnings=%d",
                overall, mapped_count, skipped_count, unmapped_count, len(errors), len(warnings))

    return annotated, report
