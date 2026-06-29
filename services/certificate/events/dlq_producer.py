from datetime import datetime, timezone

from kafka import KafkaProducer

from config import settings
from core.logging import get_logger

logger = get_logger(__name__)


class DLQProducer:
    """Publishes un-processable messages to a dead letter topic.

    The DLQ topic name is always <original-topic>.dlq.
    Error context is attached as Kafka headers so a reprocessor can
    inspect failures without decoding the Avro payload.
    """

    def __init__(self) -> None:
        self._producer = KafkaProducer(
            bootstrap_servers=settings.KAFKA_BROKERS.split(","),
            acks="all",
        )

    def send(
        self,
        *,
        original_topic: str,
        original_partition: int,
        original_offset: int,
        original_key: bytes | None,
        raw_value: bytes,
        group_id: str,
        failure_reason: str,
        retry_count: int,
    ) -> None:
        dlq_topic = f"{original_topic}.dlq"
        headers = [
            ("x-original-topic", original_topic.encode()),
            ("x-original-partition", str(original_partition).encode()),
            ("x-original-offset", str(original_offset).encode()),
            ("x-group-id", group_id.encode()),
            ("x-failure-reason", failure_reason[:1000].encode()),
            ("x-retry-count", str(retry_count).encode()),
            ("x-failed-at", datetime.now(timezone.utc).isoformat().encode()),
        ]

        self._producer.send(
            dlq_topic,
            key=original_key,
            value=raw_value,
            headers=headers,
        )
        self._producer.flush()

        logger.warning(
            "message sent to DLQ",
            dlq_topic=dlq_topic,
            original_topic=original_topic,
            partition=original_partition,
            offset=original_offset,
            retry_count=retry_count,
            failure_reason=failure_reason[:200],
        )

    def close(self) -> None:
        self._producer.close()
