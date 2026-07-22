"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-07-22

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "student_identity",
        sa.Column("evaluation_id", postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite"), primary_key=True),
        sa.Column("register_number", sa.String(), nullable=False, index=True),
        sa.Column("regulation", sa.String(), nullable=False),
        sa.Column("semester", sa.String(), nullable=False),
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "evaluation_records",
        sa.Column("evaluation_id", postgresql.UUID(as_uuid=True).with_variant(sa.String(36), "sqlite"), primary_key=True),
        sa.Column("subject_id", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("PROCESSING", "COMPLETED", "NEEDS_REVIEW", "FAILED", name="evaluationstatus").with_variant(sa.String(), "sqlite"),
            nullable=False,
            server_default="PROCESSING",
        ),
        sa.Column("blur_score", sa.Float(), nullable=True),
        sa.Column("brightness_score", sa.Float(), nullable=True),
        sa.Column("contrast_score", sa.Float(), nullable=True),
        sa.Column("skew_angle", sa.Float(), nullable=True),
        sa.Column("is_skewed", sa.Boolean(), nullable=True),
        sa.Column("quality_passed", sa.Boolean(), nullable=True),
        sa.Column("width", sa.Float(), nullable=True),
        sa.Column("height", sa.Float(), nullable=True),
        sa.Column("noise_score", sa.Float(), nullable=True),
        sa.Column("resolution_passed", sa.Boolean(), nullable=True),
        sa.Column("ocr_data", postgresql.JSONB().with_variant(sa.JSON(), "sqlite"), nullable=True),
        sa.Column("needs_manual_review", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("overall_confidence", sa.Float(), nullable=True),
        sa.Column("raw_s3_url", sa.String(), nullable=True),
        sa.Column("enhanced_s3_url", sa.String(), nullable=True),
        sa.Column("error_message", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_evaluation_records_status_created_at", "evaluation_records", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_evaluation_records_status_created_at", table_name="evaluation_records")
    op.drop_table("evaluation_records")
    op.drop_table("student_identity")
    op.execute("DROP TYPE IF EXISTS evaluationstatus")
