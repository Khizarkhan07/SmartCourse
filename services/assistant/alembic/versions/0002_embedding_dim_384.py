"""change embedding dimension 1536 -> 384 for all-MiniLM-L6-v2

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-06

We switched the embedding model to all-MiniLM-L6-v2 (self-hosted, 384-dim).
The vector column dimension must match the model's output exactly, so we
resize it. Safe here because the table holds no rows yet.

A vector index is tied to its column's dimension, so we drop the HNSW index,
alter the column, then recreate the index.

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw")
    op.execute("ALTER TABLE chunks ALTER COLUMN embedding TYPE vector(384)")
    op.execute(
        "CREATE INDEX ix_chunks_embedding_hnsw "
        "ON chunks USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_chunks_embedding_hnsw")
    op.execute("ALTER TABLE chunks ALTER COLUMN embedding TYPE vector(1536)")
    op.execute(
        "CREATE INDEX ix_chunks_embedding_hnsw "
        "ON chunks USING hnsw (embedding vector_cosine_ops)"
    )
