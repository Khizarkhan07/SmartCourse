import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError


from app.infrastructure.database.unit_of_work import UnitOfWork, get_uow
from app.schemas.enrollment import EnrollmentRequest, EnrollmentResponse, EnrollmentProgressResponse
from app.schemas.operation import OperationAcceptedResponse
from app.services import enrollment_service
from app.api.dependencies import get_current_user, require_role
from app.models.user import User, UserRole
from app.infrastructure.temporal import ENROLLMENT_TASK_QUEUE, get_temporal_client
from app.workflows.enrollment_workflow import EnrollmentWorkflow, EnrollmentWorkflowInput
from app.core.metrics import enrollments_total, workflow_failures_total

router = APIRouter(prefix="/enrollments", tags=["Enrollments"])


@router.post(
    "/",
    response_model=OperationAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def enroll_in_course(
    data: EnrollmentRequest,
    current_user: User = Depends(require_role(UserRole.student)),
):
    """
    Enroll the current student in a course via a Temporal workflow.

    The workflow runs 3 durable steps:
      1. Validate — course is published, not already enrolled
      2. Create   — write enrollment row to DB
      3. Email    — send welcome email (retried automatically on failure)

    Idempotent: same student + course = same workflow ID.

    Returns immediately with an operation ID so the client can poll
    /operations/{id} instead of waiting for the workflow to finish.
    """
    # Build a deterministic workflow ID — re-submitting the same enrollment
    # returns the existing result instead of creating a duplicate
    workflow_id = f"enroll-{current_user.id}-{data.course_id}"

    client = await get_temporal_client()

    try:
        await client.start_workflow(
            EnrollmentWorkflow.run,
            EnrollmentWorkflowInput(
                student_id=str(current_user.id),
                course_id=str(data.course_id),
                student_email=current_user.email,
            ),
            id=workflow_id,
            task_queue=ENROLLMENT_TASK_QUEUE,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        )
        enrollments_total.inc()
    except WorkflowAlreadyStartedError:
        pass
    except Exception:
        workflow_failures_total.labels(workflow="enrollment").inc()
        raise

    return OperationAcceptedResponse(
        operation_id=workflow_id,
        status="accepted",
        status_url=f"/operations/{workflow_id}",
    )


@router.get("/", response_model=list[EnrollmentResponse])
async def list_my_enrollments(
    uow: UnitOfWork = Depends(get_uow),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    current_user: User = Depends(get_current_user),
):
    """List all courses the current user is enrolled in."""
    return await enrollment_service.list_student_enrollments(
        uow, student_id=current_user.id, limit=limit, offset=offset
    )


@router.get("/{enrollment_id}", response_model=EnrollmentResponse)
async def get_enrollment(
    enrollment_id: uuid.UUID,
    uow: UnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    """Get a single enrollment by ID. Only the enrolled student can view it."""
    enrollment = await enrollment_service.get_enrollment(uow, enrollment_id)

    # Guard: students can only see their own enrollments
    if current_user.role == UserRole.student and enrollment.student_id != current_user.id:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own enrollments",
        )

    return enrollment


@router.get("/{enrollment_id}/progress", response_model=EnrollmentProgressResponse)
async def get_enrollment_progress(
    enrollment_id: uuid.UUID,
    uow: UnitOfWork = Depends(get_uow),
    current_user: User = Depends(get_current_user),
):
    """Return lesson-based progress details for an enrollment."""
    return await enrollment_service.get_enrollment_progress(uow, enrollment_id, current_user)
