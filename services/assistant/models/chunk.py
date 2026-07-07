import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from database import Base

# Output dimension of all-MiniLM-L6-v2. Must match the embedding model used at
# query time — change the model and you must change this and re-embed. See §6.2.
EMBEDDING_DIM = 384


class Chunk(Base):
    """One retrievable slice of course content plus its embedding.

    A course's content is split into chunks (Chunk 4), each embedded (Chunk 3/5)
    and stored here. Retrieval (Chunk 8) filters by course_id, then orders by
    vector distance to the question.
    """

    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # We always filter by course_id first (the student picks the course), so it
    # is indexed. module_id / lesson_id give structural anchors + citations.
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    module_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    lesson_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    content: Mapped[str] = mapped_column(Text, nullable=False)
    # sha256 of normalized text — drives incremental re-embedding
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # Which ingestion generation this chunk belongs to — enables atomic swaps.
    content_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
