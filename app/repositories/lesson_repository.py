import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.course import Course
from app.models.lesson import Lesson
from app.models.module import Module


class LessonRepository:
    """Data-access operations for Lesson entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, lesson_id: uuid.UUID) -> Lesson | None:
        result = await self.session.execute(select(Lesson).where(Lesson.id == lesson_id))
        return result.scalar_one_or_none()

    async def list_by_module(self, module_id: uuid.UUID) -> list[Lesson]:
        result = await self.session.execute(
            select(Lesson).where(Lesson.module_id == module_id).order_by(Lesson.order)
        )
        return list(result.scalars().all())

    async def get_module_by_id(self, module_id: uuid.UUID) -> Module | None:
        result = await self.session.execute(select(Module).where(Module.id == module_id))
        return result.scalar_one_or_none()

    async def get_course_by_id(self, course_id: uuid.UUID) -> Course | None:
        result = await self.session.execute(select(Course).where(Course.id == course_id))
        return result.scalar_one_or_none()
