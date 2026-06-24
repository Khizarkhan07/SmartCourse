"""add_instructor_profiles

Revision ID: 93970d74b7c1
Revises: ce10169691ad
Create Date: 2026-06-24 11:32:49.560346

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '93970d74b7c1'
down_revision: Union[str, None] = 'ce10169691ad'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "instructor_profiles",
        sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("email", sa.String(500), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("instructor_profiles")
