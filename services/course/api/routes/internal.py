import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db
from repositories.lesson_repository import LessonRepository
from repositories.module_repository import ModuleRepository
from schemas.internal import LessonCountResponse, LessonInternalResponse

router = APIRouter(prefix="/internal", tags=["Internal"])


@router.get("/lessons/{lesson_id}", response_model=LessonInternalResponse)
async def get_lesson_internal(
    lesson_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    """Service-to-service: resolve course_id for a given lesson_id."""
    lesson = await LessonRepository(session).get_by_id(lesson_id)
    if not lesson:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found")
    module = await ModuleRepository(session).get_by_id(lesson.module_id)
    if not module:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Module not found")
    return LessonInternalResponse(
        id=lesson.id, module_id=lesson.module_id, course_id=module.course_id
    )


@router.get("/courses/{course_id}/lesson-count", response_model=LessonCountResponse)
async def get_lesson_count(
    course_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
):
    """Service-to-service: total lesson count for a course (used by enrollment-service for progress)."""
    total = await LessonRepository(session).count_by_course(course_id)
    return LessonCountResponse(course_id=course_id, total_lessons=total)
