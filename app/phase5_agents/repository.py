"""
Phase 5 – Repository for Agent Reports
Saves AccuracyReport, CompletenessReport, and DepthReport records to PostgreSQL.
"""
from __future__ import annotations

import uuid
import logging
from typing import List, Tuple, Optional
from sqlalchemy.orm import Session

from app.phase5_agents.models import AccuracyReport, CompletenessReport, DepthReport

logger = logging.getLogger(__name__)


class AgentReportsRepository:
    def __init__(self, db: Session):
        self.db = db

    def save_reports(
        self,
        evaluation_id: uuid.UUID,
        blueprint_id: Optional[uuid.UUID],
        question_id: str,
        question_number: str,
        accuracy_data: dict,
        completeness_data: dict,
        depth_data: dict,
    ) -> Tuple[AccuracyReport, CompletenessReport, DepthReport]:
        """Saves independent accuracy, completeness, and depth reports."""
        acc_rec = AccuracyReport(
            report_id=uuid.uuid4(),
            evaluation_id=evaluation_id,
            blueprint_id=blueprint_id,
            question_id=question_id,
            question_number=question_number,
            score=float(accuracy_data.get("score", 0.0)),
            percentage=float(accuracy_data.get("percentage", 0.0)),
            confidence=float(accuracy_data.get("confidence", 1.0)),
            correct_concepts=accuracy_data.get("correct_concepts", []),
            incorrect_concepts=accuracy_data.get("incorrect_concepts", []),
            technical_errors=accuracy_data.get("technical_errors", []),
            remarks=accuracy_data.get("remarks"),
            status=accuracy_data.get("status", "COMPLETED"),
        )

        cmp_rec = CompletenessReport(
            report_id=uuid.uuid4(),
            evaluation_id=evaluation_id,
            blueprint_id=blueprint_id,
            question_id=question_id,
            question_number=question_number,
            score=float(completeness_data.get("score", 0.0)),
            percentage=float(completeness_data.get("percentage", 0.0)),
            confidence=float(completeness_data.get("confidence", 1.0)),
            covered_points=completeness_data.get("covered_points", []),
            missing_points=completeness_data.get("missing_points", []),
            missing_keywords=completeness_data.get("missing_keywords", []),
            missing_concepts=completeness_data.get("missing_concepts", []),
            remarks=completeness_data.get("remarks"),
            status=completeness_data.get("status", "COMPLETED"),
        )

        dph_rec = DepthReport(
            report_id=uuid.uuid4(),
            evaluation_id=evaluation_id,
            blueprint_id=blueprint_id,
            question_id=question_id,
            question_number=question_number,
            score=float(depth_data.get("score", 0.0)),
            percentage=float(depth_data.get("percentage", 0.0)),
            confidence=float(depth_data.get("confidence", 1.0)),
            strong_sections=depth_data.get("strong_sections", []),
            weak_sections=depth_data.get("weak_sections", []),
            remarks=depth_data.get("remarks"),
            status=depth_data.get("status", "COMPLETED"),
        )

        self.db.add_all([acc_rec, cmp_rec, dph_rec])
        try:
            self.db.commit()
            self.db.refresh(acc_rec)
            self.db.refresh(cmp_rec)
            self.db.refresh(dph_rec)
        except Exception:
            self.db.rollback()
            raise

        return acc_rec, cmp_rec, dph_rec

    def get_reports_by_evaluation(
        self, evaluation_id: uuid.UUID
    ) -> Tuple[List[AccuracyReport], List[CompletenessReport], List[DepthReport]]:
        """Retrieves all agent reports for an evaluation_id."""
        acc_list = self.db.query(AccuracyReport).filter_by(evaluation_id=evaluation_id).all()
        cmp_list = self.db.query(CompletenessReport).filter_by(evaluation_id=evaluation_id).all()
        dph_list = self.db.query(DepthReport).filter_by(evaluation_id=evaluation_id).all()
        return acc_list, cmp_list, dph_list
