import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import NotFoundError, PermissionDeniedError
from models.course import Course, CourseStatus
from repositories.course_repository import CourseRepository
from schemas.course import CourseCreate, CourseUpdate


async def create_course(session: AsyncSession, data: CourseCreate, instructor_id: uuid.UUID) -> Course:
    # Role is already validated by the route dependency (requires instructor or admin).
    # No cross-service call to identity needed — we trust the JWT claim.
    course = Course(
        title=data.title,
        description=data.description,
        instructor_id=instructor_id,
        status=CourseStatus.draft,
    )
    session.add(course)
    await session.commit()
    await session.refresh(course)
    return course


async def get_course(session: AsyncSession, course_id: uuid.UUID) -> Course:
    course = await CourseRepository(session).get_by_id(course_id)
    if not course:
        raise NotFoundError("Course not found")
    return course


async def list_courses(session: AsyncSession, *, limit: int, offset: int) -> list[Course]:
    return await CourseRepository(session).list_active(limit=limit, offset=offset)


async def update_course(
    session: AsyncSession,
    course_id: uuid.UUID,
    caller_id: uuid.UUID,
    caller_role: str,
    data: CourseUpdate,
) -> Course:
    course = await get_course(session, course_id)
    if caller_role != "admin" and course.instructor_id != caller_id:
        raise PermissionDeniedError("You can only update your own courses")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(course, field, value)
    await session.commit()
    await session.refresh(course)
    return course
