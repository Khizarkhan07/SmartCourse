from core.tracing import configure_tracing
from database import engine
from events.enrollment_completed_consumer import EnrollmentCompletedConsumer
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

if __name__ == "__main__":
    configure_tracing()
    SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
    EnrollmentCompletedConsumer().run()
