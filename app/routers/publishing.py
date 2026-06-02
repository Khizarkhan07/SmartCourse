import uuid
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.course import CourseResponse
from app.services import course_publishing_service
from app.auth import require_role
from app.models.user import User, UserRole

router = APIRouter(prefix="/courses", tags=["Publishing"])


@router.post("/{course_id}/publish", response_model=CourseResponse)
async def publish_course(
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.instructor, UserRole.admin)),
):
    """
    Publish a course (draft → published).

    Validates:
    - Course has a description
    - Course has at least one lesson
    - Caller is the course owner
    """
    return await course_publishing_service.publish_course(db, course_id, current_user.id)


@router.patch("/{course_id}/archive", response_model=CourseResponse)
async def archive_course(
    course_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.instructor, UserRole.admin)),
):
    """
    Archive a course (published → archived).

    Archived courses are no longer visible to new students.
    Existing enrollments are unaffected.
    """
    return await course_publishing_service.archive_course(db, course_id, current_user.id)
