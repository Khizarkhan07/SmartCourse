import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from temporalio.client import WorkflowFailureError
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.common import WorkflowIDReusePolicy
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user_payload, require_role
from clients.course_client import CourseClient, get_course_client
from config import settings
from core.exceptions import PermissionDeniedError
from database import get_db
from schemas.enrollment import EnrollmentRequest, EnrollmentResponse, EnrollmentProgressResponse
from schemas.operation import OperationAcceptedResponse, OperationStatusResponse
from services import enrollment_service
from temporal import get_temporal_client
from workflows.enrollment_workflow import EnrollmentWorkflow, EnrollmentWorkflowInput

router = APIRouter(prefix="/enrollments", tags=["Enrollments"])


@router.post("/", response_model=OperationAcceptedResponse, status_code=status.HTTP_202_ACCEPTED)
async def enroll_in_course(
    data: EnrollmentRequest,
    payload: dict = Depends(require_role("student")),
):
    """
    Start the enrollment saga via Temporal.
    Steps: validate course → create enrollment → send email → emit Kafka event.
    If any post-commit step fails, a compensation activity deletes the enrollment.
    Returns immediately with an operation_id for polling.
    """
    student_id = payload["sub"]
    workflow_id = f"enroll-{student_id}-{data.course_id}"
    client = await get_temporal_client()

    try:
        await client.start_workflow(
            EnrollmentWorkflow.run,
            EnrollmentWorkflowInput(
                student_id=student_id,
                course_id=str(data.course_id),
                student_email=payload.get("email", ""),
            ),
            id=workflow_id,
            task_queue=settings.ENROLLMENT_TASK_QUEUE,
            id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
        )
    except WorkflowAlreadyStartedError:
        pass

    return OperationAcceptedResponse(
        operation_id=workflow_id,
        status="accepted",
        status_url=f"/enrollments/operations/{workflow_id}",
    )


@router.get("/operations/{workflow_id}", response_model=OperationStatusResponse)
async def get_enrollment_operation(workflow_id: str):
    """Poll the status of an enrollment workflow."""
    client = await get_temporal_client()
    handle = client.get_workflow_handle(workflow_id)
    try:
        desc = await handle.describe()
    except Exception:
        raise HTTPException(status_code=404, detail="Operation not found")

    wf_status = str(desc.status.name).lower() if desc.status else "unknown"
    result = None
    error = None

    if wf_status == "completed":
        try:
            result = await handle.result()
        except WorkflowFailureError as exc:
            error = str(exc)
            wf_status = "failed"

    return OperationStatusResponse(
        operation_id=workflow_id,
        run_id=desc.run_id,
        status=wf_status,
        result=result,
        error=error,
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
    Mark a lesson complete. Resolves the owning course via course-service,
    updates progress, and triggers CourseCompletionWorkflow if progress hits 100%.
    """
    student_id = uuid.UUID(payload["sub"])
    return await enrollment_service.mark_lesson_complete(
        db, course_client, lesson_id=lesson_id, student_id=student_id
    )
