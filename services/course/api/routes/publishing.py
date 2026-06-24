import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from temporalio.client import Client
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError
from temporalio.service import RPCError

from api.dependencies import require_role
from config import settings
from core.logging import get_logger
from schemas.operation import OperationAcceptedResponse, OperationStatusResponse
from workflows.publish_course_workflow import (
    ArchiveCourseWorkflow,
    ArchiveCourseWorkflowInput,
    PublishCourseWorkflow,
    PublishCourseWorkflowInput,
)

router = APIRouter(prefix="/courses", tags=["Publishing"])

logger = get_logger(__name__)

_client: Client | None = None


async def _get_client() -> Client:
    global _client
    if _client is None:
        _client = await Client.connect(settings.TEMPORAL_HOST)
    return _client


@router.post(
    "/{course_id}/publish",
    response_model=OperationAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def publish_course(
    course_id: uuid.UUID,
    payload: dict = Depends(require_role("instructor", "admin")),
):
    workflow_id = f"publish-{course_id}"
    client = await _get_client()

    try:
        await client.start_workflow(
            PublishCourseWorkflow.run,
            PublishCourseWorkflowInput(
                course_id=str(course_id),
                instructor_id=payload["sub"],
            ),
            id=workflow_id,
            task_queue=settings.COURSE_TASK_QUEUE,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        )
    except WorkflowAlreadyStartedError:
        pass

    return OperationAcceptedResponse(
        operation_id=workflow_id,
        status="accepted",
        status_url=f"/courses/{course_id}/publish/status",
    )


@router.patch(
    "/{course_id}/archive",
    response_model=OperationAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def archive_course(
    course_id: uuid.UUID,
    payload: dict = Depends(require_role("instructor", "admin")),
):
    workflow_id = f"archive-{course_id}"
    client = await _get_client()

    try:
        await client.start_workflow(
            ArchiveCourseWorkflow.run,
            ArchiveCourseWorkflowInput(
                course_id=str(course_id),
                instructor_id=payload["sub"],
            ),
            id=workflow_id,
            task_queue=settings.COURSE_TASK_QUEUE,
            id_reuse_policy=WorkflowIDReusePolicy.REJECT_DUPLICATE,
        )
    except WorkflowAlreadyStartedError:
        pass

    return OperationAcceptedResponse(
        operation_id=workflow_id,
        status="accepted",
        status_url=f"/courses/{course_id}/archive/status",
    )


@router.get(
    "/{course_id}/publish/status",
    response_model=OperationStatusResponse,
)
async def get_publish_status(course_id: uuid.UUID):
    return await _get_workflow_status(f"publish-{course_id}")


@router.get(
    "/{course_id}/archive/status",
    response_model=OperationStatusResponse,
)
async def get_archive_status(course_id: uuid.UUID):
    return await _get_workflow_status(f"archive-{course_id}")


async def _get_workflow_status(workflow_id: str) -> OperationStatusResponse:
    from temporalio.client import WorkflowFailureError

    client = await _get_client()
    handle = client.get_workflow_handle(workflow_id)

    try:
        desc = await handle.describe()
    except RPCError as exc:
        if "not_found" in str(exc).lower():
            raise HTTPException(status_code=404, detail=f"Operation '{workflow_id}' not found")
        raise

    status_name = desc.status.name.lower()
    response = OperationStatusResponse(
        operation_id=workflow_id,
        run_id=desc.run_id,
        status=status_name,
    )

    if status_name == "completed":
        response.result = await handle.result()
    elif status_name in {"failed", "canceled", "terminated", "timed_out"}:
        try:
            await handle.result()
        except WorkflowFailureError as exc:
            inner = getattr(exc.cause, "cause", exc.cause)
            response.error = getattr(inner, "message", str(inner))
        except Exception as exc:
            response.error = str(exc)

    return response
