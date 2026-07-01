import time
from datetime import datetime, timezone

from kafka import KafkaConsumer, KafkaProducer
from opentelemetry import trace
from opentelemetry.propagate import extract

from config import settings
from core.logging import get_logger
from events.avro_decoder import decode
from events.profile_updater import upsert_profile

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

DLQ_TOPIC = "user.profile_updated.dlq"
FAILED_TOPIC = "user.profile_updated.failed"
GROUP_ID = "course-service-user-profile-dlq-reprocessor"

RETRY_INTERVAL_SECONDS = settings.DLQ_RETRY_INTERVAL_SECONDS
MAX_DLQ_ATTEMPTS = settings.DLQ_MAX_ATTEMPTS


class UserProfileDLQReprocessor:
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
            "user profile DLQ reprocessor started",
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

    def _wait(self, seconds: float) -> None:
        """Wait while keeping Kafka heartbeat alive via pause()/poll()/resume()."""
        assignment = self._consumer.assignment()
        self._consumer.pause(*assignment)
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self._consumer.poll(timeout_ms=1000)
        self._consumer.resume(*assignment)

    def _handle(self, message) -> None:
        headers = {k: v.decode() for k, v in (message.headers or [])}
        prior_retries = int(headers.get("x-retry-count", "0"))
        attempt_number = prior_retries + 1

        failed_at_str = headers.get("x-failed-at", "")
        try:
            failed_at = datetime.fromisoformat(failed_at_str)
            elapsed = (datetime.now(timezone.utc) - failed_at).total_seconds()
            remaining = max(0.0, RETRY_INTERVAL_SECONDS - elapsed)
        except (ValueError, TypeError):
            remaining = float(RETRY_INTERVAL_SECONDS)

        logger.info(
            "DLQ message received, waiting before retry",
            partition=message.partition,
            offset=message.offset,
            prior_retries=prior_retries,
            wait_seconds=remaining,
            original_failure=headers.get("x-failure-reason", "unknown"),
        )

        if remaining > 0:
            self._wait(remaining)

        ctx = extract(headers)
        with tracer.start_as_current_span(
            "user.profile_updated.dlq process",
            context=ctx,
            kind=trace.SpanKind.CONSUMER,
        ) as span:
            span.set_attribute("messaging.system", "kafka")
            span.set_attribute("messaging.destination", DLQ_TOPIC)
            span.set_attribute("dlq.attempt_number", attempt_number)

            try:
                result = decode(message.value)
                payload = result["payload"].get("payload", {})
                span.set_attribute("user.id", payload.get("user_id", ""))

                upsert_profile(payload)

                logger.info(
                    "DLQ message reprocessed successfully",
                    partition=message.partition,
                    offset=message.offset,
                    attempt_number=attempt_number,
                    user_id=payload.get("user_id"),
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
                    self._requeue(message, headers, str(exc), attempt_number)

                self._consumer.commit()

    def _park(self, message, headers: dict, failure_reason: str, attempt_number: int) -> None:
        self._parking_producer.send(
            FAILED_TOPIC,
            key=message.key,
            value=message.value,
            headers=[
                ("x-original-topic", headers.get("x-original-topic", "").encode()),
                ("x-original-partition", headers.get("x-original-partition", "").encode()),
                ("x-original-offset", headers.get("x-original-offset", "").encode()),
                ("x-failure-reason", failure_reason[:1000].encode()),
                ("x-retry-count", str(attempt_number).encode()),
            ],
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
        self._parking_producer.send(
            DLQ_TOPIC,
            key=message.key,
            value=message.value,
            headers=[
                ("x-original-topic", headers.get("x-original-topic", "").encode()),
                ("x-original-partition", headers.get("x-original-partition", "").encode()),
                ("x-original-offset", headers.get("x-original-offset", "").encode()),
                ("x-group-id", GROUP_ID.encode()),
                ("x-failure-reason", failure_reason[:1000].encode()),
                ("x-retry-count", str(attempt_number).encode()),
            ],
        )
        self._parking_producer.flush()
        logger.warning(
            "message requeued to DLQ",
            dlq_topic=DLQ_TOPIC,
            attempt_number=attempt_number,
            remaining=MAX_DLQ_ATTEMPTS - attempt_number,
        )
