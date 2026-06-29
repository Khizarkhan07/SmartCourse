import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user_payload, require_role
from clients.course_client import CourseClient, get_course_client
from core.exceptions import PermissionDeniedError
from database import get_db
from schemas.enrollment import EnrollmentRequest, EnrollmentResponse, EnrollmentProgressResponse
from services import enrollment_service

router = APIRouter(prefix="/enrollments", tags=["Enrollments"])


@router.post("/", response_model=EnrollmentResponse, status_code=status.HTTP_201_CREATED)
async def enroll_in_course(
    data: EnrollmentRequest,
    payload: dict = Depends(require_role("student")),
    db: AsyncSession = Depends(get_db),
    course_client: CourseClient = Depends(get_course_client),
):
    """
    Enroll the authenticated student in a course.
    Validates the course is published via cross-service call to course-service.
    Temporal workflow (email + Kafka event) is added in Chunk 24.
    """
    student_id = uuid.UUID(payload["sub"])
    return await enrollment_service.create_enrollment(
        db, course_client, student_id=student_id, course_id=data.course_id
    )


@router.get("/", response_model=list[EnrollmentResponse])
async def list_my_enrollments(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    """List all enrollments for the authenticated user."""
    student_id = uuid.UUID(payload["sub"])
    return await enrollment_service.list_student_enrollments(
        db, student_id=student_id, limit=limit, offset=offset
    )


@router.get("/{enrollment_id}", response_model=EnrollmentResponse)
async def get_enrollment(
    enrollment_id: uuid.UUID,
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
):
    """Get a single enrollment. Students may only view their own."""
    enrollment = await enrollment_service.get_enrollment(db, enrollment_id)
    if payload.get("role") == "student" and enrollment.student_id != uuid.UUID(payload["sub"]):
        raise PermissionDeniedError("You can only view your own enrollments")
    return enrollment


@router.get("/{enrollment_id}/progress", response_model=EnrollmentProgressResponse)
async def get_enrollment_progress(
    enrollment_id: uuid.UUID,
    payload: dict = Depends(get_current_user_payload),
    db: AsyncSession = Depends(get_db),
    course_client: CourseClient = Depends(get_course_client),
):
    """Return lesson-based progress for an enrollment."""
    student_id = uuid.UUID(payload["sub"])
    role = payload.get("role", "student")
    return await enrollment_service.get_enrollment_progress(
        db, course_client, enrollment_id, student_id, role
    )


@router.post("/lessons/{lesson_id}/complete", response_model=EnrollmentResponse)
async def mark_lesson_complete(
    lesson_id: uuid.UUID,
    payload: dict = Depends(require_role("student")),
    db: AsyncSession = Depends(get_db),
    course_client: CourseClient = Depends(get_course_client),
):
    """
    Mark a lesson as complete for the authenticated student.
    Resolves the owning course via cross-service call to course-service — no
    request body needed.
    """
    student_id = uuid.UUID(payload["sub"])
    return await enrollment_service.mark_lesson_complete(
        db, course_client, lesson_id=lesson_id, student_id=student_id
    )
