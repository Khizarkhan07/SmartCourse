from core.logging import configure_logging
from core.tracing import configure_tracing
from database import sync_engine
from events.dlq_reprocessor import UserProfileDLQReprocessor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

configure_logging()
configure_tracing()
SQLAlchemyInstrumentor().instrument(engine=sync_engine)

if __name__ == "__main__":
    UserProfileDLQReprocessor().run()
