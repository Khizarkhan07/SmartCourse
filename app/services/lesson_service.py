import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Lesson, Module, Course
from app.schemas.lesson import LessonCreate, LessonUpdate
from app.exceptions import NotFoundError, PermissionDeniedError


async def create_lesson(
    db: AsyncSession,
    data: LessonCreate,
    instructor_id: uuid.UUID,
) -> Lesson:
    """
    Create a new lesson inside a module.

    Ownership check goes 2 levels up: Lesson → Module → Course.
    Only the course owner can add lessons.

    Raises:
        NotFoundError: if module not found
        PermissionDeniedError: if caller is not the course owner
    """
    # Verify module exists
    module_result = await db.execute(select(Module).where(Module.id == data.module_id))
    module = module_result.scalar_one_or_none()

    if not module:
        raise NotFoundError("Module not found")

    # Ownership check via module's parent course
    course_result = await db.execute(select(Course).where(Course.id == module.course_id))
    course = course_result.scalar_one()

    if course.instructor_id != instructor_id:
        raise PermissionDeniedError("You can only add lessons to your own courses")

    new_lesson = Lesson(
        module_id=data.module_id,
        title=data.title,
        content=data.content,
        order=data.order,
    )

    db.add(new_lesson)
    await db.commit()
    await db.refresh(new_lesson)

    return new_lesson


async def get_lesson_by_id(
    db: AsyncSession,
    lesson_id: uuid.UUID,
) -> Lesson:
    """Get a single lesson by ID. Raises NotFoundError if not found."""
    result = await db.execute(select(Lesson).where(Lesson.id == lesson_id))
    lesson = result.scalar_one_or_none()

    if not lesson:
        raise NotFoundError("Lesson not found")

    return lesson


async def list_lessons(
    db: AsyncSession,
    module_id: uuid.UUID,
) -> list[Lesson]:
    """List all lessons for a module, ordered by the `order` field."""
    result = await db.execute(
        select(Lesson)
        .where(Lesson.module_id == module_id)
        .order_by(Lesson.order)
    )
    return list(result.scalars().all())


async def update_lesson(
    db: AsyncSession,
    lesson_id: uuid.UUID,
    instructor_id: uuid.UUID,
    data: LessonUpdate,
) -> Lesson:
    """
    Update a lesson.

    Ownership check goes 2 levels up: Lesson → Module → Course.

    Raises:
        NotFoundError: if lesson not found
        PermissionDeniedError: if caller is not the course owner
    """
    lesson = await get_lesson_by_id(db, lesson_id)

    # Ownership check via lesson's parent module → parent course
    module_result = await db.execute(select(Module).where(Module.id == lesson.module_id))
    module = module_result.scalar_one()

    course_result = await db.execute(select(Course).where(Course.id == module.course_id))
    course = course_result.scalar_one()

    if course.instructor_id != instructor_id:
        raise PermissionDeniedError("You can only update lessons in your own courses")

    # Only update fields that were actually sent (PATCH behaviour)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(lesson, field, value)

    await db.commit()
    await db.refresh(lesson)

    return lesson
