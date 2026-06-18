"""add unique enrollment constraint

Revision ID: b3c9f1f9d5a2
Revises: 244f2892fa58
Create Date: 2026-06-03 14:05:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b3c9f1f9d5a2"
down_revision: Union[str, Sequence[str], None] = "244f2892fa58"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Safety: remove any pre-existing duplicates so unique constraint can be applied.
    op.execute(
        """
        DELETE FROM enrollments e
        USING (
            SELECT id
            FROM (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY student_id, course_id
                           ORDER BY enrolled_at ASC, id ASC
                       ) AS rn
                FROM enrollments
            ) ranked
            WHERE ranked.rn > 1
        ) dups
        WHERE e.id = dups.id
        """
    )

    op.create_unique_constraint(
        "uq_enrollments_student_course",
        "enrollments",
        ["student_id", "course_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(
        "uq_enrollments_student_course",
        "enrollments",
        type_="unique",
    )
