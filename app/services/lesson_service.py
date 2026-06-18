import uuid

from app.models import Lesson
from app.schemas.lesson import LessonCreate, LessonUpdate
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.infrastructure.database.unit_of_work import UnitOfWork
from app.repositories.lesson_repository import LessonRepository


def _lessons_repo(uow: UnitOfWork) -> LessonRepository:
    if uow.lessons is None:
        raise RuntimeError("UnitOfWork is not initialized")
    return uow.lessons


async def create_lesson(
    uow: UnitOfWork,
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
    if uow.session is None:
        raise RuntimeError("UnitOfWork session is not initialized")

    repo = _lessons_repo(uow)

    # Verify module exists
    module = await repo.get_module_by_id(data.module_id)

    if not module:
        raise NotFoundError("Module not found")

    # Ownership check via module's parent course
    course = await repo.get_course_by_id(module.course_id)
    if course is None:
        raise NotFoundError("Course not found")

    if course.instructor_id != instructor_id:
        raise PermissionDeniedError("You can only add lessons to your own courses")

    new_lesson = Lesson(
        module_id=data.module_id,
        title=data.title,
        content=data.content,
        order=data.order,
    )

    uow.session.add(new_lesson)
    await uow.commit()
    await uow.session.refresh(new_lesson)

    return new_lesson


async def get_lesson_by_id(
    uow: UnitOfWork,
    lesson_id: uuid.UUID,
) -> Lesson:
    """Get a single lesson by ID. Raises NotFoundError if not found."""
    lesson = await _lessons_repo(uow).get_by_id(lesson_id)

    if not lesson:
        raise NotFoundError("Lesson not found")

    return lesson


async def list_lessons(
    uow: UnitOfWork,
    module_id: uuid.UUID,
) -> list[Lesson]:
    """List all lessons for a module, ordered by the `order` field."""
    return await _lessons_repo(uow).list_by_module(module_id)


async def update_lesson(
    uow: UnitOfWork,
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
    if uow.session is None:
        raise RuntimeError("UnitOfWork session is not initialized")

    repo = _lessons_repo(uow)
    lesson = await get_lesson_by_id(uow, lesson_id)

    # Ownership check via lesson's parent module → parent course
    module = await repo.get_module_by_id(lesson.module_id)
    if module is None:
        raise NotFoundError("Module not found")

    course = await repo.get_course_by_id(module.course_id)
    if course is None:
        raise NotFoundError("Course not found")

    if course.instructor_id != instructor_id:
        raise PermissionDeniedError("You can only update lessons in your own courses")

    # Only update fields that were actually sent (PATCH behaviour)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(lesson, field, value)

    await uow.commit()
    await uow.session.refresh(lesson)

    return lesson
