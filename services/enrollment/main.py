from fastapi import FastAPI
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from sqlalchemy import text

from config import settings
from core.exceptions import NotFoundError, PermissionDeniedError, ValidationError, ConflictError
from core.logging import configure_logging, get_logger
from core.tracing import configure_tracing
from database import engine, sync_engine

configure_logging()
configure_tracing()
SQLAlchemyInstrumentor().instrument(engine=sync_engine)

logger = get_logger(__name__)

app = FastAPI(title=settings.SERVICE_NAME)


@app.exception_handler(NotFoundError)
async def not_found_handler(request, exc):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(PermissionDeniedError)
async def permission_denied_handler(request, exc):
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.exception_handler(ValidationError)
async def validation_error_handler(request, exc):
    return JSONResponse(status_code=422, content={"detail": str(exc)})


@app.exception_handler(ConflictError)
async def conflict_handler(request, exc):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


@app.get("/health", tags=["Health"])
async def health_check():
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("health check", service=settings.SERVICE_NAME)
    return {"status": "ok", "service": settings.SERVICE_NAME}


FastAPIInstrumentor.instrument_app(app)
