from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.routers import auth, users, courses, enrollments, modules, lessons, publishing, operations, analytics
from app.config import settings

# Limiter reads the client's IP address to track request counts per IP
# In production this can be backed by Redis for distributed rate limiting
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="SmartCourse API",
    description="Intelligent Course Delivery Platform — Backend",
    version="1.0.0",
)

# Attach limiter to app state so routes can access it via Depends
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
