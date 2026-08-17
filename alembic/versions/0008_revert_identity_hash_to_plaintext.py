"""revert student identity hashing back to plaintext register_number

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("student_identity", sa.Column("register_number", sa.String(), nullable=True))
    with op.batch_alter_table("student_identity") as batch_op:
        batch_op.create_index("ix_student_identity_register_number", ["register_number"])
        try:
            batch_op.drop_index("ix_student_identity_student_hash")
        except Exception:
            pass
        batch_op.drop_column("student_hash")


def downgrade() -> None:
    op.add_column("student_identity", sa.Column("student_hash", sa.String(length=64), nullable=True))
    with op.batch_alter_table("student_identity") as batch_op:
        batch_op.create_index("ix_student_identity_student_hash", ["student_hash"])
        try:
            batch_op.drop_index("ix_student_identity_register_number")
        except Exception:
            pass
        batch_op.drop_column("register_number")
