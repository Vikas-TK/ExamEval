"""create academic master table

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    status_enum = sa.Enum("ACTIVE", "INACTIVE", name="academicmasterstatus")
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        status_enum.create(bind, checkfirst=True)
    op.create_table(
        "academic_master",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("academic_year", sa.String(length=20), nullable=False),
        sa.Column("regulation", sa.String(length=50), nullable=False),
        sa.Column("department", sa.String(length=100), nullable=False),
        sa.Column("semester", sa.String(length=20), nullable=False),
        sa.Column("subject_code", sa.String(length=50), nullable=False),
        sa.Column("subject_name", sa.String(length=200), nullable=False),
        sa.Column("credits", sa.Integer(), nullable=True),
        sa.Column("status", status_enum, nullable=False, server_default="ACTIVE"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("subject_code"),
    )
    op.create_index("ix_academic_master_subject_code", "academic_master", ["subject_code"], unique=True)
    op.create_index("ix_academic_master_status", "academic_master", ["status"], unique=False)
    op.create_index("ix_academic_master_filters", "academic_master", ["academic_year", "regulation", "department", "semester", "status"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_academic_master_filters", table_name="academic_master")
    op.drop_index("ix_academic_master_status", table_name="academic_master")
    op.drop_index("ix_academic_master_subject_code", table_name="academic_master")
    op.drop_table("academic_master")
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        sa.Enum(name="academicmasterstatus").drop(bind, checkfirst=True)
