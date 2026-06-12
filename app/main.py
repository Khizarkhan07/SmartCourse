from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from app.api import register_exception_handlers
from app.api.v1 import api_router
from app.config import settings
from app.core.limiter import limiter

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
app.include_router(api_router)


@app.get("/health", tags=["Health"])
async def health_check():
    """Simple health check endpoint."""
    return {"status": "ok"}


@app.get("/metrics", include_in_schema=False)
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


register_exception_handlers(app)

# HTTP request instrumentation — adds latency histogram + request counter for
# every route into the default Prometheus registry, picked up by GET /metrics
Instrumentator().instrument(app)
