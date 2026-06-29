"""create enrollment tables

Revision ID: 0001
Revises:
Create Date: 2026-06-24

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "enrollments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "status",
            sa.Enum("enrolled", "dropped", "completed", name="enrollmentstatus"),
            nullable=False,
            server_default="enrolled",
        ),
        sa.Column("progress_percentage", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "enrolled_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("student_id", "course_id", name="uq_enrollments_student_course"),
    )
    op.create_index("ix_enrollments_student_id", "enrollments", ["student_id"])
    op.create_index("ix_enrollments_course_id", "enrollments", ["course_id"])

    op.create_table(
        "lesson_completions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("student_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lesson_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "completed_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "student_id", "lesson_id", name="uq_lesson_completions_student_lesson"
        ),
    )
    op.create_index("ix_lesson_completions_student_id", "lesson_completions", ["student_id"])
    op.create_index("ix_lesson_completions_lesson_id", "lesson_completions", ["lesson_id"])
    op.create_index("ix_lesson_completions_course_id", "lesson_completions", ["course_id"])


def downgrade() -> None:
    op.drop_table("lesson_completions")
    op.drop_table("enrollments")
    op.execute("DROP TYPE IF EXISTS enrollmentstatus")
