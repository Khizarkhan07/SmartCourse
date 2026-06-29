import asyncio
import time

from kafka import KafkaConsumer, KafkaProducer
from opentelemetry import trace
from opentelemetry.propagate import extract

from config import settings
from core.logging import get_logger
from events.avro_decoder import decode
from events.certificate_issuer import issue_certificate

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

DLQ_TOPIC = "enrollment.completed.dlq"
FAILED_TOPIC = "enrollment.completed.failed"
GROUP_ID = "certificate-service-dlq-reprocessor"

# How long to wait before attempting each DLQ message (gives downstream time to recover)
RETRY_INTERVAL_SECONDS = settings.DLQ_RETRY_INTERVAL_SECONDS
# After this many attempts from the DLQ the message is parked in .failed
MAX_DLQ_ATTEMPTS = settings.DLQ_MAX_ATTEMPTS


class DLQReprocessor:
    """Always-on consumer that retries messages from the DLQ.

    Flow per message:
      1. Sleep RETRY_INTERVAL_SECONDS  (back-pressure: let the system recover)
      2. Decode and call issue_certificate()
      3. On success  → commit DLQ offset
      4. On failure after MAX_DLQ_ATTEMPTS → park in enrollment.completed.failed → commit
    """

    def __init__(self) -> None:
        self._consumer = KafkaConsumer(
            DLQ_TOPIC,
            bootstrap_servers=settings.KAFKA_BROKERS.split(","),
            group_id=GROUP_ID,
            auto_offset_reset="earliest",
            enable_auto_commit=False,
        )
        self._parking_producer = KafkaProducer(
            bootstrap_servers=settings.KAFKA_BROKERS.split(","),
            acks="all",
        )

    def run(self) -> None:
        logger.info(
            "DLQ reprocessor started",
            topic=DLQ_TOPIC,
            group_id=GROUP_ID,
            retry_interval=RETRY_INTERVAL_SECONDS,
            max_attempts=MAX_DLQ_ATTEMPTS,
        )
        try:
            for message in self._consumer:
                self._handle(message)
        finally:
            self._parking_producer.close()
            self._consumer.close()

    def _handle(self, message) -> None:
        headers = {k: v.decode() for k, v in (message.headers or [])}
        prior_retries = int(headers.get("x-retry-count", "0"))
        attempt_number = prior_retries + 1

        logger.info(
            "DLQ message received, waiting before retry",
            partition=message.partition,
            offset=message.offset,
            prior_retries=prior_retries,
            wait_seconds=RETRY_INTERVAL_SECONDS,
            original_failure=headers.get("x-failure-reason", "unknown"),
        )

        time.sleep(RETRY_INTERVAL_SECONDS)

        ctx = extract(headers)
        with tracer.start_as_current_span(
            "enrollment.completed.dlq process",
            context=ctx,
            kind=trace.SpanKind.CONSUMER,
        ) as span:
            span.set_attribute("messaging.system", "kafka")
            span.set_attribute("messaging.destination", DLQ_TOPIC)
            span.set_attribute("dlq.attempt_number", attempt_number)

            try:
                result = decode(message.value)
                inner = result["payload"].get("payload", {})
                span.set_attribute("enrollment.id", inner.get("enrollment_id", ""))

                asyncio.run(issue_certificate(inner))

                logger.info(
                    "DLQ message reprocessed successfully",
                    partition=message.partition,
                    offset=message.offset,
                    attempt_number=attempt_number,
                    enrollment_id=inner.get("enrollment_id"),
                )
                self._consumer.commit()

            except Exception as exc:
                span.record_exception(exc)
                logger.error(
                    "DLQ reprocessing failed",
                    partition=message.partition,
                    offset=message.offset,
                    attempt_number=attempt_number,
                    error=str(exc),
                )

                if attempt_number >= MAX_DLQ_ATTEMPTS:
                    self._park(message, headers, str(exc), attempt_number)
                else:
                    # Put back on DLQ with incremented retry count so the
                    # reprocessor picks it up again on the next pass
                    self._requeue(message, headers, str(exc), attempt_number)

                self._consumer.commit()

    def _park(self, message, headers: dict, failure_reason: str, attempt_number: int) -> None:
        """Move to the terminal parking lot — requires manual intervention."""
        parking_headers = [
            ("x-original-topic", headers.get("x-original-topic", "").encode()),
            ("x-original-partition", headers.get("x-original-partition", "").encode()),
            ("x-original-offset", headers.get("x-original-offset", "").encode()),
            ("x-failure-reason", failure_reason[:1000].encode()),
            ("x-retry-count", str(attempt_number).encode()),
        ]
        self._parking_producer.send(
            FAILED_TOPIC,
            key=message.key,
            value=message.value,
            headers=parking_headers,
        )
        self._parking_producer.flush()
        logger.error(
            "message parked in failed topic — manual intervention required",
            failed_topic=FAILED_TOPIC,
            partition=message.partition,
            offset=message.offset,
            attempt_number=attempt_number,
        )

    def _requeue(self, message, headers: dict, failure_reason: str, attempt_number: int) -> None:
        """Republish to the DLQ with an incremented retry count."""
        updated_headers = [
            ("x-original-topic", headers.get("x-original-topic", "").encode()),
            ("x-original-partition", headers.get("x-original-partition", "").encode()),
            ("x-original-offset", headers.get("x-original-offset", "").encode()),
            ("x-group-id", GROUP_ID.encode()),
            ("x-failure-reason", failure_reason[:1000].encode()),
            ("x-retry-count", str(attempt_number).encode()),
        ]
        self._parking_producer.send(
            DLQ_TOPIC,
            key=message.key,
            value=message.value,
            headers=updated_headers,
        )
        self._parking_producer.flush()
        logger.warning(
            "message requeued to DLQ",
            dlq_topic=DLQ_TOPIC,
            attempt_number=attempt_number,
            remaining=MAX_DLQ_ATTEMPTS - attempt_number,
        )
