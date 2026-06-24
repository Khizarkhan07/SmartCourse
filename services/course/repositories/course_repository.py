import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from models.course import Course
from models.instructor_profile import InstructorProfile
from models.lesson import Lesson
from models.module import Module


class CourseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, course_id: uuid.UUID) -> Course | None:
        result = await self.session.execute(
            select(Course, InstructorProfile.name, InstructorProfile.email)
            .outerjoin(InstructorProfile, Course.instructor_id == InstructorProfile.id)
            .where(Course.id == course_id)
        )
        row = result.first()
        if not row:
            return None
        course, instr_name, instr_email = row
        course.instructor_name = instr_name
        course.instructor_email = instr_email
        return course

    async def list_active(self, *, limit: int, offset: int) -> list[Course]:
        result = await self.session.execute(
            select(Course, InstructorProfile.name, InstructorProfile.email)
            .outerjoin(InstructorProfile, Course.instructor_id == InstructorProfile.id)
            .where(Course.is_active.is_(True))
            .order_by(Course.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        courses = []
        for course, instr_name, instr_email in result.all():
            course.instructor_name = instr_name
            course.instructor_email = instr_email
            courses.append(course)
        return courses

    async def count_lessons(self, course_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.count(Lesson.id))
            .join(Module, Lesson.module_id == Module.id)
            .where(Module.course_id == course_id)
        )
        return int(result.scalar() or 0)
