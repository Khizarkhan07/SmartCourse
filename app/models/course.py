import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.infrastructure.database import Base
import enum

if TYPE_CHECKING:
    from app.models.user import User


class CourseStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    archived = "archived"


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    status: Mapped[CourseStatus] = mapped_column(
        SAEnum(CourseStatus), nullable=False, default=CourseStatus.draft
    )
    instructor_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationship — lets you do course.instructor to get the User object
    instructor: Mapped["User"] = relationship("User", lazy="selectin")
