"""drop stale unique constraint on answer_evaluations.evaluation_id

answer_evaluations is one row PER QUESTION per evaluation (see
app/phase4/models.py), but the live table carries a leftover UNIQUE
(evaluation_id) constraint from an earlier draft of the schema, before it
was one row per evaluation. It blocks inserting more than one question's
score per evaluation, which is the whole point of the table.

Five other tables (accuracy_reports, completeness_reports, depth_reports,
evaluation_contexts, consolidated_evaluations) each carry a REDUNDANT second
foreign key on evaluation_id pointing at answer_evaluations(evaluation_id) —
on top of the correct, model-defined FK to student_identity(evaluation_id)
every one of them already has. These redundant FKs are what's pinning the
stale unique constraint in place; none of them are declared in any current
SQLAlchemy model, so they're dropped first, then the constraint itself.

No migration ever created any of this — it predates migration tracking for
these tables — so none of it is reflected in any prior revision either.

Revision ID: 0007
Revises: 0006
"""
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

_REDUNDANT_FKS = [
    ("fk_accuracy_evaluation", "accuracy_reports"),
    ("fk_completeness_evaluation", "completeness_reports"),
    ("fk_depth_evaluation", "depth_reports"),
    ("fk_context_evaluation", "evaluation_contexts"),
    ("fk_consolidated_evaluation", "consolidated_evaluations"),
]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    for fk_name, table_name in _REDUNDANT_FKS:
        op.drop_constraint(fk_name, table_name, type_="foreignkey")
    op.drop_constraint(
        "uq_answer_evaluations_evaluation_id",
        "answer_evaluations",
        type_="unique",
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    op.create_unique_constraint(
        "uq_answer_evaluations_evaluation_id",
        "answer_evaluations",
        ["evaluation_id"],
    )
    for fk_name, table_name in _REDUNDANT_FKS:
        op.create_foreign_key(
            fk_name,
            table_name,
            "answer_evaluations",
            ["evaluation_id"],
            ["evaluation_id"],
            ondelete="CASCADE",
        )
