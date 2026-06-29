from core.logging import configure_logging
from core.tracing import configure_tracing
from events.dlq_reprocessor import DLQReprocessor


def main() -> None:
    configure_logging()
    configure_tracing()
    DLQReprocessor().run()


if __name__ == "__main__":
    main()
