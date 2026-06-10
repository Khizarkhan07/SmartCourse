import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course
from app.models.lesson import Lesson
from app.models.module import Module
from app.models.user import User


class CourseRepository:
    """Data-access operations for Course entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_course_by_id(self, course_id: uuid.UUID) -> Course | None:
        result = await self.session.execute(select(Course).where(Course.id == course_id))
        return result.scalar_one_or_none()

    async def get_instructor_by_id(self, instructor_id: uuid.UUID) -> User | None:
        result = await self.session.execute(select(User).where(User.id == instructor_id))
        return result.scalar_one_or_none()

    async def list_active_courses(self, *, limit: int, offset: int) -> list[Course]:
        result = await self.session.execute(
            select(Course)
            .where(Course.is_active.is_(True))
            .order_by(Course.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_lessons(self, course_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.count(Lesson.id))
            .join(Module, Lesson.module_id == Module.id)
            .where(Module.course_id == course_id)
        )
        return int(result.scalar() or 0)
