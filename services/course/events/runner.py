import threading

from core.logging import configure_logging, get_logger
from core.tracing import configure_tracing
from database import sync_engine
from events.user_profile_consumer import UserProfileConsumer
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

configure_logging()
configure_tracing()
SQLAlchemyInstrumentor().instrument(engine=sync_engine)

logger = get_logger(__name__)


def _run(consumer) -> None:
    consumer.run()


if __name__ == "__main__":
    consumers = [UserProfileConsumer()]
    threads = [threading.Thread(target=_run, args=(c,), daemon=True) for c in consumers]

    for t in threads:
        t.start()

    logger.info("course consumers started", count=len(consumers))

    for t in threads:
        t.join()
