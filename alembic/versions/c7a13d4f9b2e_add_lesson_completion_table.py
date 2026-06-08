"""add lesson completion table

Revision ID: c7a13d4f9b2e
Revises: b3c9f1f9d5a2
Create Date: 2026-06-08 13:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "c7a13d4f9b2e"
down_revision: Union[str, Sequence[str], None] = "b3c9f1f9d5a2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "lesson_completions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("student_id", sa.UUID(), nullable=False),
        sa.Column("lesson_id", sa.UUID(), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["lesson_id"], ["lessons.id"]),
        sa.ForeignKeyConstraint(["student_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "student_id", "lesson_id", name="uq_lesson_completions_student_lesson"
        ),
    )
    op.create_index(
        op.f("ix_lesson_completions_student_id"),
        "lesson_completions",
        ["student_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_lesson_completions_lesson_id"),
        "lesson_completions",
        ["lesson_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_lesson_completions_lesson_id"), table_name="lesson_completions")
    op.drop_index(op.f("ix_lesson_completions_student_id"), table_name="lesson_completions")
    op.drop_table("lesson_completions")
