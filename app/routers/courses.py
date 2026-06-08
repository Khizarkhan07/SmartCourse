import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.course import CourseCreate, CourseUpdate, CourseResponse
from app.services import course_service
from app.auth import require_role
from app.models.user import User, UserRole

router = APIRouter(prefix="/courses", tags=["Courses"])


@router.post("/", response_model=CourseResponse, status_code=201)
async def create_course(
    data: CourseCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.instructor, UserRole.admin)),
):
    """
    Create a new course (starts as draft).
    Only instructors and admins can create courses.
    """
    return await course_service.create_course(db, data, current_user.id)


@router.get("/", response_model=list[CourseResponse])
async def list_courses(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100, description="Number of results per page"),
    offset: int = Query(default=0, ge=0, description="Number of results to skip"),
):
    """Return active courses with pagination. Max 100 per page."""
    return await course_service.list_courses(db, limit=limit, offset=offset)


@router.get("/{course_id}", response_model=CourseResponse)
async def get_course(course_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get a single course by ID. Public — no auth required."""
    return await course_service.get_course_by_id(db, course_id)


@router.patch("/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: uuid.UUID,
    data: CourseUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.instructor, UserRole.admin)),
):
    """
    Partially update a course.
    Only instructors and admins can update.
    - Instructors can only update their own courses
    - Admins can update any course
    """
    return await course_service.update_course(db, course_id, current_user.id, current_user.role, data)
