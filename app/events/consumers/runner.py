import threading

from app.core.logging import configure_logging, get_logger
from app.core.tracing import configure_tracing
from app.events.consumers.course_consumer import CourseConsumer

logger = get_logger(__name__)


def main() -> None:
    configure_logging()
    configure_tracing()
    logger.info("starting kafka consumer runner")

    consumers = [
        ("course", CourseConsumer()),
    ]

    threads = []
    for name, consumer in consumers:
        t = threading.Thread(target=consumer.run, name=f"{name}-consumer", daemon=True)
        t.start()
        threads.append(t)
        logger.info("consumer thread started", consumer=name)

    logger.info("all consumers running — press Ctrl+C to stop")

    try:
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        logger.info("shutdown signal received — stopping consumers")


if __name__ == "__main__":
    main()
