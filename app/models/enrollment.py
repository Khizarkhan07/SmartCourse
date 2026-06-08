import uuid
from datetime import datetime, timezone
import enum

from sqlalchemy import DateTime, ForeignKey, Enum as SAEnum, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class EnrollmentStatus(str, enum.Enum):
    enrolled = "enrolled"
    dropped = "dropped"
    completed = "completed"


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("student_id", "course_id", name="uq_enrollments_student_course"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    course_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[EnrollmentStatus] = mapped_column(
        SAEnum(EnrollmentStatus), nullable=False, default=EnrollmentStatus.enrolled
    )
    progress_percentage: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enrolled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    student: Mapped["User"] = relationship("User", lazy="selectin")
    course: Mapped["Course"] = relationship("Course", lazy="selectin")
