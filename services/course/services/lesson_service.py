import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import NotFoundError, PermissionDeniedError
from models.lesson import Lesson
from repositories.course_repository import CourseRepository
from repositories.lesson_repository import LessonRepository
from repositories.module_repository import ModuleRepository
from schemas.lesson import LessonCreate, LessonUpdate


async def create_lesson(session: AsyncSession, data: LessonCreate, instructor_id: uuid.UUID) -> Lesson:
    module = await ModuleRepository(session).get_by_id(data.module_id)
    if not module:
        raise NotFoundError("Module not found")
    course = await CourseRepository(session).get_by_id(module.course_id)
    if not course:
        raise NotFoundError("Course not found")
    if course.instructor_id != instructor_id:
        raise PermissionDeniedError("You can only add lessons to your own courses")
    lesson = Lesson(module_id=data.module_id, title=data.title, content=data.content, order=data.order)
    session.add(lesson)
    await session.commit()
    await session.refresh(lesson)
    return lesson


async def get_lesson(session: AsyncSession, lesson_id: uuid.UUID) -> Lesson:
    lesson = await LessonRepository(session).get_by_id(lesson_id)
    if not lesson:
        raise NotFoundError("Lesson not found")
    return lesson


async def list_lessons(session: AsyncSession, module_id: uuid.UUID) -> list[Lesson]:
    return await LessonRepository(session).list_by_module(module_id)


async def update_lesson(
    session: AsyncSession, lesson_id: uuid.UUID, instructor_id: uuid.UUID, data: LessonUpdate
) -> Lesson:
    lesson = await get_lesson(session, lesson_id)
    module = await ModuleRepository(session).get_by_id(lesson.module_id)
    if not module:
        raise NotFoundError("Module not found")
    course = await CourseRepository(session).get_by_id(module.course_id)
    if not course:
        raise NotFoundError("Course not found")
    if course.instructor_id != instructor_id:
        raise PermissionDeniedError("You can only update lessons in your own courses")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(lesson, field, value)
    await session.commit()
    await session.refresh(lesson)
    return lesson
