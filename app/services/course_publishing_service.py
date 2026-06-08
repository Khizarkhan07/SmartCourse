import uuid
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Course, Module, Lesson
from app.models.course import CourseStatus
from app.exceptions import NotFoundError, PermissionDeniedError, ValidationError, InvalidStateError


# Valid state transitions — prevents jumping from draft → archived directly
VALID_TRANSITIONS = {
    CourseStatus.draft: [CourseStatus.published],
    CourseStatus.published: [CourseStatus.archived],
    CourseStatus.archived: [],  # archived is a terminal state
}


async def _validate_course_for_publish(
    db: AsyncSession,
    course: Course,
) -> None:
    """
    Internal validation: ensures a course meets all requirements before publishing.

    Requirements:
        - Must have a title (already enforced by model, sanity check here)
        - Must have a description
        - Must have at least one lesson

    Raises:
        ValidationError: if any requirement is not met
    """
    if not course.description:
        raise ValidationError("Course must have a description before publishing")

    # Count total lessons across all modules in this course
    lesson_count_result = await db.execute(
        select(func.count(Lesson.id))
        .join(Module, Lesson.module_id == Module.id)
        .where(Module.course_id == course.id)
    )
    lesson_count = lesson_count_result.scalar()

    if lesson_count == 0:
        raise ValidationError("Course must have at least one lesson before publishing")


async def publish_course(
    db: AsyncSession,
    course_id: uuid.UUID,
    instructor_id: uuid.UUID,
) -> Course:
    """
    Publish a course (draft → published).

    Validates the course has all required content, then transitions status.

    Raises:
        NotFoundError: if course not found
        PermissionDeniedError: if caller is not the course owner
        InvalidStateError: if course is not in draft status
        ValidationError: if course fails validation
    """
    # Fetch course
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()

    if not course:
        raise NotFoundError("Course not found")

    # Ownership check
    if course.instructor_id != instructor_id:
        raise PermissionDeniedError("You can only publish your own courses")

    # State machine check — must be in draft to publish
    if CourseStatus.published not in VALID_TRANSITIONS[course.status]:
        raise InvalidStateError(f"Cannot publish a course with status '{course.status}'. Only draft courses can be published")

    # Content validation
    await _validate_course_for_publish(db, course)

    # Transition status
    course.status = CourseStatus.published
    await db.commit()
    await db.refresh(course)

    return course


async def archive_course(
    db: AsyncSession,
    course_id: uuid.UUID,
    instructor_id: uuid.UUID,
) -> Course:
    """
    Archive a course (published → archived).

    Archived courses are no longer visible to new students.
    Existing enrollments are unaffected.

    Raises:
        NotFoundError: if course not found
        PermissionDeniedError: if caller is not the course owner
        InvalidStateError: if course is not in published status
    """
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()

    if not course:
        raise NotFoundError("Course not found")

    # Ownership check
    if course.instructor_id != instructor_id:
        raise PermissionDeniedError("You can only archive your own courses")

    # State machine check — must be published to archive
    if CourseStatus.archived not in VALID_TRANSITIONS[course.status]:
        raise InvalidStateError(f"Cannot archive a course with status '{course.status}'. Only published courses can be archived")

    course.status = CourseStatus.archived
    await db.commit()
    await db.refresh(course)

    return course
