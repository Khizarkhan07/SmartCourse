import uuid

from app.models.course import Course, CourseStatus
from app.models.user import UserRole
from app.schemas.course import CourseCreate, CourseUpdate
from app.core.exceptions import NotFoundError, PermissionDeniedError, ValidationError
from app.infrastructure.database.unit_of_work import UnitOfWork
from app.repositories.course_repository import CourseRepository


def _courses_repo(uow: UnitOfWork) -> CourseRepository:
    if uow.courses is None:
        raise RuntimeError("UnitOfWork is not initialized")
    return uow.courses


async def create_course(uow: UnitOfWork, data: CourseCreate, instructor_id: uuid.UUID) -> Course:
    """
    Create a new course.
    - Verifies the instructor exists and has the instructor role
    - Course starts as 'draft' — publishing is a separate workflow
    
    Raises:
        NotFoundError: if instructor not found
        ValidationError: if instructor does not have instructor role
    """
    # Verify the instructor exists and is actually an instructor
    instructor = await _courses_repo(uow).get_instructor_by_id(instructor_id)

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

    if uow.session is None:
        raise RuntimeError("UnitOfWork session is not initialized")

    uow.session.add(new_course)
    await uow.commit()
    await uow.session.refresh(new_course)
    return new_course


async def get_course_by_id(uow: UnitOfWork, course_id: uuid.UUID) -> Course:
    """Fetch a single course by ID. Raises NotFoundError if not found."""
    course = await _courses_repo(uow).get_course_by_id(course_id)

    if not course:
        raise NotFoundError("Course not found")
    return course


async def list_courses(uow: UnitOfWork, limit: int = 20, offset: int = 0) -> list[Course]:
    """Return active courses with pagination. Default page size is 20. Ordered by creation date (newest first)."""
    return await _courses_repo(uow).list_active_courses(limit=limit, offset=offset)


async def update_course(
    uow: UnitOfWork,
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
    course = await get_course_by_id(uow, course_id)

    # Ownership/permission check
    # Admins can update any course; instructors can only edit their own
    if user_role != UserRole.admin and course.instructor_id != user_id:
        raise PermissionDeniedError("You can only update your own courses")

    # Only update fields that were actually sent (not None)
    # This is what makes PATCH different from PUT
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(course, field, value)

    if uow.session is None:
        raise RuntimeError("UnitOfWork session is not initialized")

    await uow.commit()
    await uow.session.refresh(course)
    return course
