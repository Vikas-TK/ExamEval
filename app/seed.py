"""
Database Seeding Script for AI AutoGrader System.
Seeds 5 sample records into Academic Master, Evaluation Records (Answer Sheets), and Exam Blueprints.
"""

import uuid
from loguru import logger
from sqlalchemy import select

from app.db.database import engine
from app.db.base import Base
from app.db.session import SessionLocal

# Import models to ensure they are registered on Base
from app.academic_master_models import AcademicMaster, AcademicMasterStatus
from app.blueprint_models import ExamBlueprint
from app.models.evaluation import EvaluationRecord, EvaluationStatus, StudentIdentity


def seed_database():
    logger.info("Initializing database tables...")
    Base.metadata.create_all(bind=engine)

    session = SessionLocal()
    try:
        # 1. Seed Academic Master Records (5 items)
        logger.info("Seeding Academic Master records...")
        academic_samples = [
            {
                "academic_year": "2025-26",
                "regulation": "R2021",
                "department": "CSE",
                "semester": "SEM-04",
                "subject_code": "CS8451",
                "subject_name": "Data Structures & Algorithms",
                "credits": 4,
                "status": AcademicMasterStatus.ACTIVE,
                "created_by": "System Admin",
            },
            {
                "academic_year": "2025-26",
                "regulation": "R2021",
                "department": "CSE",
                "semester": "SEM-04",
                "subject_code": "CS8491",
                "subject_name": "Computer Architecture & Organization",
                "credits": 3,
                "status": AcademicMasterStatus.ACTIVE,
                "created_by": "System Admin",
            },
            {
                "academic_year": "2025-26",
                "regulation": "R2021",
                "department": "AI&DS",
                "semester": "SEM-05",
                "subject_code": "CS8591",
                "subject_name": "Programming in Python & Machine Learning",
                "credits": 4,
                "status": AcademicMasterStatus.ACTIVE,
                "created_by": "System Admin",
            },
            {
                "academic_year": "2025-26",
                "regulation": "R2021",
                "department": "ECE",
                "semester": "SEM-03",
                "subject_code": "EC8392",
                "subject_name": "Digital Electronics & Microprocessors",
                "credits": 3,
                "status": AcademicMasterStatus.ACTIVE,
                "created_by": "System Admin",
            },
            {
                "academic_year": "2025-26",
                "regulation": "R2021",
                "department": "IT",
                "semester": "SEM-06",
                "subject_code": "IT8401",
                "subject_name": "Cloud Computing & Distributed Systems",
                "credits": 4,
                "status": AcademicMasterStatus.ACTIVE,
                "created_by": "System Admin",
            },
        ]

        for data in academic_samples:
            existing = session.scalar(
                select(AcademicMaster).where(AcademicMaster.subject_code == data["subject_code"])
            )
            if not existing:
                session.add(AcademicMaster(**data))
        session.commit()

        # 2. Seed Answer Sheet Evaluations & Student Identities (5 items)
        logger.info("Seeding Answer Sheet evaluation records...")
        eval_samples = [
            (
                "10000000-0000-0000-0000-000000000001",
                "312221104001",
                "CS8451",
                "R2021",
                "SEM-04",
                EvaluationStatus.COMPLETED,
                0.94,
                True,
                False,
                92.4,
                140.5,
                25.1,
                0.8,
                False,
                True,
                1200,
                1600,
                8.2,
                True,
                {
                    "pages": [
                        {
                            "page_number": 1,
                            "transcript": "Q1: Explain AVL tree rotations with an example.\nAn AVL tree is a self-balancing binary search tree...",
                            "confidence": 0.95,
                            "visual_elements": [{"type": "diagram", "description": "AVL Tree Rotation Diagram", "bbox": [100.0, 150.0, 400.0, 450.0]}],
                        }
                    ]
                },
            ),
            (
                "10000000-0000-0000-0000-000000000002",
                "312221104002",
                "CS8491",
                "R2021",
                "SEM-04",
                EvaluationStatus.NEEDS_REVIEW,
                0.68,
                False,
                True,
                42.5,
                48.0,
                12.0,
                6.2,
                True,
                False,
                800,
                1000,
                45.0,
                False,
                {
                    "pages": [
                        {
                            "page_number": 1,
                            "transcript": "Q1: Cache Memory Mapping Techniques...",
                            "confidence": 0.68,
                            "visual_elements": [],
                        }
                    ]
                },
            ),
            (
                "10000000-0000-0000-0000-000000000003",
                "312221104003",
                "CS8591",
                "R2021",
                "SEM-05",
                EvaluationStatus.COMPLETED,
                0.98,
                True,
                False,
                110.2,
                155.0,
                32.0,
                0.2,
                False,
                True,
                1400,
                1800,
                5.0,
                True,
                {
                    "pages": [
                        {
                            "page_number": 1,
                            "transcript": "Q1: Define Supervised Learning and Gradient Descent algorithm...",
                            "confidence": 0.98,
                            "visual_elements": [{"type": "graph", "description": "Gradient Descent Loss Curve", "bbox": [50.0, 200.0, 500.0, 600.0]}],
                        }
                    ]
                },
            ),
            (
                "10000000-0000-0000-0000-000000000004",
                "312221104004",
                "EC8392",
                "R2021",
                "SEM-03",
                EvaluationStatus.PROCESSING,
                None,
                True,
                False,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            ),
            (
                "10000000-0000-0000-0000-000000000005",
                "312221104005",
                "IT8401",
                "R2021",
                "SEM-06",
                EvaluationStatus.COMPLETED,
                0.91,
                True,
                False,
                88.5,
                135.0,
                22.0,
                1.1,
                False,
                True,
                1200,
                1600,
                12.0,
                True,
                {
                    "pages": [
                        {
                            "page_number": 1,
                            "transcript": "Q1: Differentiate IaaS, PaaS, and SaaS cloud service models...",
                            "confidence": 0.91,
                            "visual_elements": [{"type": "table", "description": "Comparison Table of Cloud Models", "bbox": [100.0, 100.0, 600.0, 400.0]}],
                        }
                    ]
                },
            ),
        ]

        for eval_id_str, reg_no, subject, reg, sem, status, conf, q_pass, review, blur, bright, contrast, skew, is_skew, qual_pass, w, h, noise, res_pass, ocr in eval_samples:
            eval_id = uuid.UUID(eval_id_str)
            student_hash_val = f"hash_{reg_no}_secret"

            ident = session.get(StudentIdentity, eval_id)
            if not ident:
                ident = StudentIdentity(
                    evaluation_id=eval_id,
                    student_hash=student_hash_val,
                    regulation=reg,
                    semester=sem,
                    subject_id=subject,
                )
                session.add(ident)
                session.commit()

            rec = session.get(EvaluationRecord, eval_id)
            if not rec:
                rec = EvaluationRecord(
                    evaluation_id=eval_id,
                    subject_id=subject,
                    status=status,
                    blur_score=blur,
                    brightness_score=bright,
                    contrast_score=contrast,
                    skew_angle=skew,
                    is_skewed=is_skew,
                    quality_passed=qual_pass,
                    width=w,
                    height=h,
                    noise_score=noise,
                    resolution_passed=res_pass,
                    ocr_data=ocr,
                    needs_manual_review=review,
                    overall_confidence=conf,
                    raw_s3_url=f"https://supabase.co/storage/v1/object/public/question-papers/answer-sheets/original/{eval_id_str}/answersheet.png",
                    enhanced_s3_url=f"https://supabase.co/storage/v1/object/public/question-papers/answer-sheets/processed/{eval_id_str}/answersheet.png",
                    transcript_s3_url=f"https://supabase.co/storage/v1/object/public/evaluation-reports/answer-sheets/transcripts/{eval_id_str}/transcript.txt",
                )
                session.add(rec)
        session.commit()

        # 3. Seed Exam Blueprints (5 items)
        logger.info("Seeding Exam Blueprint records...")
        blueprint_samples = [
            {
                "blueprint_id": uuid.UUID("20000000-0000-0000-0000-000000000001"),
                "exam_name": "End Semester Examination April 2025",
                "subject": "Data Structures & Algorithms",
                "subject_code": "CS8451",
                "regulation": "R2021",
                "semester": "SEM-04",
                "department": "CSE",
                "duration_minutes": 180,
                "maximum_marks": 100.0,
                "sections": [
                    {
                        "section_id": "sec_a",
                        "name": "Part A (10 x 2 = 20 Marks)",
                        "instructions": "Answer all questions",
                        "questions": [
                            {"question_id": "q1", "question_number": "1", "question_text": "Define Stack and Queue.", "maximum_marks": 2, "question_type": "short", "question_order": 1},
                            {"question_id": "q2", "question_number": "2", "question_text": "What is AVL Tree balance factor?", "maximum_marks": 2, "question_type": "short", "question_order": 2},
                        ],
                    },
                    {
                        "section_id": "sec_b",
                        "name": "Part B (5 x 13 = 65 Marks)",
                        "instructions": "Answer all questions choosing either (a) or (b)",
                        "questions": [
                            {"question_id": "q11a", "question_number": "11(a)", "question_text": "Explain Dijkstra shortest path algorithm with example graph.", "maximum_marks": 13, "question_type": "descriptive", "question_order": 3},
                        ],
                    },
                ],
                "source_ocr": {"pages": [{"page_number": 1, "transcript": "CS8451 Data Structures Question Paper"}]},
            },
            {
                "blueprint_id": uuid.UUID("20000000-0000-0000-0000-000000000002"),
                "exam_name": "Mid Semester Assessment I",
                "subject": "Computer Architecture & Organization",
                "subject_code": "CS8491",
                "regulation": "R2021",
                "semester": "SEM-04",
                "department": "CSE",
                "duration_minutes": 90,
                "maximum_marks": 50.0,
                "sections": [
                    {
                        "section_id": "sec_a",
                        "name": "Part A",
                        "instructions": "Answer all questions",
                        "questions": [
                            {"question_id": "q1", "question_number": "1", "question_text": "Explain MIPS instruction formats.", "maximum_marks": 10, "question_type": "descriptive", "question_order": 1},
                        ],
                    }
                ],
                "source_ocr": {"pages": [{"page_number": 1, "transcript": "CS8491 Computer Architecture Question Paper"}]},
            },
            {
                "blueprint_id": uuid.UUID("20000000-0000-0000-0000-000000000003"),
                "exam_name": "Final Theory Examination May 2025",
                "subject": "Programming in Python & Machine Learning",
                "subject_code": "CS8591",
                "regulation": "R2021",
                "semester": "SEM-05",
                "department": "AI&DS",
                "duration_minutes": 180,
                "maximum_marks": 100.0,
                "sections": [
                    {
                        "section_id": "sec_a",
                        "name": "Part A - Fundamentals",
                        "instructions": "Answer all questions",
                        "questions": [
                            {"question_id": "q1", "question_number": "1", "question_text": "Explain Linear vs Logistic Regression.", "maximum_marks": 10, "question_type": "descriptive", "question_order": 1},
                        ],
                    }
                ],
                "source_ocr": {"pages": [{"page_number": 1, "transcript": "CS8591 Python & ML Question Paper"}]},
            },
            {
                "blueprint_id": uuid.UUID("20000000-0000-0000-0000-000000000004"),
                "exam_name": "End Semester Examination",
                "subject": "Digital Electronics & Microprocessors",
                "subject_code": "EC8392",
                "regulation": "R2021",
                "semester": "SEM-03",
                "department": "ECE",
                "duration_minutes": 180,
                "maximum_marks": 100.0,
                "sections": [
                    {
                        "section_id": "sec_a",
                        "name": "Part A",
                        "instructions": "Answer all questions",
                        "questions": [
                            {"question_id": "q1", "question_number": "1", "question_text": "Design 4-bit synchronous binary counter.", "maximum_marks": 16, "question_type": "diagrammatic", "question_order": 1},
                        ],
                    }
                ],
                "source_ocr": {"pages": [{"page_number": 1, "transcript": "EC8392 Digital Electronics Paper"}]},
            },
            {
                "blueprint_id": uuid.UUID("20000000-0000-0000-0000-000000000005"),
                "exam_name": "Continuous Assessment Test II",
                "subject": "Cloud Computing & Distributed Systems",
                "subject_code": "IT8401",
                "regulation": "R2021",
                "semester": "SEM-06",
                "department": "IT",
                "duration_minutes": 90,
                "maximum_marks": 50.0,
                "sections": [
                    {
                        "section_id": "sec_a",
                        "name": "Part A",
                        "instructions": "Answer all questions",
                        "questions": [
                            {"question_id": "q1", "question_number": "1", "question_text": "Explain Kubernetes Pod architecture.", "maximum_marks": 10, "question_type": "descriptive", "question_order": 1},
                        ],
                    }
                ],
                "source_ocr": {"pages": [{"page_number": 1, "transcript": "IT8401 Cloud Computing Paper"}]},
            },
        ]

        for bp_data in blueprint_samples:
            existing = session.get(ExamBlueprint, bp_data["blueprint_id"])
            if not existing:
                session.add(ExamBlueprint(**bp_data))
        session.commit()

        logger.info("Successfully seeded database with sample records for all modules!")
    except Exception as exc:
        session.rollback()
        logger.error(f"Error seeding database: {exc}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    seed_database()
