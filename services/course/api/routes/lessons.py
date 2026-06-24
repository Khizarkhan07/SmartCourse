import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, require_role
from schemas.lesson import LessonResponse, LessonUpdate
from services import lesson_service

router = APIRouter(prefix="/lessons", tags=["Lessons"])


@router.get("/{lesson_id}", response_model=LessonResponse)
async def get_lesson(lesson_id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    return await lesson_service.get_lesson(session, lesson_id)


@router.patch("/{lesson_id}", response_model=LessonResponse)
async def update_lesson(
    lesson_id: uuid.UUID,
    data: LessonUpdate,
    session: AsyncSession = Depends(get_db),
    payload: dict = Depends(require_role("instructor", "admin")),
):
    return await lesson_service.update_lesson(session, lesson_id, uuid.UUID(payload["sub"]), data)
