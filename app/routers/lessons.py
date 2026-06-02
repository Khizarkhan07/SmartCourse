import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.lesson import LessonCreate, LessonUpdate, LessonResponse
from app.services import lesson_service
from app.auth import require_role
from app.models.user import User, UserRole

router = APIRouter(tags=["Lessons"])


@router.post("/modules/{module_id}/lessons", response_model=LessonResponse, status_code=201)
async def create_lesson(
    module_id: uuid.UUID,
    data: LessonCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.instructor, UserRole.admin)),
):
    """
    Add a lesson to a module.
    Only the course owner (instructor) can add lessons.
    """
    # Force module_id from URL path — client cannot target a different module in the body
    data.module_id = module_id
    return await lesson_service.create_lesson(db, data, current_user.id)


@router.get("/modules/{module_id}/lessons", response_model=list[LessonResponse])
async def list_lessons(
    module_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """List all lessons in a module, ordered by sequence. Public — no auth required."""
    return await lesson_service.list_lessons(db, module_id)


@router.get("/lessons/{lesson_id}", response_model=LessonResponse)
async def get_lesson(
    lesson_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single lesson by ID. Public — no auth required."""
    return await lesson_service.get_lesson_by_id(db, lesson_id)


@router.patch("/lessons/{lesson_id}", response_model=LessonResponse)
async def update_lesson(
    lesson_id: uuid.UUID,
    data: LessonUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.instructor, UserRole.admin)),
):
    """
    Partially update a lesson.
    Only the course owner can update their lessons.
    """
    return await lesson_service.update_lesson(db, lesson_id, current_user.id, data)
