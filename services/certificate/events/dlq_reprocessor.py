import asyncio

from smartcourse_kafka.dlq_reprocessor_base import BaseDLQReprocessor
from events.certificate_issuer import issue_certificate


class DLQReprocessor(BaseDLQReprocessor):
    DLQ_TOPIC    = "enrollment.completed.dlq"
    FAILED_TOPIC = "enrollment.completed.failed"
    GROUP_ID     = "certificate-service-dlq-reprocessor"

    def _process(self, payload: dict) -> None:
        asyncio.run(issue_certificate(payload))
