from fastapi import FastAPI, status
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    ConflictError,
    InvalidStateError,
    NotFoundError,
    PermissionDeniedError,
    ValidationError,
)


def register_exception_handlers(app: FastAPI) -> None:
    """Register global HTTP mappings for domain exceptions."""

    @app.exception_handler(NotFoundError)
    async def not_found_handler(request, exc):
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"detail": str(exc)},
        )

    @app.exception_handler(ConflictError)
    async def conflict_handler(request, exc):
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content={"detail": str(exc)},
        )

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request, exc):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)},
        )

    @app.exception_handler(PermissionDeniedError)
    async def permission_denied_handler(request, exc):
        return JSONResponse(
            status_code=status.HTTP_403_FORBIDDEN,
            content={"detail": str(exc)},
        )

    @app.exception_handler(InvalidStateError)
    async def invalid_state_handler(request, exc):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)},
        )
