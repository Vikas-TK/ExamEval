"""add reusable exam blueprints

Revision ID: 0002
Revises: 0001
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "exam_blueprints",
        sa.Column("blueprint_id", postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite"), primary_key=True),
        sa.Column("exam_name", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("subject_code", sa.String(length=100), nullable=False),
        sa.Column("regulation", sa.String(length=100), nullable=False),
        sa.Column("semester", sa.String(length=100), nullable=False),
        sa.Column("department", sa.String(length=255), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("maximum_marks", sa.Float(), nullable=False),
        sa.Column("sections", postgresql.JSONB().with_variant(sa.JSON(), "sqlite"), nullable=False),
        sa.Column("source_ocr", postgresql.JSONB().with_variant(sa.JSON(), "sqlite"), nullable=False),
        sa.Column("faculty_answer_key", postgresql.JSONB().with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("exam_name", "subject_code", "regulation", "semester",
                            name="uq_exam_blueprint_identity"),
    )
    op.create_index("ix_exam_blueprints_subject_code", "exam_blueprints", ["subject_code"])


def downgrade() -> None:
    op.drop_index("ix_exam_blueprints_subject_code", table_name="exam_blueprints")
    op.drop_table("exam_blueprints")