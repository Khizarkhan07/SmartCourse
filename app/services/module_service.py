import uuid

from app.models import Module
from app.schemas.module import ModuleCreate, ModuleUpdate
from app.core.exceptions import NotFoundError, PermissionDeniedError
from app.infrastructure.database.unit_of_work import UnitOfWork
from app.repositories.module_repository import ModuleRepository


def _modules_repo(uow: UnitOfWork) -> ModuleRepository:
    if uow.modules is None:
        raise RuntimeError("UnitOfWork is not initialized")
    return uow.modules


async def create_module(
    uow: UnitOfWork,
    data: ModuleCreate,
    instructor_id: uuid.UUID,
) -> Module:
    if uow.session is None:
        raise RuntimeError("UnitOfWork session is not initialized")

    repo = _modules_repo(uow)

    # Verify course exists
    course = await repo.get_course_by_id(data.course_id)

    if not course:
        raise NotFoundError("Course not found")

    # Ownership check — only the instructor who owns the course can add modules
    if course.instructor_id != instructor_id:
        raise PermissionDeniedError("You can only add modules to your own courses")

    new_module = Module(
        course_id=data.course_id,
        title=data.title,
        description=data.description,
        order=data.order,
    )

    uow.session.add(new_module)
    await uow.commit()
    await uow.session.refresh(new_module)

    return new_module


async def get_module_by_id(
    uow: UnitOfWork,
    module_id: uuid.UUID,
) -> Module:
    """Get a single module by ID. Raises NotFoundError if not found."""
    module = await _modules_repo(uow).get_by_id(module_id)

    if not module:
        raise NotFoundError("Module not found")

    return module


async def list_modules(
    uow: UnitOfWork,
    course_id: uuid.UUID,
) -> list[Module]:
    """List all modules for a course, ordered by the `order` field."""
    return await _modules_repo(uow).list_by_course(course_id)


async def update_module(
    uow: UnitOfWork,
    module_id: uuid.UUID,
    instructor_id: uuid.UUID,
    data: ModuleUpdate,
) -> Module:
    """
    Update a module.

    Only the owner of the course the module belongs to can update it.

    Raises:
        NotFoundError: if module not found
        PermissionDeniedError: if caller is not the course owner
    """
    if uow.session is None:
        raise RuntimeError("UnitOfWork session is not initialized")

    repo = _modules_repo(uow)
    module = await get_module_by_id(uow, module_id)

    # Ownership check via the module's parent course
    course = await repo.get_course_by_id(module.course_id)
    if course is None:
        raise NotFoundError("Course not found")

    if course.instructor_id != instructor_id:
        raise PermissionDeniedError("You can only update modules in your own courses")

    # Only update fields that were actually sent (PATCH behaviour)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(module, field, value)

    await uow.commit()
    await uow.session.refresh(module)

    return module
