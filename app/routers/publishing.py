import uuid
from fastapi import APIRouter, Depends, status
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from app.auth import require_role
from app.models.user import User, UserRole
from app.schemas.operation import OperationAcceptedResponse
from app.temporal_client import COURSE_TASK_QUEUE, get_temporal_client
from app.workflows.publish_course_workflow import (
    ArchiveCourseWorkflow,
    ArchiveCourseWorkflowInput,
    PublishCourseWorkflow,
    PublishCourseWorkflowInput,
)

router = APIRouter(prefix="/courses", tags=["Publishing"])


@router.post(
    "/{course_id}/publish",
    response_model=OperationAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def publish_course(
    course_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.instructor, UserRole.admin)),
):
    """
    Publish a course (draft → published).

    Validates:
    - Course has a description
    - Course has at least one lesson
    - Caller is the course owner
    """
    workflow_id = f"publish-{course_id}"
    client = await get_temporal_client()

    try:
        await client.start_workflow(
            PublishCourseWorkflow.run,
            PublishCourseWorkflowInput(
                course_id=str(course_id),
                instructor_id=str(current_user.id),
            ),
            id=workflow_id,
            task_queue=COURSE_TASK_QUEUE,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        )
    except WorkflowAlreadyStartedError:
        pass

    return OperationAcceptedResponse(
        operation_id=workflow_id,
        status="accepted",
        status_url=f"/operations/{workflow_id}",
    )


@router.patch(
    "/{course_id}/archive",
    response_model=OperationAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def archive_course(
    course_id: uuid.UUID,
    current_user: User = Depends(require_role(UserRole.instructor, UserRole.admin)),
):
    """
    Archive a course (published → archived).

    Archived courses are no longer visible to new students.
    Existing enrollments are unaffected.
    """
    workflow_id = f"archive-{course_id}"
    client = await get_temporal_client()

    try:
        await client.start_workflow(
            ArchiveCourseWorkflow.run,
            ArchiveCourseWorkflowInput(
                course_id=str(course_id),
                instructor_id=str(current_user.id),
            ),
            id=workflow_id,
            task_queue=COURSE_TASK_QUEUE,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        )
    except WorkflowAlreadyStartedError:
        pass

    return OperationAcceptedResponse(
        operation_id=workflow_id,
        status="accepted",
        status_url=f"/operations/{workflow_id}",
    )
