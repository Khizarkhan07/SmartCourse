import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from core.exceptions import NotFoundError, PermissionDeniedError
from models.module import Module
from repositories.course_repository import CourseRepository
from repositories.module_repository import ModuleRepository
from schemas.module import ModuleCreate, ModuleUpdate


async def create_module(session: AsyncSession, data: ModuleCreate, instructor_id: uuid.UUID) -> Module:
    course = await CourseRepository(session).get_by_id(data.course_id)
    if not course:
        raise NotFoundError("Course not found")
    if course.instructor_id != instructor_id:
        raise PermissionDeniedError("You can only add modules to your own courses")
    module = Module(course_id=data.course_id, title=data.title, description=data.description, order=data.order)
    session.add(module)
    await session.commit()
    await session.refresh(module)
    return module


async def get_module(session: AsyncSession, module_id: uuid.UUID) -> Module:
    module = await ModuleRepository(session).get_by_id(module_id)
    if not module:
        raise NotFoundError("Module not found")
    return module


async def list_modules(session: AsyncSession, course_id: uuid.UUID) -> list[Module]:
    return await ModuleRepository(session).list_by_course(course_id)


async def update_module(
    session: AsyncSession, module_id: uuid.UUID, instructor_id: uuid.UUID, data: ModuleUpdate
) -> Module:
    module = await get_module(session, module_id)
    course = await CourseRepository(session).get_by_id(module.course_id)
    if not course:
        raise NotFoundError("Course not found")
    if course.instructor_id != instructor_id:
        raise PermissionDeniedError("You can only update modules in your own courses")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(module, field, value)
    await session.commit()
    await session.refresh(module)
    return module
