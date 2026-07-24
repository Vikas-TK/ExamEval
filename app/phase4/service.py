"""
Phase 4 – Service Layer

Orchestrates AI scoring, marks matrix assembly, and transcript/report generation.
"""
from __future__ import annotations

import csv
import io
import logging
import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from app.blueprint_models import ExamBlueprint
from app.models.evaluation import EvaluationRecord, StudentIdentity
from app.phase3.models import QuestionAnswerMapping
from app.phase4.evaluator import score_answer
from app.phase4.models import AnswerEvaluation
from app.phase4.repository import EvaluationResultRepository
from app.phase4.schemas import (
    MarksMatrixResponse, MatrixCell, Phase4Response, ScoredAnswerOut,
)

logger = logging.getLogger(__name__)


class Phase4Service:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._repo = EvaluationResultRepository(db)

    # ─── Helpers ──────────────────────────────────────────────────────────────

    def _get_student_display(self, evaluation_id: uuid.UUID) -> str:
        identity = (
            self._db.query(StudentIdentity)
            .filter(StudentIdentity.evaluation_id == evaluation_id)
            .first()
        )
        if identity:
            # student_hash is stored; we return first 8 chars as display key.
            # In production UI the frontend resolves this using the register_number
            # that the faculty originally uploaded (stored in StudentIdentity.student_hash
            # as hmac — not reversible here, so we show a unique short label).
            return identity.student_hash[:12]
        return str(evaluation_id)[:8]

    def _section_choose_counts(self, blueprint: ExamBlueprint) -> dict[str, int]:
        """section_name -> how many of that section's questions actually
        count, for 'answer any N of M' sections (declared via choose_count
        on the section). Sections without it are fully mandatory."""
        return {
            section["name"]: int(section["choose_count"])
            for section in (blueprint.sections or [])
            if section.get("choose_count")
        }

    def _fixed_max_marks(self, blueprint: ExamBlueprint) -> float:
        """
        The exam's true achievable maximum, independent of what any one
        student attempted. For a choice section ('answer any 2 of 3'), only
        choose_count questions' worth of marks ever count toward the total
        — not all M candidates — even if nobody attempted the extra ones.
        """
        total = 0.0
        for section in blueprint.sections or []:
            questions = section.get("questions", [])
            choose_count = section.get("choose_count")
            if choose_count and questions:
                per_question = float(questions[0].get("maximum_marks", 0))
                total += int(choose_count) * per_question
            else:
                total += sum(float(q.get("maximum_marks", 0)) for q in questions)
        return total

    def _get_answer_key_map(self, blueprint: ExamBlueprint) -> dict[str, str]:
        """Returns question_id → answer_key text from faculty_answer_key field."""
        if not blueprint.faculty_answer_key:
            return {}
        key_map: dict[str, str] = {}
        for item in blueprint.faculty_answer_key:
            if isinstance(item, dict):
                qid = item.get("question_id") or item.get("question_number", "")
                answer = item.get("answer_key") or item.get("answer", "")
                if qid and answer:
                    key_map[str(qid)] = str(answer)
        return key_map

    # ─── Phase 4 Pipeline ─────────────────────────────────────────────────────

    def run(self, evaluation_id: uuid.UUID, blueprint_id: uuid.UUID) -> Phase4Response:
        logger.info("Phase 4 started | evaluation_id=%s blueprint_id=%s", evaluation_id, blueprint_id)

        # Fetch Q&A records from Phase 3
        qa_records: list[QuestionAnswerMapping] = (
            self._db.query(QuestionAnswerMapping)
            .filter(QuestionAnswerMapping.evaluation_id == evaluation_id)
            .order_by(QuestionAnswerMapping.question_sequence)
            .all()
        )
        if not qa_records:
            raise ValueError(
                f"No Q&A mapping records found for evaluation_id={evaluation_id}. "
                "Run Phase 3 (mapping) first."
            )

        blueprint: ExamBlueprint | None = (
            self._db.query(ExamBlueprint)
            .filter(ExamBlueprint.blueprint_id == blueprint_id)
            .first()
        )
        if not blueprint:
            raise ValueError(f"Blueprint not found: blueprint_id={blueprint_id}")

        answer_key_map = self._get_answer_key_map(blueprint)
        student_display = self._get_student_display(evaluation_id)
        choose_counts = self._section_choose_counts(blueprint)
        section_attempted_seen: dict[str, int] = {}

        results: list[AnswerEvaluation] = []
        total_scored = 0.0
        total_max = self._fixed_max_marks(blueprint)
        questions_evaluated = 0

        for qa in qa_records:
            try:
                is_skipped = qa.mapping_status in ("SKIPPED", "UNMAPPED") or not qa.student_answer
                answer_key = answer_key_map.get(qa.question_id) or answer_key_map.get(qa.question_number)
                has_visual = bool(qa.visual_elements)

                # "Answer any N of M" sections: qa_records are already in
                # paper order (question_sequence), so the Nth attempted
                # question here really is the Nth one the student attempted
                # on the page. Anything attempted beyond the section's
                # choose_count is excess — it doesn't count toward the
                # total, and skipping the AI call for it also avoids
                # burning more of this hardware's very limited time on a
                # question that can never be scored anyway.
                is_excess = False
                if not is_skipped:
                    limit = choose_counts.get(qa.section_name)
                    if limit is not None:
                        seen = section_attempted_seen.get(qa.section_name, 0) + 1
                        section_attempted_seen[qa.section_name] = seen
                        is_excess = seen > limit

                if is_skipped:
                    scored = 0.0
                    feedback = "Student did not attempt this question."
                    confidence = 1.0
                    status = "SKIPPED"
                elif is_excess:
                    scored = 0.0
                    feedback = (
                        f"Not counted — {qa.section_name} allows only the first "
                        f"{choose_counts[qa.section_name]} attempted questions to be scored, "
                        "and this was attempted beyond that limit."
                    )
                    confidence = 1.0
                    status = "EXCESS_ATTEMPT"
                else:
                    result = score_answer(
                        question_text=qa.question_text,
                        student_answer=qa.student_answer,
                        maximum_marks=qa.maximum_marks or 0.0,
                        answer_key=answer_key,
                        question_type=qa.question_type,
                        has_visual=has_visual,
                        subject=blueprint.subject,
                    )
                    scored = result.score
                    feedback = result.feedback
                    confidence = result.confidence
                    status = "SCORED"
                    questions_evaluated += 1

                total_scored += scored

                results.append(AnswerEvaluation(
                    evaluation_id=evaluation_id,
                    blueprint_id=blueprint_id,
                    question_id=qa.question_id,
                    question_number=qa.question_number,
                    question_text=qa.question_text,
                    section_name=qa.section_name,
                    question_sequence=qa.question_sequence,
                    maximum_marks=qa.maximum_marks or 0.0,
                    question_type=qa.question_type,
                    student_answer=qa.student_answer,
                    visual_elements=qa.visual_elements,
                    answer_key=answer_key,
                    scored_marks=scored,
                    ai_feedback=feedback,
                    ai_confidence=confidence,
                    evaluation_status=status,
                ))

            except Exception as exc:
                logger.error("Scoring failed for Q%s: %s — recording as ERROR.", qa.question_number, exc)
                results.append(AnswerEvaluation(
                    evaluation_id=evaluation_id,
                    blueprint_id=blueprint_id,
                    question_id=qa.question_id,
                    question_number=qa.question_number,
                    question_text=qa.question_text,
                    section_name=qa.section_name,
                    question_sequence=qa.question_sequence,
                    maximum_marks=qa.maximum_marks or 0.0,
                    student_answer=qa.student_answer,
                    scored_marks=0.0,
                    ai_feedback=f"Evaluation error: {exc}",
                    ai_confidence=0.0,
                    evaluation_status="ERROR",
                ))

        self._repo.delete_by_evaluation_excluding_blueprint(evaluation_id, blueprint_id)
        self._repo.bulk_upsert(results)
        percentage = round((total_scored / total_max * 100) if total_max > 0 else 0.0, 2)

        return Phase4Response(
            status="SUCCESS",
            evaluation_id=str(evaluation_id),
            blueprint_id=str(blueprint_id),
            student_id=student_display,
            questions_evaluated=questions_evaluated,
            total_scored_marks=round(total_scored, 2),
            total_maximum_marks=round(total_max, 2),
            percentage=percentage,
            output=f"Evaluation complete. {questions_evaluated} questions scored. Total: {total_scored:.1f}/{total_max:.1f} ({percentage}%)",
        )

    # ─── Marks Matrix ─────────────────────────────────────────────────────────

    def build_matrix(self, blueprint_id: uuid.UUID) -> MarksMatrixResponse:
        blueprint: ExamBlueprint | None = (
            self._db.query(ExamBlueprint)
            .filter(ExamBlueprint.blueprint_id == blueprint_id)
            .first()
        )
        if not blueprint:
            raise ValueError(f"Blueprint not found: {blueprint_id}")

        all_results = self._repo.get_by_blueprint(blueprint_id)

        # Build question header list from blueprint sections
        question_headers: list[dict[str, Any]] = []
        section_max: dict[str, float] = defaultdict(float)
        for section in blueprint.sections or []:
            sname = section.get("name", "General")
            for q in section.get("questions", []):
                question_headers.append({
                    "question_number": str(q.get("question_number", "")),
                    "maximum_marks": float(q.get("maximum_marks", 0)),
                    "section_name": sname,
                    "question_id": q.get("question_id", ""),
                })
                section_max[sname] += float(q.get("maximum_marks", 0))

        section_headers = [
            {"section_name": s, "section_max": m} for s, m in section_max.items()
        ]

        # Group results by evaluation_id
        by_eval: dict[str, list[AnswerEvaluation]] = defaultdict(list)
        for r in all_results:
            by_eval[str(r.evaluation_id)].append(r)

        rows: list[MatrixCell] = []
        for eval_id_str, scored_records in by_eval.items():
            eval_id = uuid.UUID(eval_id_str)
            student_display = self._get_student_display(eval_id)

            q_scores: dict[str, float | None] = {}
            section_totals: dict[str, float] = defaultdict(float)

            for rec in scored_records:
                q_scores[rec.question_number] = rec.scored_marks
                if rec.section_name and rec.scored_marks is not None:
                    section_totals[rec.section_name] += rec.scored_marks

            grand_total = sum(v for v in q_scores.values() if v is not None)
            max_total = sum(h["maximum_marks"] for h in question_headers)
            pct = round(grand_total / max_total * 100, 2) if max_total > 0 else 0.0

            rows.append(MatrixCell(
                evaluation_id=eval_id_str,
                register_number=student_display,
                question_scores=q_scores,
                section_totals=dict(section_totals),
                grand_total=round(grand_total, 2),
                maximum_total=round(max_total, 2),
                percentage=pct,
            ))

        # Sort by register_number
        rows.sort(key=lambda r: r.register_number)

        return MarksMatrixResponse(
            blueprint_id=str(blueprint_id),
            exam_name=blueprint.exam_name,
            subject=blueprint.subject,
            subject_code=blueprint.subject_code,
            question_headers=question_headers,
            section_headers=section_headers,
            rows=rows,
            total_students=len(rows),
        )

    # ─── CSV Download ─────────────────────────────────────────────────────────

    def export_matrix_csv(self, blueprint_id: uuid.UUID) -> bytes:
        matrix = self.build_matrix(blueprint_id)
        buf = io.StringIO()
        writer = csv.writer(buf)

        # Header row
        headers = (
            ["Student"]
            + [f"Q{h['question_number']} ({h['maximum_marks']}m)" for h in matrix.question_headers]
            + [f"{s['section_name']} Total" for s in matrix.section_headers]
            + ["Grand Total", "Max Marks", "Percentage"]
        )
        writer.writerow(headers)

        for row in matrix.rows:
            cells = (
                [row.register_number]
                + [row.question_scores.get(h["question_number"], "") for h in matrix.question_headers]
                + [row.section_totals.get(s["section_name"], 0) for s in matrix.section_headers]
                + [row.grand_total, row.maximum_total, f"{row.percentage}%"]
            )
            writer.writerow(cells)

        return buf.getvalue().encode("utf-8-sig")  # utf-8-sig for Excel compatibility

    # ─── Transcript Download ───────────────────────────────────────────────────

    def build_transcript_txt(self, evaluation_id: uuid.UUID) -> bytes:
        record: EvaluationRecord | None = (
            self._db.query(EvaluationRecord)
            .filter(EvaluationRecord.evaluation_id == evaluation_id)
            .first()
        )
        results = self._repo.get_by_evaluation(evaluation_id)
        ocr_data = record.ocr_data if record else {}
        pages = ocr_data.get("pages", []) if ocr_data else []

        lines = [
            "=" * 60,
            "STUDENT ANSWER SCRIPT TRANSCRIPT",
            f"Evaluation ID : {evaluation_id}",
            f"Subject       : {results[0].section_name if results else 'N/A'}",
            "=" * 60,
            "",
        ]

        if results:
            lines.append("── SCORED ANSWER SUMMARY ──")
            for r in results:
                score_str = f"{r.scored_marks}/{r.maximum_marks}" if r.scored_marks is not None else "Not evaluated"
                lines.append(f"  Q{r.question_number}  [{score_str}]")
                if r.student_answer:
                    lines.append(f"    {r.student_answer[:300]}{'...' if len(r.student_answer or '') > 300 else ''}")
            lines.append("")

        lines.append("── FULL OCR TRANSCRIPT ──")
        for page in pages:
            lines.append(f"\n[Page {page.get('page_number', '?')}]")
            lines.append(page.get("transcript", "(empty page)"))

        return "\n".join(lines).encode("utf-8")

    def build_transcript_pdf(self, evaluation_id: uuid.UUID) -> bytes:
        """Generate a minimal PDF using reportlab if available, else fall back to TXT wrapped in a basic PDF."""
        txt = self.build_transcript_txt(evaluation_id).decode("utf-8")
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.units import cm
            from reportlab.pdfgen import canvas as pdfcanvas

            buf = io.BytesIO()
            c = pdfcanvas.Canvas(buf, pagesize=A4)
            width, height = A4
            margin = 2 * cm
            y = height - margin
            c.setFont("Helvetica-Bold", 13)
            c.drawString(margin, y, f"Student Transcript — {evaluation_id}")
            y -= 0.8 * cm
            c.setFont("Helvetica", 9)

            for line in txt.splitlines():
                if y < margin:
                    c.showPage()
                    y = height - margin
                    c.setFont("Helvetica", 9)
                c.drawString(margin, y, line[:120])
                y -= 0.4 * cm

            c.save()
            return buf.getvalue()

        except ImportError:
            # reportlab not installed — return TXT with PDF-like header as bytes
            logger.warning("reportlab not installed; returning TXT as fallback for PDF transcript.")
            return txt.encode("utf-8")
