import uuid
from fastapi import APIRouter, Depends, Query

from app.infrastructure.database.unit_of_work import UnitOfWork, get_uow
from app.schemas.course import CourseCreate, CourseUpdate, CourseResponse
from app.services import course_service
from app.api.dependencies import require_role
from app.models.user import User, UserRole

router = APIRouter(prefix="/courses", tags=["Courses"])


@router.post("/", response_model=CourseResponse, status_code=201)
async def create_course(
    data: CourseCreate,
    uow: UnitOfWork = Depends(get_uow),
    current_user: User = Depends(require_role(UserRole.instructor, UserRole.admin)),
):
    """
    Create a new course (starts as draft).
    Only instructors and admins can create courses.
    """
    return await course_service.create_course(uow, data, current_user.id)


@router.get("/", response_model=list[CourseResponse])
async def list_courses(
    uow: UnitOfWork = Depends(get_uow),
    limit: int = Query(default=20, ge=1, le=100, description="Number of results per page"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
):
    """Return active courses with pagination. Max 100 per page."""
    return await course_service.list_courses(uow, limit=limit, offset=offset)


@router.get("/{course_id}", response_model=CourseResponse)
async def get_course(course_id: uuid.UUID, uow: UnitOfWork = Depends(get_uow)):
    """Get a single course by ID. Public — no auth required."""
    return await course_service.get_course_by_id(uow, course_id)


@router.patch("/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: uuid.UUID,
    data: CourseUpdate,
    uow: UnitOfWork = Depends(get_uow),
    current_user: User = Depends(require_role(UserRole.instructor, UserRole.admin)),
):
    """
    Partially update a course.
    Only instructors and admins can update.
    - Instructors can only update their own courses
    - Admins can update any course
    """
    return await course_service.update_course(uow, course_id, current_user.id, current_user.role, data)
