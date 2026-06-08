import uuid
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models import Course, Module, Lesson
from app.models.course import CourseStatus


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
        HTTPException 400: if any requirement is not met
    """
    if not course.description:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Course must have a description before publishing",
        )

    # Count total lessons across all modules in this course
    lesson_count_result = await db.execute(
        select(func.count(Lesson.id))
        .join(Module, Lesson.module_id == Module.id)
        .where(Module.course_id == course.id)
    )
    lesson_count = lesson_count_result.scalar()

    if lesson_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Course must have at least one lesson before publishing",
        )


async def publish_course(
    db: AsyncSession,
    course_id: uuid.UUID,
    instructor_id: uuid.UUID,
) -> Course:
    """
    Publish a course (draft → published).

    Validates the course has all required content, then transitions status.

    Raises:
        HTTPException 404: if course not found
        HTTPException 403: if caller is not the course owner
        HTTPException 400: if course is not in draft status or fails validation
    """
    # Fetch course
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()

    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )

    # Ownership check
    if course.instructor_id != instructor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only publish your own courses",
        )

    # State machine check — must be in draft to publish
    if CourseStatus.published not in VALID_TRANSITIONS[course.status]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot publish a course with status '{course.status}'. Only draft courses can be published",
        )

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
        HTTPException 404: if course not found
        HTTPException 403: if caller is not the course owner
        HTTPException 400: if course is not in published status
    """
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()

    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Course not found",
        )

    # Ownership check
    if course.instructor_id != instructor_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only archive your own courses",
        )

    # State machine check — must be published to archive
    if CourseStatus.archived not in VALID_TRANSITIONS[course.status]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot archive a course with status '{course.status}'. Only published courses can be archived",
        )

    course.status = CourseStatus.archived
    await db.commit()
    await db.refresh(course)

    return course
