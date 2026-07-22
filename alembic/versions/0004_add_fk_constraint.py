"""add foreign key constraint between student identity and evaluation records

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("evaluation_records") as batch_op:
        batch_op.create_foreign_key(
            "fk_evaluation_records_student_identity",
            "student_identity",
            ["evaluation_id"],
            ["evaluation_id"],
            ondelete="CASCADE"
        )


def downgrade() -> None:
    op.drop_constraint("fk_evaluation_records_student_identity", "evaluation_records", type_="foreignkey")
