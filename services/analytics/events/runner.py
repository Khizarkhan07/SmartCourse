import threading

from core.logging import configure_logging, get_logger
from core.tracing import configure_tracing
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from database import engine
from events.enrollment_created_consumer import EnrollmentCreatedConsumer
from events.enrollment_completed_consumer import EnrollmentCompletedConsumer
from events.course_published_consumer import CoursePublishedConsumer

configure_logging()
configure_tracing()
SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)

logger = get_logger(__name__)


def _run(consumer) -> None:
    consumer.run()


if __name__ == "__main__":
    consumers = [
        EnrollmentCreatedConsumer(),
        EnrollmentCompletedConsumer(),
        CoursePublishedConsumer(),
    ]

    threads = [threading.Thread(target=_run, args=(c,), daemon=True) for c in consumers]

    for t in threads:
        t.start()

    logger.info("analytics consumers started", count=len(consumers))

    for t in threads:
        t.join()
