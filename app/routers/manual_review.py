"""
Module 9-14 – Manual Review, Blueprint & Answer Key Management, Re-trigger Pipeline Router
Endpoints for Manual Blueprint Creation/Editing, Answer Key Versioning, Pre-mapping Verification,
Manual Review with Audit Trail, Pipeline Re-triggering, and Student PDF Report Generation.
"""
from __future__ import annotations

import uuid
import logging
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.blueprint_models import ExamBlueprint, AnswerKeyVersion, AuditLog
from app.blueprint_validator import validate_blueprint_before_mapping, BlueprintValidationReport
from app.phase3.repository import QAMappingRepository
from app.phase3.service import Phase3Service
from app.phase4_context.service import build_evaluation_context_service
from app.phase5_agents.service import run_phase5_multi_agent_evaluation
from app.phase6_consensus.service import run_phase6_consensus_service
from app.reports_generator import generate_student_report, generate_html_report_content, StudentReportResponse

from app.blueprint_manager import (
    ComprehensiveBlueprintSchema,
    validate_blueprint_json,
    get_active_approved_blueprint,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/manual-review", tags=["Manual Review & Management Engine"])


class ApprovalStatusUpdateRequest(BaseModel):
    status: str  # Draft | Under Review | Approved | Archived
    performed_by: str = "Faculty Admin"
    remarks: Optional[str] = None


@router.post("/blueprint/manual-create", status_code=status.HTTP_201_CREATED, summary="Mode 3 - Create Blueprint Manually")
def create_manual_blueprint(body: ComprehensiveBlueprintSchema, db: Session = Depends(get_db)):
    """Creates a complete Manual Blueprint via Visual Builder Mode without needing a question paper."""
    bp_id = body.blueprint_id or uuid.uuid4()

    existing = db.query(ExamBlueprint).filter_by(
        exam_name=body.exam_name,
        subject_code=body.subject_code,
        regulation=body.regulation,
        semester=body.semester,
    ).first()

    bp = existing if existing else ExamBlueprint(blueprint_id=bp_id)
    bp.exam_name = body.exam_name
    bp.subject = body.subject
    bp.subject_code = body.subject_code
    bp.regulation = body.regulation
    bp.semester = body.semester
    bp.department = body.department
    bp.duration_minutes = body.duration_minutes
    bp.maximum_marks = body.maximum_marks
    bp.sections = [sec.model_dump() for sec in body.sections]
    bp.source_ocr = {"source": "Manual Visual Builder Mode"}
    bp.faculty_answer_key = body.faculty_answer_key or []
    bp.status = body.status
    bp.blueprint_type = "manual_builder"
    bp.academic_year = body.academic_year
    bp.exam_type = body.exam_type
    bp.is_template = body.is_template
    bp.template_name = body.template_name

    db.add(bp)
    db.commit()
    db.refresh(bp)
    return {"message": "Manual Blueprint created successfully.", "blueprint_id": str(bp.blueprint_id), "status": bp.status}


@router.post("/blueprint/upload-json", summary="Mode 2 - Upload & Validate Blueprint JSON")
def upload_blueprint_json(body: Dict[str, Any], db: Session = Depends(get_db)):
    """Uploads and schema-validates a Blueprint JSON, returning errors before saving."""
    validation = validate_blueprint_json(body)
    if not validation.is_valid:
        raise HTTPException(422, detail={"message": "Blueprint JSON validation failed.", "errors": validation.errors, "warnings": validation.warnings})

    bp_schema = ComprehensiveBlueprintSchema.model_validate(body)
    bp_id = bp_schema.blueprint_id or uuid.uuid4()

    bp = ExamBlueprint(
        blueprint_id=bp_id,
        exam_name=bp_schema.exam_name,
        subject=bp_schema.subject,
        subject_code=bp_schema.subject_code,
        regulation=bp_schema.regulation,
        semester=bp_schema.semester,
        department=bp_schema.department,
        duration_minutes=bp_schema.duration_minutes,
        maximum_marks=bp_schema.maximum_marks,
        sections=[sec.model_dump() for sec in bp_schema.sections],
        source_ocr={"source": "JSON Upload Mode"},
        faculty_answer_key=bp_schema.faculty_answer_key or [],
        status=bp_schema.status,
        blueprint_type="json_upload",
        academic_year=bp_schema.academic_year,
        exam_type=bp_schema.exam_type,
        is_template=bp_schema.is_template,
        template_name=bp_schema.template_name,
    )
    db.add(bp)
    db.commit()
    db.refresh(bp)
    return {
        "message": "Blueprint JSON uploaded and validated successfully.",
        "blueprint_id": str(bp.blueprint_id),
        "status": bp.status,
        "validation_warnings": validation.warnings,
    }


@router.put("/blueprint/{blueprint_id}/approval", summary="Blueprint Approval Workflow")
def update_blueprint_approval_status(blueprint_id: uuid.UUID, body: ApprovalStatusUpdateRequest, db: Session = Depends(get_db)):
    """Updates blueprint state between Draft -> Under Review -> Approved -> Archived."""
    bp = db.query(ExamBlueprint).filter_by(blueprint_id=blueprint_id).first()
    if not bp:
        raise HTTPException(404, f"Blueprint '{blueprint_id}' not found.")

    if body.status not in ("Draft", "Under Review", "Approved", "Archived"):
        raise HTTPException(400, f"Invalid status '{body.status}'. Must be Draft, Under Review, Approved, or Archived.")

    prev_status = bp.status
    bp.status = body.status

    log = AuditLog(
        log_id=uuid.uuid4(),
        entity_type="blueprint",
        entity_id=str(blueprint_id),
        action=f"status_change_{body.status.lower()}",
        performed_by=body.performed_by,
        previous_state={"status": prev_status},
        new_state={"status": body.status},
        remarks=body.remarks,
    )
    db.add(log)
    db.commit()

    return {"message": f"Blueprint status changed from '{prev_status}' to '{body.status}'.", "blueprint_id": str(blueprint_id), "status": bp.status}


@router.post("/blueprint/{blueprint_id}/template", summary="Save Blueprint as Template")
def save_blueprint_as_template(blueprint_id: uuid.UUID, template_name: str, db: Session = Depends(get_db)):
    """Saves an existing blueprint as a reusable template."""
    bp = db.query(ExamBlueprint).filter_by(blueprint_id=blueprint_id).first()
    if not bp:
        raise HTTPException(404, f"Blueprint '{blueprint_id}' not found.")

    bp.is_template = True
    bp.template_name = template_name
    db.commit()
    return {"message": f"Blueprint saved as template '{template_name}'.", "blueprint_id": str(blueprint_id)}


@router.get("/templates", summary="List Reusable Blueprint Templates")
def list_blueprint_templates(db: Session = Depends(get_db)):
    """Lists templates categorized by Department, Subject, Semester, and Regulation."""
    templates = db.query(ExamBlueprint).filter(ExamBlueprint.is_template == True).all()
    return templates


@router.get("/blueprint/{blueprint_id}/export", summary="Export Blueprint JSON & Answer Key")
def export_blueprint_json(blueprint_id: uuid.UUID, db: Session = Depends(get_db)):
    """Exports full Blueprint JSON, Answer Keys, and Metadata."""
    bp = db.query(ExamBlueprint).filter_by(blueprint_id=blueprint_id).first()
    if not bp:
        raise HTTPException(404, f"Blueprint '{blueprint_id}' not found.")

    return {
        "blueprint_id": str(bp.blueprint_id),
        "exam_name": bp.exam_name,
        "subject": bp.subject,
        "subject_code": bp.subject_code,
        "regulation": bp.regulation,
        "semester": bp.semester,
        "department": bp.department,
        "duration_minutes": bp.duration_minutes,
        "maximum_marks": bp.maximum_marks,
        "status": bp.status,
        "blueprint_type": bp.blueprint_type,
        "sections": bp.sections,
        "faculty_answer_key": bp.faculty_answer_key,
        "exported_at": str(bp.updated_at),
    }


class AnswerKeyCreateRequest(BaseModel):
    blueprint_id: uuid.UUID
    format_type: str = "manual"  # pdf | docx | handwritten | manual | ai_generated
    author: str = "Faculty Admin"
    status: str = "Approved"     # Draft | Approved | Archived
    answer_key_data: List[Dict[str, Any]]


class RetriggerPipelineRequest(BaseModel):
    evaluation_id: uuid.UUID
    start_phase: str  # phase2_blueprint | phase3_mapping | phase4_context | phase5_evaluation | phase6_consensus
    performed_by: str = "Faculty Admin"
    remarks: Optional[str] = "Pipeline re-triggered after manual correction."


@router.post("/blueprint/validate", response_model=BlueprintValidationReport, summary="Verify Blueprint Before Mapping")
def validate_blueprint_endpoint(blueprint_id: uuid.UUID, db: Session = Depends(get_db)):
    """Module 11 – Validates blueprint integrity before Phase 3 Mapping begins."""
    bp = db.query(ExamBlueprint).filter_by(blueprint_id=blueprint_id).first()
    if not bp:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Blueprint '{blueprint_id}' not found.")

    bp_dict = {
        "blueprint_id": str(bp.blueprint_id),
        "sections": bp.sections,
        "faculty_answer_key": bp.faculty_answer_key,
    }
    return validate_blueprint_before_mapping(bp_dict)


@router.post("/answer-keys", status_code=status.HTTP_201_CREATED, summary="Create/Version Answer Key")
def create_answer_key_version(body: AnswerKeyCreateRequest, db: Session = Depends(get_db)):
    """Module 10 – Manages multi-option Answer Key versioning (Draft/Approved/Archived)."""
    bp = db.query(ExamBlueprint).filter_by(blueprint_id=body.blueprint_id).first()
    if not bp:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"Blueprint '{body.blueprint_id}' not found.")

    # Get max version
    existing_versions = db.query(AnswerKeyVersion).filter_by(blueprint_id=body.blueprint_id).all()
    next_version = len(existing_versions) + 1

    # Deactivate previous approved versions if new is approved
    if body.status == "Approved":
        for v in existing_versions:
            v.is_active = False

    rec = AnswerKeyVersion(
        version_id=uuid.uuid4(),
        blueprint_id=body.blueprint_id,
        version_number=next_version,
        author=body.author,
        format_type=body.format_type,
        status=body.status,
        is_active=(body.status == "Approved"),
        answer_key_data=body.answer_key_data,
    )
    db.add(rec)

    # Sync to blueprint model
    if body.status == "Approved":
        bp.faculty_answer_key = body.answer_key_data

    db.commit()
    db.refresh(rec)
    return {"message": "Answer key version created successfully.", "version_number": next_version, "version_id": str(rec.version_id)}


@router.post("/retrigger", summary="Re-trigger Pipeline from Any Phase")
async def retrigger_pipeline_from_phase(body: RetriggerPipelineRequest, db: Session = Depends(get_db)):
    """
    Module 13 – Triggers re-evaluation from any phase (Phase 2 to 6)
    without repeating completed earlier phases, maintaining audit log trail.
    """
    eval_id = body.evaluation_id
    phase = body.start_phase.lower()

    # Log audit entry
    log = AuditLog(
        log_id=uuid.uuid4(),
        entity_type="evaluation",
        entity_id=str(eval_id),
        action=f"retrigger_{phase}",
        performed_by=body.performed_by,
        remarks=body.remarks,
    )
    db.add(log)
    db.commit()

    # Fetch Phase 4 context to get blueprint_id
    repo_ctx = EvaluationContextRepository(db)
    ctxs = repo_ctx.get_contexts_by_evaluation_id(eval_id)
    bp_id = ctxs[0].blueprint_id if ctxs else None

    if not bp_id:
        bp = db.query(ExamBlueprint).first()
        bp_id = bp.blueprint_id if bp else uuid.uuid4()

    executed_phases: list[str] = []

    if phase in ("phase3_mapping", "phase2_blueprint"):
        Phase3Service(db).run(evaluation_id=eval_id, blueprint_id=bp_id)
        executed_phases.append("Phase 3 - Question Answer Mapping")

    if phase in ("phase4_context", "phase3_mapping", "phase2_blueprint"):
        build_evaluation_context_service(db, eval_id, bp_id)
        executed_phases.append("Phase 4 - Evaluation Context Builder")

    if phase in ("phase5_evaluation", "phase4_context", "phase3_mapping", "phase2_blueprint"):
        await run_phase5_multi_agent_evaluation(db, eval_id)
        executed_phases.append("Phase 5 - Multi-Agent Parallel Evaluation")

    if phase in ("phase6_consensus", "phase5_evaluation", "phase4_context", "phase3_mapping", "phase2_blueprint"):
        run_phase6_consensus_service(db, eval_id)
        executed_phases.append("Phase 6 - Multi-Agent Consensus Engine")

    return {
        "evaluation_id": str(eval_id),
        "retriggered_from": phase,
        "executed_phases": executed_phases,
        "status": "PIPELINE_RETRIGGER_COMPLETED",
    }


@router.get("/evaluations/{evaluation_id}/student-report", response_model=StudentReportResponse, summary="Get Student Breakdown Report")
def get_student_evaluation_report(evaluation_id: uuid.UUID, db: Session = Depends(get_db)):
    """Module 14 – Generates comprehensive question-wise breakdown for student portal."""
    return generate_student_report(db, evaluation_id)


@router.get("/evaluations/{evaluation_id}/download-report", summary="Download Student HTML/PDF Report")
def download_student_evaluation_report(evaluation_id: uuid.UUID, db: Session = Depends(get_db)):
    """Module 14 – Downloads printable HTML/PDF report artifact."""
    report = generate_student_report(db, evaluation_id)
    html_content = generate_html_report_content(report)
    return Response(content=html_content, media_type="text/html", headers={
        "Content-Disposition": f"attachment; filename=Evaluation_Report_{report.student_id}.html"
    })
