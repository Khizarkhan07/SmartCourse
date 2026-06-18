import logging
import sys

import structlog


_configured = False


def configure_logging() -> None:
    global _configured
    if _configured:
        return

    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO,
        stream=sys.stdout,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str):
    configure_logging()
    return structlog.get_logger(name)