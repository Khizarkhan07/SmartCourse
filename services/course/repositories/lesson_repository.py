import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.lesson import Lesson
from models.module import Module


class LessonRepository:
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

    async def count_by_course(self, course_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.count(Lesson.id))
            .join(Module, Lesson.module_id == Module.id)
            .where(Module.course_id == course_id)
        )
        return int(result.scalar() or 0)
