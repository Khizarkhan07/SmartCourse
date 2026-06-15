from kafka import KafkaConsumer

from app.config import settings
from app.core.logging import get_logger
from app.events.consumers.avro_decoder import decode

logger = get_logger(__name__)

TOPIC = "course.published"
GROUP_ID = "smartcourse-course-consumer"


class CourseConsumer:
    def __init__(self) -> None:
        self._consumer = KafkaConsumer(
            TOPIC,
            bootstrap_servers=settings.KAFKA_BROKERS.split(","),
            group_id=GROUP_ID,
            auto_offset_reset="earliest",
            enable_auto_commit=True,
        )

    def run(self) -> None:
        logger.info("course consumer started", topic=TOPIC, group_id=GROUP_ID)
        for message in self._consumer:
            try:
                result = decode(message.value)
                event = result["payload"]       # full Avro envelope
                inner = event.get("payload", {})  # domain fields nested inside
                logger.info(
                    "course.published received",
                    schema_id=result["schema_id"],
                    event_id=event.get("event_id"),
                    course_id=inner.get("course_id"),
                    instructor_id=inner.get("instructor_id"),
                    title=inner.get("title"),
                    status=inner.get("status"),
                )
            except Exception as exc:
                logger.error(
                    "failed to decode course.published message",
                    offset=message.offset,
                    partition=message.partition,
                    error=str(exc),
                )
