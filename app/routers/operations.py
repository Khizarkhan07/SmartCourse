from fastapi import APIRouter, Depends, HTTPException, status
from temporalio.client import WorkflowFailureError
from temporalio.service import RPCError

from app.dependencies import get_current_user
from app.models.user import User
from app.schemas.operation import OperationStatusResponse
from app.temporal_client import get_temporal_client

router = APIRouter(prefix="/operations", tags=["Operations"])


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
        response.result = await handle.result()
    elif status_name in {"failed", "canceled", "terminated", "timed_out"}:
        try:
            await handle.result()
        except WorkflowFailureError as e:
            inner = getattr(e.cause, "cause", e.cause)
            response.error = getattr(inner, "message", str(inner))
        except Exception as e:  # fallback for unexpected failure wrappers
            response.error = str(e)

    return response
