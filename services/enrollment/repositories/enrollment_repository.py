import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.enrollment import Enrollment
from models.lesson_completion import LessonCompletion


class EnrollmentRepository:
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
            .order_by(Enrollment.enrolled_at.desc())
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
            .order_by(Enrollment.enrolled_at.desc())
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

    async def count_completed_lessons(
        self,
        student_id: uuid.UUID,
        course_id: uuid.UUID,
    ) -> int:
        result = await self.session.execute(
            select(func.count(LessonCompletion.id)).where(
                LessonCompletion.student_id == student_id,
                LessonCompletion.course_id == course_id,
            )
        )
        return int(result.scalar() or 0)

