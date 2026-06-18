from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from config import settings
from core.logging import configure_logging, get_logger
from core.tracing import configure_tracing

configure_logging()
configure_tracing()

logger = get_logger(__name__)

app = FastAPI(title=settings.SERVICE_NAME)


@app.get("/health", tags=["Health"])
async def health_check():
    logger.info("health check", service=settings.SERVICE_NAME)
    return {"status": "ok", "service": settings.SERVICE_NAME}


FastAPIInstrumentor.instrument_app(app)
