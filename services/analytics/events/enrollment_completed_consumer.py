import time

from kafka import KafkaConsumer
from opentelemetry import trace
from opentelemetry.propagate import extract

from config import settings
from core.logging import get_logger
from smartcourse_kafka.avro_decoder import decode
from events.dlq_producer import DLQProducer
from events.enrollment_fact_handler import complete_enrollment_fact

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

TOPIC = "enrollment.completed"
GROUP_ID = "analytics-service-enrollment-completed"
MAX_RETRIES = 3
_RETRY_DELAYS = [2, 4, 8]


class EnrollmentCompletedConsumer:
    def __init__(self) -> None:
        self._consumer = KafkaConsumer(
            TOPIC,
            bootstrap_servers=settings.KAFKA_BROKERS.split(","),
            group_id=GROUP_ID,
            auto_offset_reset="earliest",
            enable_auto_commit=False,
        )
        self._dlq = DLQProducer()

    def run(self) -> None:
        logger.info("consumer started", topic=TOPIC, group_id=GROUP_ID)
        try:
            for message in self._consumer:
                self._handle(message)
        finally:
            self._dlq.close()
            self._consumer.close()

    def _handle(self, message) -> None:
        headers_dict = {k: v.decode("utf-8") for k, v in (message.headers or [])}
        ctx = extract(headers_dict)

        with tracer.start_as_current_span(
            "enrollment.completed process",
            context=ctx,
            kind=trace.SpanKind.CONSUMER,
        ) as span:
            span.set_attribute("messaging.system", "kafka")
            span.set_attribute("messaging.destination", TOPIC)

            last_exc: Exception | None = None

            for attempt in range(MAX_RETRIES):
                try:
                    result = decode(message.value)
                    inner = result["payload"].get("payload", {})
                    enrollment_id = inner.get("enrollment_id", "")
                    span.set_attribute("enrollment.id", enrollment_id)

                    if attempt == 0:
                        logger.info(
                            "enrollment.completed received",
                            enrollment_id=enrollment_id,
                            course_title=inner.get("course_title"),
                        )

                    complete_enrollment_fact(inner)
                    self._consumer.commit()
                    return

                except Exception as exc:
                    last_exc = exc
                    remaining = MAX_RETRIES - attempt - 1
                    logger.warning(
                        "enrollment.completed processing failed",
                        attempt=attempt + 1,
                        remaining_retries=remaining,
                        offset=message.offset,
                        partition=message.partition,
                        error=str(exc),
                    )
                    if remaining > 0:
                        time.sleep(_RETRY_DELAYS[attempt])

            span.record_exception(last_exc)
            self._dlq.send(
                original_topic=TOPIC,
                original_partition=message.partition,
                original_offset=message.offset,
                original_key=message.key,
                raw_value=message.value,
                group_id=GROUP_ID,
                failure_reason=str(last_exc),
                retry_count=MAX_RETRIES,
            )
            self._consumer.commit()
