import uuid
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Module, Course
from app.schemas.module import ModuleCreate, ModuleUpdate
from app.exceptions import NotFoundError, PermissionDeniedError


async def create_module(
    db: AsyncSession,
    data: ModuleCreate,
    instructor_id: uuid.UUID,
) -> Module:
    # Verify course exists
    course_result = await db.execute(select(Course).where(Course.id == data.course_id))
    course = course_result.scalar_one_or_none()

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

    db.add(new_module)
    await db.commit()
    await db.refresh(new_module)

    return new_module


async def get_module_by_id(
    db: AsyncSession,
    module_id: uuid.UUID,
) -> Module:
    """Get a single module by ID. Raises NotFoundError if not found."""
    result = await db.execute(select(Module).where(Module.id == module_id))
    module = result.scalar_one_or_none()

    if not module:
        raise NotFoundError("Module not found")

    return module


async def list_modules(
    db: AsyncSession,
    course_id: uuid.UUID,
) -> list[Module]:
    """List all modules for a course, ordered by the `order` field."""
    result = await db.execute(
        select(Module)
        .where(Module.course_id == course_id)
        .order_by(Module.order)
    )
    return list(result.scalars().all())


async def update_module(
    db: AsyncSession,
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
    module = await get_module_by_id(db, module_id)

    # Ownership check via the module's parent course
    course_result = await db.execute(select(Course).where(Course.id == module.course_id))
    course = course_result.scalar_one()

    if course.instructor_id != instructor_id:
        raise PermissionDeniedError("You can only update modules in your own courses")

    # Only update fields that were actually sent (PATCH behaviour)
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(module, field, value)

    await db.commit()
    await db.refresh(module)

    return module
