import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, require_role
from schemas.lesson import LessonCreate, LessonResponse
from schemas.module import ModuleResponse, ModuleUpdate
from services import lesson_service, module_service

router = APIRouter(prefix="/modules", tags=["Modules"])


@router.get("/{module_id}", response_model=ModuleResponse)
async def get_module(module_id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    return await module_service.get_module(session, module_id)


@router.patch("/{module_id}", response_model=ModuleResponse)
async def update_module(
    module_id: uuid.UUID,
    data: ModuleUpdate,
    session: AsyncSession = Depends(get_db),
    payload: dict = Depends(require_role("instructor", "admin")),
):
    return await module_service.update_module(session, module_id, uuid.UUID(payload["sub"]), data)


@router.get("/{module_id}/lessons", response_model=list[LessonResponse])
async def list_lessons_for_module(module_id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    return await lesson_service.list_lessons(session, module_id)


@router.post("/{module_id}/lessons", response_model=LessonResponse, status_code=201)
async def create_lesson_for_module(
    module_id: uuid.UUID,
    data: LessonCreate,
    session: AsyncSession = Depends(get_db),
    payload: dict = Depends(require_role("instructor", "admin")),
):
    data.module_id = module_id
    return await lesson_service.create_lesson(session, data, uuid.UUID(payload["sub"]))
