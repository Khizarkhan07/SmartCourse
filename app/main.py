from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi import status
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.routers import auth, users, courses, enrollments, modules, lessons, publishing, operations, analytics
from app.config import settings
from app.limiter import limiter
from app.exceptions import (
    NotFoundError,
    ConflictError,
    ValidationError,
    PermissionDeniedError,
    InvalidStateError,
)

app = FastAPI(
    title="SmartCourse API",
    description="Intelligent Course Delivery Platform — Backend",
    version="1.0.0",
)

# Attach shared limiter to app state so routes can access it via Depends
app.state.limiter = limiter

# Returns 429 Too Many Requests when a limit is exceeded
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# CORS — controls which frontend origins can call this API
allowed_origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(auth.router)
app.include_router(users.router)
app.include_router(courses.router)
app.include_router(enrollments.router)
app.include_router(modules.router)
app.include_router(lessons.router)
app.include_router(publishing.router)
app.include_router(operations.router)
app.include_router(analytics.router)


@app.get("/health", tags=["Health"])
async def health_check():
    """Simple health check endpoint."""
    return {"status": "ok"}


# Global exception handlers — map domain exceptions to HTTP responses
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
