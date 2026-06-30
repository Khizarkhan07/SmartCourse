import threading

from core.logging import configure_logging, get_logger
from core.tracing import configure_tracing
from database import sync_engine
from events.dlq_reprocessor import (
    CoursePublishedDLQReprocessor,
    EnrollmentCompletedDLQReprocessor,
    EnrollmentCreatedDLQReprocessor,
)
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

configure_logging()
configure_tracing()
SQLAlchemyInstrumentor().instrument(engine=sync_engine)

logger = get_logger(__name__)


if __name__ == "__main__":
    reprocessors = [
        EnrollmentCreatedDLQReprocessor(),
        EnrollmentCompletedDLQReprocessor(),
        CoursePublishedDLQReprocessor(),
    ]

    threads = [threading.Thread(target=r.run, daemon=True) for r in reprocessors]

    for t in threads:
        t.start()

    logger.info("analytics DLQ reprocessors started", count=len(reprocessors))

    for t in threads:
        t.join()
