import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, require_role
from schemas.course import CourseCreate, CourseResponse, CourseUpdate
from schemas.module import ModuleCreate, ModuleResponse
from services import course_service, module_service

router = APIRouter(prefix="/courses", tags=["Courses"])


@router.post("/", response_model=CourseResponse, status_code=201)
async def create_course(
    data: CourseCreate,
    session: AsyncSession = Depends(get_db),
    payload: dict = Depends(require_role("instructor", "admin")),
):
    return await course_service.create_course(session, data, uuid.UUID(payload["sub"]))


@router.get("/", response_model=list[CourseResponse])
async def list_courses(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    return await course_service.list_courses(session, limit=limit, offset=offset)


@router.get("/{course_id}", response_model=CourseResponse)
async def get_course(course_id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    return await course_service.get_course(session, course_id)


@router.patch("/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: uuid.UUID,
    data: CourseUpdate,
    session: AsyncSession = Depends(get_db),
    payload: dict = Depends(require_role("instructor", "admin")),
):
    return await course_service.update_course(
        session, course_id, uuid.UUID(payload["sub"]), payload["role"], data
    )


@router.get("/{course_id}/modules", response_model=list[ModuleResponse])
async def list_modules_for_course(course_id: uuid.UUID, session: AsyncSession = Depends(get_db)):
    return await module_service.list_modules(session, course_id)


@router.post("/{course_id}/modules", response_model=ModuleResponse, status_code=201)
async def create_module_for_course(
    course_id: uuid.UUID,
    data: ModuleCreate,
    session: AsyncSession = Depends(get_db),
    payload: dict = Depends(require_role("instructor", "admin")),
):
    data.course_id = course_id
    return await module_service.create_module(session, data, uuid.UUID(payload["sub"]))
