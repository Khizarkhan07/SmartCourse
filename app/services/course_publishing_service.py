import uuid

from app.models import Course
from app.models.course import CourseStatus
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError, InvalidStateError
from app.infrastructure.database.unit_of_work import UnitOfWork
from app.repositories.course_repository import CourseRepository


def _courses_repo(uow: UnitOfWork) -> CourseRepository:
    if uow.courses is None:
        raise RuntimeError("UnitOfWork is not initialized")
    return uow.courses


# Valid state transitions — prevents jumping from draft → archived directly
VALID_TRANSITIONS = {
    CourseStatus.draft: [CourseStatus.published],
    CourseStatus.published: [CourseStatus.archived],
    CourseStatus.archived: [],  # archived is a terminal state
}


async def _validate_course_for_publish(
    uow: UnitOfWork,
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
    lesson_count = await _courses_repo(uow).count_lessons(course.id)

    if lesson_count == 0:
        raise ValidationError("Course must have at least one lesson before publishing")


async def publish_course(
    uow: UnitOfWork,
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
    course = await _courses_repo(uow).get_course_by_id(course_id)

    if not course:
        raise NotFoundError("Course not found")

    # Ownership check
    if course.instructor_id != instructor_id:
        raise PermissionDeniedError("You can only publish your own courses")

    # State machine check — must be in draft to publish
    if CourseStatus.published not in VALID_TRANSITIONS[course.status]:
        raise InvalidStateError(f"Cannot publish a course with status '{course.status}'. Only draft courses can be published")

    # Content validation
    await _validate_course_for_publish(uow, course)

    # Transition status
    course.status = CourseStatus.published
    if uow.session is None:
        raise RuntimeError("UnitOfWork session is not initialized")

    await uow.commit()
    await uow.session.refresh(course)

    return course


async def archive_course(
    uow: UnitOfWork,
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
    course = await _courses_repo(uow).get_course_by_id(course_id)

    if not course:
        raise NotFoundError("Course not found")

    # Ownership check
    if course.instructor_id != instructor_id:
        raise PermissionDeniedError("You can only archive your own courses")

    # State machine check — must be published to archive
    if CourseStatus.archived not in VALID_TRANSITIONS[course.status]:
        raise InvalidStateError(f"Cannot archive a course with status '{course.status}'. Only published courses can be archived")

    course.status = CourseStatus.archived
    if uow.session is None:
        raise RuntimeError("UnitOfWork session is not initialized")

    await uow.commit()
    await uow.session.refresh(course)

    return course
