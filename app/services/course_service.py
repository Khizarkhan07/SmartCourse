import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.course import Course, CourseStatus
from app.models.user import User, UserRole
from app.schemas.course import CourseCreate, CourseUpdate
from app.exceptions import NotFoundError, PermissionDeniedError, ValidationError


async def create_course(db: AsyncSession, data: CourseCreate, instructor_id: uuid.UUID) -> Course:
    """
    Create a new course.
    - Verifies the instructor exists and has the instructor role
    - Course starts as 'draft' — publishing is a separate workflow
    
    Raises:
        NotFoundError: if instructor not found
        ValidationError: if instructor does not have instructor role
    """
    # Verify the instructor exists and is actually an instructor
    result = await db.execute(select(User).where(User.id == instructor_id))
    instructor = result.scalar_one_or_none()

    if not instructor:
        raise NotFoundError("Instructor not found")

    if instructor.role != UserRole.instructor:
        raise ValidationError("Only users with the instructor role can create courses")

    new_course = Course(
        title=data.title,
        description=data.description,
        instructor_id=instructor_id,
        status=CourseStatus.draft,   # always starts as draft
    )

    db.add(new_course)
    await db.commit()
    await db.refresh(new_course)
    return new_course


async def get_course_by_id(db: AsyncSession, course_id: uuid.UUID) -> Course:
    """Fetch a single course by ID. Raises NotFoundError if not found."""
    result = await db.execute(select(Course).where(Course.id == course_id))
    course = result.scalar_one_or_none()

    if not course:
        raise NotFoundError("Course not found")
    return course


async def list_courses(db: AsyncSession, limit: int = 20, offset: int = 0) -> list[Course]:
    """Return active courses with pagination. Default page size is 20. Ordered by creation date (newest first)."""
    result = await db.execute(
        select(Course)
        .where(Course.is_active.is_(True))
        .order_by(Course.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def update_course(
    db: AsyncSession,
    course_id: uuid.UUID,
    user_id: uuid.UUID,
    user_role: UserRole,
    data: CourseUpdate,
) -> Course:
    """
    Update a course.
    - Instructors can only update their own courses
    - Admins can update any course
    """
    course = await get_course_by_id(db, course_id)

    # Ownership/permission check
    # Admins can update any course; instructors can only edit their own
    if user_role != UserRole.admin and course.instructor_id != user_id:
        raise PermissionDeniedError("You can only update your own courses")

    # Only update fields that were actually sent (not None)
    # This is what makes PATCH different from PUT
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(course, field, value)

    await db.commit()
    await db.refresh(course)
    return course
