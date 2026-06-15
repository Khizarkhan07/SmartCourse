from kafka import KafkaConsumer

from app.config import settings
from app.core.logging import get_logger
from app.events.consumers.avro_decoder import decode

logger = get_logger(__name__)

TOPIC = "enrollment.created"
GROUP_ID = "smartcourse-enrollment-consumer"


class EnrollmentConsumer:
    def __init__(self) -> None:
        self._consumer = KafkaConsumer(
            TOPIC,
            bootstrap_servers=settings.KAFKA_BROKERS.split(","),
            group_id=GROUP_ID,
            auto_offset_reset="earliest",
            enable_auto_commit=True,
        )

    def run(self) -> None:
        logger.info("enrollment consumer started", topic=TOPIC, group_id=GROUP_ID)
        for message in self._consumer:
            try:
                result = decode(message.value)
                event = result["payload"]       # full Avro envelope
                inner = event.get("payload", {})  # domain fields nested inside
                logger.info(
                    "enrollment.created received",
                    schema_id=result["schema_id"],
                    event_id=event.get("event_id"),
                    enrollment_id=inner.get("enrollment_id"),
                    student_id=inner.get("student_id"),
                    course_id=inner.get("course_id"),
                    status=inner.get("status"),
                    progress_percentage=inner.get("progress_percentage"),
                )
            except Exception as exc:
                logger.error(
                    "failed to decode enrollment.created message",
                    offset=message.offset,
                    partition=message.partition,
                    error=str(exc),
                )
