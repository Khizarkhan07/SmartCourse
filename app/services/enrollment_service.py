import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from app.models import Enrollment, Course, User, CourseStatus
from app.schemas.enrollment import EnrollmentCreate


async def create_enrollment(
    db: AsyncSession,
    data: EnrollmentCreate,
) -> Enrollment:
    """
    Create a new enrollment for a student in a course.

    Idempotent: if the student is already enrolled, returns the existing enrollment.

    Raises:
        HTTPException 404: if course or student not found
        HTTPException 400: if course is not published
    """

    # Step 1: Check if enrollment already exists (idempotency)
    existing = await db.execute(
        select(Enrollment).where(
            (Enrollment.student_id == data.student_id)
            & (Enrollment.course_id == data.course_id)
        )
    )
    enrollment = existing.scalar_one_or_none()

    if enrollment:
        return enrollment  # Already enrolled — return as-is

    # Step 2: Validate course exists and is published
    course_result = await db.execute(select(Course).where(Course.id == data.course_id))
    course = course_result.scalar_one_or_none()

    if not course:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Course {data.course_id} not found",
        )

    if course.status != CourseStatus.published:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Course is not published (status: {course.status})",
        )

    # Step 3: Validate student exists
    student_result = await db.execute(select(User).where(User.id == data.student_id))
    student = student_result.scalar_one_or_none()

    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Student {data.student_id} not found",
        )

    # Step 4: Create new enrollment — progress always starts at 0 (server-controlled)
    new_enrollment = Enrollment(
        student_id=data.student_id,
        course_id=data.course_id,
        progress_percentage=0,
    )

    db.add(new_enrollment)
    await db.commit()
    await db.refresh(new_enrollment)

    return new_enrollment


async def get_enrollment(
    db: AsyncSession,
    enrollment_id: uuid.UUID,
) -> Enrollment:
    """Get a single enrollment by ID. Raises 404 if not found."""
    result = await db.execute(select(Enrollment).where(Enrollment.id == enrollment_id))
    enrollment = result.scalar_one_or_none()

    if not enrollment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enrollment not found",
        )

    return enrollment


async def list_student_enrollments(
    db: AsyncSession,
    student_id: uuid.UUID,
    limit: int = 10,
    offset: int = 0,
) -> list[Enrollment]:
    """List all enrollments for a student with pagination."""
    result = await db.execute(
        select(Enrollment)
        .where(Enrollment.student_id == student_id)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def list_course_students(
    db: AsyncSession,
    course_id: uuid.UUID,
    limit: int = 10,
    offset: int = 0,
) -> list[Enrollment]:
    """List all students enrolled in a course with pagination."""
    result = await db.execute(
        select(Enrollment)
        .where(Enrollment.course_id == course_id)
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())
