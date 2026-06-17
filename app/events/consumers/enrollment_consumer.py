from kafka import KafkaConsumer
from opentelemetry import trace
from opentelemetry.propagate import extract

from app.config import settings
from app.core.logging import get_logger
from app.events.consumers.avro_decoder import decode
from app.worker.tasks.analytics_tasks import invalidate_analytics_cache_task

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

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
            # Extract W3C trace context from Kafka headers — links this span to
            # the API request that originally produced the message
            headers_dict = {k: v.decode("utf-8") for k, v in (message.headers or [])}
            ctx = extract(headers_dict)

            with tracer.start_as_current_span(
                "enrollment.created process",
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
                    span.set_attribute("enrollment.id", inner.get("enrollment_id", ""))
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
                    span.record_exception(exc)
                    logger.error(
                        "failed to decode enrollment.created message",
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
                    enrollment_id=inner.get("enrollment_id"),
                )
            except Exception as exc:
                logger.error(
                    "failed to dispatch analytics cache invalidation",
                    event_id=event.get("event_id"),
                    error=str(exc),
                )
