"""
Module 14 – Student Evaluation Breakdown & PDF Report Generator
Generates comprehensive question-wise breakdown and downloadable PDF report artifacts for students.
"""
from __future__ import annotations

import uuid
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

from sqlalchemy.orm import Session
from app.models import StudentIdentity
from app.phase4_context.repository import EvaluationContextRepository
from app.phase6_consensus.repository import ConsolidatedEvaluationRepository

logger = logging.getLogger(__name__)


class StudentQuestionBreakdown(BaseModel):
    question_id: str
    question_number: str
    question_text: str
    student_answer: str
    answer_key: Optional[str] = "Model answer provided by institution policy."
    maximum_marks: float
    final_marks: float
    percentage: float
    accuracy_score: float
    completeness_score: float
    depth_score: float
    strengths: List[str] = Field(default_factory=list)
    weaknesses: List[str] = Field(default_factory=list)
    missing_concepts: List[str] = Field(default_factory=list)
    improvement_suggestions: List[str] = Field(default_factory=list)
    ai_remarks: Optional[str] = None


class StudentReportResponse(BaseModel):
    student_id: str
    evaluation_id: uuid.UUID
    blueprint_id: Optional[uuid.UUID] = None
    subject_code: str = "GENERAL"
    total_max_marks: float
    total_scored_marks: float
    overall_percentage: float
    overall_grade: str
    questions: List[StudentQuestionBreakdown]


def generate_student_report(db: Session, evaluation_id: uuid.UUID) -> StudentReportResponse:
    """
    Generates structured student evaluation breakdown response.
    """
    student_rec = db.query(StudentIdentity).filter_by(evaluation_id=evaluation_id).first()
    student_id = student_rec.register_number if student_rec else f"STU-{str(evaluation_id)[:8]}"
    subj_code = student_rec.subject_id if student_rec else "GENERAL"

    repo_ctx = EvaluationContextRepository(db)
    contexts = repo_ctx.get_contexts_by_evaluation_id(evaluation_id)
    ctx_map = {c.question_id: c for c in contexts}

    repo_p6 = ConsolidatedEvaluationRepository(db)
    consolidated_records = repo_p6.get_consolidated_by_evaluation(evaluation_id)

    questions_list: list[StudentQuestionBreakdown] = []
    total_max = 0.0
    total_scored = 0.0

    for rec in consolidated_records:
        ctx = ctx_map.get(rec.question_id)
        q_text = ctx.question_text if ctx else rec.question_number
        stu_ans = ctx.student_answer if ctx else ""

        total_max += rec.maximum_marks
        total_scored += rec.final_marks

        questions_list.append(
            StudentQuestionBreakdown(
                question_id=rec.question_id,
                question_number=rec.question_number,
                question_text=q_text,
                student_answer=stu_ans,
                answer_key="Model answer provided per institutional blueprint policy.",
                maximum_marks=rec.maximum_marks,
                final_marks=rec.final_marks,
                percentage=rec.percentage,
                accuracy_score=rec.accuracy_score,
                completeness_score=rec.completeness_score,
                depth_score=rec.depth_score,
                strengths=rec.strengths or [],
                weaknesses=rec.weaknesses or [],
                missing_concepts=rec.missing_concepts or [],
                improvement_suggestions=rec.improvement_suggestions or [],
                ai_remarks=rec.final_remarks or "Question evaluated.",
            )
        )

    overall_pct = round((total_scored / total_max * 100.0), 2) if total_max > 0 else 0.0

    if overall_pct >= 90.0:
        grade = "A+ (Excellent)"
    elif overall_pct >= 80.0:
        grade = "A (Very Good)"
    elif overall_pct >= 70.0:
        grade = "B (Good)"
    elif overall_pct >= 50.0:
        grade = "C (Average)"
    elif overall_pct >= 35.0:
        grade = "D (Needs Improvement)"
    else:
        grade = "F (Fail)"

    return StudentReportResponse(
        student_id=student_id,
        evaluation_id=evaluation_id,
        blueprint_id=consolidated_records[0].blueprint_id if consolidated_records else None,
        subject_code=subj_code,
        total_max_marks=round(total_max, 2),
        total_scored_marks=round(total_scored, 2),
        overall_percentage=overall_pct,
        overall_grade=grade,
        questions=questions_list,
    )


def generate_html_report_content(report: StudentReportResponse) -> str:
    """Generates clean printable HTML document string for PDF download."""
    rows = ""
    for q in report.questions:
        rows += f"""
        <div style="border: 1px solid #cbd5e1; border-radius: 8px; padding: 16px; margin-bottom: 16px; background: #ffffff;">
            <div style="display: flex; justify-content: space-between; font-weight: bold; color: #0f172a; margin-bottom: 8px;">
                <span>{q.question_number}. {q.question_text}</span>
                <span style="color: #2563eb;">{q.final_marks} / {q.maximum_marks} Marks</span>
            </div>
            <div style="font-size: 13px; color: #334155; margin-bottom: 8px;">
                <strong>Student Answer:</strong> <span style="font-style: italic;">{q.student_answer or 'No answer provided'}</span>
            </div>
            <div style="font-size: 12px; color: #475569; background: #f8fafc; padding: 8px; border-radius: 6px;">
                <strong>AI Remarks:</strong> {q.ai_remarks}<br/>
                <strong>Strengths:</strong> {', '.join(q.strengths) if q.strengths else 'None'}<br/>
                <strong>Missing Concepts:</strong> {', '.join(q.missing_concepts) if q.missing_concepts else 'None'}
            </div>
        </div>
        """

    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8"/>
        <title>Student Evaluation Report - {report.student_id}</title>
        <style>
            body {{ font-family: 'Segoe UI', Roboto, sans-serif; color: #0f172a; margin: 40px; background: #f1f5f9; }}
            .card {{ background: #ffffff; padding: 24px; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
            .header {{ display: flex; justify-content: space-between; border-bottom: 2px solid #e2e8f0; padding-bottom: 16px; margin-bottom: 24px; }}
            .grade-badge {{ font-size: 20px; font-weight: bold; color: #16a34a; background: #dcfce7; padding: 8px 16px; border-radius: 8px; }}
        </style>
    </head>
    <body>
        <div class="card">
            <div class="header">
                <div>
                    <h2 style="margin: 0;">Automated Exam Evaluation Report</h2>
                    <p style="margin: 4px 0; color: #64748b;">Student ID: {report.student_id} | Subject: {report.subject_code}</p>
                </div>
                <div class="grade-badge">{report.overall_grade} ({report.overall_percentage}%)</div>
            </div>
            <h3>Score: {report.total_scored_marks} / {report.total_max_marks} Marks</h3>
            {rows}
        </div>
    </body>
    </html>
    """
