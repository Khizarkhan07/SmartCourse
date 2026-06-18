from fastapi import APIRouter, Depends, HTTPException, status
from temporalio.client import WorkflowFailureError
from temporalio.service import RPCError

from app.api.dependencies import get_current_user
from app.core.metrics import workflow_duration_seconds
from app.models.user import User
from app.schemas.operation import OperationStatusResponse
from app.infrastructure.temporal import get_temporal_client

router = APIRouter(prefix="/operations", tags=["Operations"])

# Maps operation_id prefix → workflow label used in the histogram
_WORKFLOW_PREFIXES = {
    "enroll-": "enrollment",
    "complete-": "completion",
    "publish-": "publish",
    "archive-": "archive",
}

# Dedup set — once a terminal workflow's duration is recorded we never record it again,
# even if the client polls the same operation_id multiple times afterwards
_recorded_workflows: set[str] = set()


def _record_duration(operation_id: str, desc) -> None:
    if operation_id in _recorded_workflows:
        return

    workflow_type = next(
        (label for prefix, label in _WORKFLOW_PREFIXES.items() if operation_id.startswith(prefix)),
        None,
    )
    if workflow_type is None:
        return

    if desc.execution_start_time and desc.close_time:
        duration = (desc.close_time - desc.execution_start_time).total_seconds()
        workflow_duration_seconds.labels(workflow=workflow_type).observe(duration)
        _recorded_workflows.add(operation_id)


@router.get("/{operation_id}", response_model=OperationStatusResponse)
async def get_operation_status(
    operation_id: str,
    current_user: User = Depends(get_current_user),
):
    # current_user is intentionally required so operation status is not public
    # (ownership checks can be tightened later with an operation store)
    _ = current_user

    client = await get_temporal_client()
    handle = client.get_workflow_handle(operation_id)

    try:
        desc = await handle.describe()
    except RPCError as e:
        if getattr(e, "status", None) and str(e.status).lower().find("not_found") != -1:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Operation '{operation_id}' not found",
            )
        raise

    status_name = desc.status.name.lower()
    response = OperationStatusResponse(
        operation_id=operation_id,
        run_id=desc.run_id,
        status=status_name,
    )

    if status_name == "completed":
        _record_duration(operation_id, desc)
        response.result = await handle.result()
    elif status_name in {"failed", "canceled", "terminated", "timed_out"}:
        _record_duration(operation_id, desc)
        try:
            await handle.result()
        except WorkflowFailureError as e:
            inner = getattr(e.cause, "cause", e.cause)
            response.error = getattr(inner, "message", str(inner))
        except Exception as e:  # fallback for unexpected failure wrappers
            response.error = str(e)

    return response
