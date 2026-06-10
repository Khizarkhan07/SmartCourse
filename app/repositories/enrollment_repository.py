import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enrollment import Enrollment
from app.models.lesson import Lesson
from app.models.lesson_completion import LessonCompletion
from app.models.module import Module


class EnrollmentRepository:
    """Data-access operations for Enrollment entities."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, enrollment_id: uuid.UUID) -> Enrollment | None:
        result = await self.session.execute(
            select(Enrollment).where(Enrollment.id == enrollment_id)
        )
        return result.scalar_one_or_none()

    async def list_by_student(
        self,
        student_id: uuid.UUID,
        *,
        limit: int,
        offset: int,
    ) -> list[Enrollment]:
        result = await self.session.execute(
            select(Enrollment)
            .where(Enrollment.student_id == student_id)
            .order_by(Enrollment.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def list_by_course(
        self,
        course_id: uuid.UUID,
        *,
        limit: int,
        offset: int,
    ) -> list[Enrollment]:
        result = await self.session.execute(
            select(Enrollment)
            .where(Enrollment.course_id == course_id)
            .order_by(Enrollment.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_by_student_course(
        self,
        student_id: uuid.UUID,
        course_id: uuid.UUID,
    ) -> Enrollment | None:
        result = await self.session.execute(
            select(Enrollment).where(
                Enrollment.student_id == student_id,
                Enrollment.course_id == course_id,
            )
        )
        return result.scalar_one_or_none()

    async def get_lesson_completion(
        self,
        student_id: uuid.UUID,
        lesson_id: uuid.UUID,
    ) -> LessonCompletion | None:
        result = await self.session.execute(
            select(LessonCompletion).where(
                LessonCompletion.student_id == student_id,
                LessonCompletion.lesson_id == lesson_id,
            )
        )
        return result.scalar_one_or_none()

    async def count_total_lessons(self, course_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.count(Lesson.id))
            .join(Module, Lesson.module_id == Module.id)
            .where(Module.course_id == course_id)
        )
        return int(result.scalar() or 0)

    async def count_completed_lessons(
        self,
        student_id: uuid.UUID,
        course_id: uuid.UUID,
    ) -> int:
        result = await self.session.execute(
            select(func.count(LessonCompletion.id))
            .join(Lesson, LessonCompletion.lesson_id == Lesson.id)
            .join(Module, Lesson.module_id == Module.id)
            .where(
                LessonCompletion.student_id == student_id,
                Module.course_id == course_id,
            )
        )
        return int(result.scalar() or 0)

    async def get_lesson_by_id(self, lesson_id: uuid.UUID) -> Lesson | None:
        result = await self.session.execute(select(Lesson).where(Lesson.id == lesson_id))
        return result.scalar_one_or_none()

    async def get_module_by_id(self, module_id: uuid.UUID) -> Module | None:
        result = await self.session.execute(select(Module).where(Module.id == module_id))
        return result.scalar_one_or_none()
