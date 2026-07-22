"""replace plaintext identity with keyed hash and add transcript artifact

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa
import hashlib
import hmac
import os

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("student_identity", sa.Column("student_hash", sa.String(length=64), nullable=True))
    secret = os.getenv("IDENTITY_HASH_SECRET")
    if not secret:
        raise RuntimeError("IDENTITY_HASH_SECRET is required to migrate student identities")
    connection = op.get_bind()
    rows = connection.execute(sa.text("SELECT evaluation_id, register_number FROM student_identity"))
    for evaluation_id, register_number in rows:
        digest = hmac.new(secret.encode(), register_number.strip().casefold().encode(), hashlib.sha256).hexdigest()
        connection.execute(
            sa.text("UPDATE student_identity SET student_hash = :digest WHERE evaluation_id = :id"),
            {"digest": digest, "id": evaluation_id},
        )
    with op.batch_alter_table("student_identity") as batch_op:
        batch_op.alter_column("student_hash", nullable=False)
        batch_op.create_index("ix_student_identity_student_hash", ["student_hash"])
        try:
            batch_op.drop_index("ix_student_identity_register_number")
        except Exception:
            pass
        batch_op.drop_column("register_number")
    op.add_column("evaluation_records", sa.Column("transcript_s3_url", sa.String(), nullable=True))
    op.add_column("exam_blueprints", sa.Column("blueprint_s3_url", sa.String(), nullable=True))


def downgrade() -> None:
    op.add_column("student_identity", sa.Column("register_number", sa.String(), nullable=True))
    op.drop_index("ix_student_identity_student_hash", table_name="student_identity")
    op.drop_column("student_identity", "student_hash")
    op.drop_column("evaluation_records", "transcript_s3_url")
    op.drop_column("exam_blueprints", "blueprint_s3_url")