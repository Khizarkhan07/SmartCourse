from kafka import KafkaConsumer
from opentelemetry import trace
from opentelemetry.propagate import extract

from app.config import settings
from app.core.logging import get_logger
from app.events.consumers.avro_decoder import decode
from app.worker.tasks.analytics_tasks import invalidate_analytics_cache_task

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

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
            headers_dict = {k: v.decode("utf-8") for k, v in (message.headers or [])}
            ctx = extract(headers_dict)

            with tracer.start_as_current_span(
                "course.published process",
                context=ctx,
                kind=trace.SpanKind.CONSUMER,
            ) as span:
                span.set_attribute("messaging.system", "kafka")
                span.set_attribute("messaging.destination", TOPIC)
                span.set_attribute("messaging.kafka.partition", message.partition)

                try:
                    result = decode(message.value)
                    event = result["payload"]         # full Avro envelope
                    inner = event.get("payload", {})  # domain fields nested inside
                    span.set_attribute("course.id", inner.get("course_id", ""))
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
                    span.record_exception(exc)
                    logger.error(
                        "failed to decode course.published message",
                        offset=message.offset,
                        partition=message.partition,
                        error=str(exc),
                    )
                    continue

            # Dispatch Celery tasks after successful decode.
            # Isolated try/except — a dispatch failure must never crash the consumer
            # or prevent the Kafka offset from being committed.
            try:
                invalidate_analytics_cache_task.delay()
                logger.info(
                    "analytics cache invalidation dispatched",
                    event_id=event.get("event_id"),
                    course_id=inner.get("course_id"),
                )
            except Exception as exc:
                logger.error(
                    "failed to dispatch analytics cache invalidation",
                    event_id=event.get("event_id"),
                    error=str(exc),
                )
