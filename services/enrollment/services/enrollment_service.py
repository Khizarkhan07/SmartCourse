import uuid
from sqlalchemy.ext.asyncio import AsyncSession

from clients.course_client import CourseClient
from core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from core.logging import get_logger
from models.enrollment import Enrollment, EnrollmentStatus
from models.lesson_completion import LessonCompletion
from repositories.enrollment_repository import EnrollmentRepository

logger = get_logger(__name__)


def _repo(session: AsyncSession) -> EnrollmentRepository:
    return EnrollmentRepository(session)


async def create_enrollment(
    session: AsyncSession,
    course_client: CourseClient,
    student_id: uuid.UUID,
    course_id: uuid.UUID,
) -> Enrollment:
    """
    Idempotent enrollment. Validates the course is published via cross-service call
    before writing. Returns the existing enrollment if already enrolled.
    """
    repo = _repo(session)

    existing = await repo.get_by_student_course(student_id, course_id)
    if existing:
        return existing

    await course_client.check_course_published(course_id)

    enrollment = Enrollment(student_id=student_id, course_id=course_id)
    session.add(enrollment)
    await session.commit()
    await session.refresh(enrollment)
    return enrollment


async def get_enrollment(
    session: AsyncSession,
    enrollment_id: uuid.UUID,
) -> Enrollment:
    enrollment = await _repo(session).get_by_id(enrollment_id)
    if not enrollment:
        raise NotFoundError("Enrollment not found")
    return enrollment


async def list_student_enrollments(
    session: AsyncSession,
    student_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0,
) -> list[Enrollment]:
    return await _repo(session).list_by_student(student_id, limit=limit, offset=offset)


async def list_course_students(
    session: AsyncSession,
    course_id: uuid.UUID,
    limit: int = 20,
    offset: int = 0,
) -> list[Enrollment]:
    return await _repo(session).list_by_course(course_id, limit=limit, offset=offset)


async def mark_lesson_complete(
    session: AsyncSession,
    course_client: CourseClient,
    lesson_id: uuid.UUID,
    student_id: uuid.UUID,
) -> Enrollment:
    """
    Mark a lesson as complete and update enrollment progress.

    Resolves course_id from lesson_id via course-service (no longer requires
    the caller to supply it). Total lesson count also comes from course-service,
    so progress_percentage is now accurate.
    """
    course_id = await course_client.get_lesson_course(lesson_id)

    repo = _repo(session)
    enrollment = await repo.get_by_student_course(student_id=student_id, course_id=course_id)
    if not enrollment:
        raise ValidationError("Student is not enrolled in this course")

    completion = await repo.get_lesson_completion(student_id=student_id, lesson_id=lesson_id)
    if completion is None:
        session.add(LessonCompletion(
            student_id=student_id,
            lesson_id=lesson_id,
            course_id=course_id,
        ))

    completed = await repo.count_completed_lessons(student_id, course_id)
    total = await course_client.count_course_lessons(course_id)

    if total > 0:
        progress = int(round((completed / total) * 100))
        enrollment.progress_percentage = progress
        if progress >= 100:
            enrollment.status = EnrollmentStatus.completed

    await session.commit()
    await session.refresh(enrollment)

    logger.info(
        "lesson marked complete",
        student_id=str(student_id),
        lesson_id=str(lesson_id),
        course_id=str(course_id),
        completed=completed,
        total=total,
    )

    # TODO: Chunk 24 — trigger CourseCompletionWorkflow via Temporal when progress == 100
    return enrollment


async def get_enrollment_progress(
    session: AsyncSession,
    course_client: CourseClient,
    enrollment_id: uuid.UUID,
    student_id: uuid.UUID,
    role: str,
) -> dict:
    enrollment = await get_enrollment(session, enrollment_id)

    if role == "student" and enrollment.student_id != student_id:
        raise PermissionDeniedError("You can only view your own enrollment progress")

    repo = _repo(session)
    completed = await repo.count_completed_lessons(enrollment.student_id, enrollment.course_id)
    total = await course_client.count_course_lessons(enrollment.course_id)

    if total > 0:
        progress = int(round((completed / total) * 100))
        if enrollment.progress_percentage != progress:
            enrollment.progress_percentage = progress
            if progress >= 100:
                enrollment.status = EnrollmentStatus.completed
            await session.commit()
            await session.refresh(enrollment)

    return {
        "enrollment_id": enrollment.id,
        "student_id": enrollment.student_id,
        "course_id": enrollment.course_id,
        "progress_percentage": enrollment.progress_percentage,
        "completed_lessons": completed,
        "total_lessons": total,
        "enrollment_status": enrollment.status,
    }
