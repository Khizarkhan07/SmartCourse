from pydantic import BaseModel


class OperationAcceptedResponse(BaseModel):
    operation_id: str
    status: str = "accepted"
    status_url: str


class OperationStatusResponse(BaseModel):
    operation_id: str
    run_id: str | None = None
    status: str
    result: dict | None = None
    error: str | None = None
