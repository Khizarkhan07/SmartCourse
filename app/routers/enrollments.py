import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.enrollment import EnrollmentCreate, EnrollmentResponse
from app.services import enrollment_service
from app.auth import get_current_user, require_role
from app.models.user import User, UserRole

router = APIRouter(prefix="/enrollments", tags=["Enrollments"])


@router.post("/", response_model=EnrollmentResponse, status_code=201)
async def enroll_in_course(
    data: EnrollmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(UserRole.student)),
):
    """
    Enroll the current student in a course.
    Idempotent: calling this twice returns the same enrollment.
    Only students can enroll.
    """
    # Force student_id to be the authenticated user — client cannot enroll on behalf of others
    data.student_id = current_user.id
    return await enrollment_service.create_enrollment(db, data)


@router.get("/", response_model=list[EnrollmentResponse])
async def list_my_enrollments(
    db: AsyncSession = Depends(get_db),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
):
    """List all courses the current user is enrolled in."""
    return await enrollment_service.list_student_enrollments(
        db, student_id=current_user.id, limit=limit, offset=offset
    )


@router.get("/{enrollment_id}", response_model=EnrollmentResponse)
async def get_enrollment(
    enrollment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get a single enrollment by ID. Only the enrolled student can view it."""
    enrollment = await enrollment_service.get_enrollment(db, enrollment_id)

    # Guard: students can only see their own enrollments
    if current_user.role == UserRole.student and enrollment.student_id != current_user.id:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own enrollments",
        )

    return enrollment
