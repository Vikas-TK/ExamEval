"""add faculty_answer_key_s3_url column to exam blueprints

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("exam_blueprints", sa.Column("faculty_answer_key_s3_url", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("exam_blueprints", "faculty_answer_key_s3_url")
