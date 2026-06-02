import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.module import ModuleCreate, ModuleUpdate, ModuleResponse
from app.services import module_service
from app.auth import get_current_user, require_role
from app.models.user import User, UserRole

router = APIRouter(tags=["Modules"])


@router.post("/courses/{course_id}/modules", response_model=ModuleResponse, status_code=201)
async def create_module(
    course_id: uuid.UUID,
    data: ModuleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.instructor, UserRole.admin)),
):
    """
    Add a module to a course.
    Only the course owner (instructor) can add modules.
    """
    # Force course_id from URL path — client cannot target a different course in the body
    data.course_id = course_id
    return await module_service.create_module(db, data, current_user.id)


@router.get("/courses/{course_id}/modules", response_model=list[ModuleResponse])
async def list_modules(
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """List all modules for a course, ordered by sequence. Public — no auth required."""
    return await module_service.list_modules(db, course_id)


@router.get("/modules/{module_id}", response_model=ModuleResponse)
async def get_module(
    module_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single module by ID. Public — no auth required."""
    return await module_service.get_module_by_id(db, module_id)


@router.patch("/modules/{module_id}", response_model=ModuleResponse)
async def update_module(
    module_id: uuid.UUID,
    data: ModuleUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.instructor, UserRole.admin)),
):
    """
    Partially update a module.
    Only the course owner can update their modules.
    """
    return await module_service.update_module(db, module_id, current_user.id, data)
