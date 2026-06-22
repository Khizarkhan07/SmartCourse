from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from sqlalchemy import text

from api.routes.auth import router as auth_router
from api.routes.users import router as users_router
from config import settings
from core.logging import configure_logging, get_logger
from core.tracing import configure_tracing
from database import engine

configure_logging()
configure_tracing()
SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)

logger = get_logger(__name__)

app = FastAPI(title=settings.SERVICE_NAME)


@app.get("/health", tags=["Health"])
async def health_check():
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    logger.info("health check", service=settings.SERVICE_NAME)
    return {"status": "ok", "service": settings.SERVICE_NAME}


app.include_router(auth_router)
app.include_router(users_router)

FastAPIInstrumentor.instrument_app(app)
