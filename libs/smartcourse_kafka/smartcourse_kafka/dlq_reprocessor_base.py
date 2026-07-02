import time
from datetime import datetime, timezone

import structlog
from kafka import KafkaConsumer, KafkaProducer
from opentelemetry import trace
from opentelemetry.propagate import extract
from pydantic_settings import BaseSettings

from smartcourse_kafka.avro_decoder import decode

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)


class _Settings(BaseSettings):
    KAFKA_BROKERS: str = "localhost:9092"
    DLQ_RETRY_INTERVAL_SECONDS: int = 60
    DLQ_MAX_ATTEMPTS: int = 3


_settings = _Settings()


class BaseDLQReprocessor:
    """Base DLQ reprocessor. Subclasses declare three class attributes and implement _process().

    Class attributes required on each subclass:
        DLQ_TOPIC   — Kafka topic to consume from (e.g. "user.profile_updated.dlq")
        FAILED_TOPIC — Kafka topic to park permanently failed messages in
        GROUP_ID    — Kafka consumer group id for this reprocessor
    """

    DLQ_TOPIC: str
    FAILED_TOPIC: str
    GROUP_ID: str

    def __init__(self) -> None:
        self._consumer = KafkaConsumer(
            self.DLQ_TOPIC,
            bootstrap_servers=_settings.KAFKA_BROKERS.split(","),
            group_id=self.GROUP_ID,
            auto_offset_reset="earliest",
            enable_auto_commit=False,
        )
        self._parking_producer = KafkaProducer(
            bootstrap_servers=_settings.KAFKA_BROKERS.split(","),
            acks="all",
        )

    def _process(self, payload: dict) -> None:
        raise NotImplementedError

    def run(self) -> None:
        logger.info(
            "DLQ reprocessor started",
            topic=self.DLQ_TOPIC,
            group_id=self.GROUP_ID,
            retry_interval=_settings.DLQ_RETRY_INTERVAL_SECONDS,
            max_attempts=_settings.DLQ_MAX_ATTEMPTS,
        )
        try:
            for message in self._consumer:
                self._handle(message)
        finally:
            self._parking_producer.close()
            self._consumer.close()

    def _wait(self, seconds: float) -> None:
        """Wait while keeping Kafka heartbeat alive via pause()/poll()/resume().

        Unlike time.sleep(), this keeps calling poll() so the broker never
        considers the consumer dead and max_poll_interval_ms is never exceeded.
        """
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
            remaining = max(0.0, _settings.DLQ_RETRY_INTERVAL_SECONDS - elapsed)
        except (ValueError, TypeError):
            remaining = float(_settings.DLQ_RETRY_INTERVAL_SECONDS)

        logger.info(
            "DLQ message received, waiting before retry",
            topic=self.DLQ_TOPIC,
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
            f"{self.DLQ_TOPIC} process",
            context=ctx,
            kind=trace.SpanKind.CONSUMER,
        ) as span:
            span.set_attribute("messaging.system", "kafka")
            span.set_attribute("messaging.destination", self.DLQ_TOPIC)
            span.set_attribute("dlq.attempt_number", attempt_number)

            try:
                result = decode(message.value)
                payload = result["payload"].get("payload", {})

                self._process(payload)

                logger.info(
                    "DLQ message reprocessed successfully",
                    topic=self.DLQ_TOPIC,
                    partition=message.partition,
                    offset=message.offset,
                    attempt_number=attempt_number,
                )
                self._consumer.commit()

            except Exception as exc:
                span.record_exception(exc)
                logger.error(
                    "DLQ reprocessing failed",
                    topic=self.DLQ_TOPIC,
                    partition=message.partition,
                    offset=message.offset,
                    attempt_number=attempt_number,
                    error=str(exc),
                )

                if attempt_number >= _settings.DLQ_MAX_ATTEMPTS:
                    self._park(message, headers, str(exc), attempt_number)
                else:
                    self._requeue(message, headers, str(exc), attempt_number)

                self._consumer.commit()

    def _park(self, message, headers: dict, failure_reason: str, attempt_number: int) -> None:
        self._parking_producer.send(
            self.FAILED_TOPIC,
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
            failed_topic=self.FAILED_TOPIC,
            partition=message.partition,
            offset=message.offset,
            attempt_number=attempt_number,
        )

    def _requeue(self, message, headers: dict, failure_reason: str, attempt_number: int) -> None:
        self._parking_producer.send(
            self.DLQ_TOPIC,
            key=message.key,
            value=message.value,
            headers=[
                ("x-original-topic", headers.get("x-original-topic", "").encode()),
                ("x-original-partition", headers.get("x-original-partition", "").encode()),
                ("x-original-offset", headers.get("x-original-offset", "").encode()),
                ("x-group-id", self.GROUP_ID.encode()),
                ("x-failure-reason", failure_reason[:1000].encode()),
                ("x-retry-count", str(attempt_number).encode()),
            ],
        )
        self._parking_producer.flush()
        logger.warning(
            "message requeued to DLQ",
            dlq_topic=self.DLQ_TOPIC,
            attempt_number=attempt_number,
            remaining=_settings.DLQ_MAX_ATTEMPTS - attempt_number,
        )
