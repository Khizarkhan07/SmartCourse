import threading

from app.core.logging import configure_logging, get_logger
from app.events.consumers.enrollment_consumer import EnrollmentConsumer
from app.events.consumers.course_consumer import CourseConsumer

logger = get_logger(__name__)


def main() -> None:
    configure_logging()
    logger.info("starting kafka consumer runner")

    consumers = [
        ("enrollment", EnrollmentConsumer()),
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
        # Block the main thread. Daemon threads keep running as long as this stays alive.
        for t in threads:
            t.join()
    except KeyboardInterrupt:
        logger.info("shutdown signal received — stopping consumers")


if __name__ == "__main__":
    main()
