"""create chunks table with pgvector embedding + HNSW index

Revision ID: 0001
Revises:
Create Date: 2026-07-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EMBEDDING_DIM = 1536


def upgrade() -> None:
    # Ensure the extension exists even if the DB was created without the init
    # script. Migrations run on every deploy; the init script runs only once.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("course_id", UUID(as_uuid=True), nullable=False),
        sa.Column("module_id", UUID(as_uuid=True), nullable=True),
        sa.Column("lesson_id", UUID(as_uuid=True), nullable=True),
        sa.Column("chunk_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("content_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("embedding", Vector(EMBEDDING_DIM), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
    )

    # We always filter by course_id before similarity search.
    op.create_index("ix_chunks_course_id", "chunks", ["course_id"])
    op.create_index("ix_chunks_content_hash", "chunks", ["content_hash"])

    # HNSW index for approximate-nearest-neighbour search using COSINE distance
    # (vector_cosine_ops pairs with the <=> operator). This is what makes search
    # navigate the graph instead of scanning every row.
    op.execute(
        "CREATE INDEX ix_chunks_embedding_hnsw "
        "ON chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_index("ix_chunks_embedding_hnsw", table_name="chunks")
    op.drop_index("ix_chunks_content_hash", table_name="chunks")
    op.drop_index("ix_chunks_course_id", table_name="chunks")
    op.drop_table("chunks")
