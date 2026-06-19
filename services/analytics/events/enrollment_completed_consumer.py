from datetime import datetime, timezone

from kafka import KafkaConsumer
from opentelemetry import trace
from opentelemetry.propagate import extract

from config import settings
from core.logging import get_logger
from database import SyncSessionLocal
from events.avro_decoder import decode
from repositories.enrollment_fact_repository import SyncEnrollmentFactRepository

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

TOPIC = "enrollment.completed"
GROUP_ID = "analytics-service-enrollment-completed"


class EnrollmentCompletedConsumer:
    def __init__(self) -> None:
        self._consumer = KafkaConsumer(
            TOPIC,
            bootstrap_servers=settings.KAFKA_BROKERS.split(","),
            group_id=GROUP_ID,
            auto_offset_reset="earliest",
            enable_auto_commit=True,
        )

    def run(self) -> None:
        logger.info("consumer started", topic=TOPIC, group_id=GROUP_ID)
        for message in self._consumer:
            headers_dict = {k: v.decode("utf-8") for k, v in (message.headers or [])}
            ctx = extract(headers_dict)

            with tracer.start_as_current_span(
                "enrollment.completed process",
                context=ctx,
                kind=trace.SpanKind.CONSUMER,
            ) as span:
                span.set_attribute("messaging.system", "kafka")
                span.set_attribute("messaging.destination", TOPIC)

                try:
                    result = decode(message.value)
                    inner = result["payload"].get("payload", {})
                    enrollment_id = inner.get("enrollment_id", "")
                    span.set_attribute("enrollment.id", enrollment_id)

                    logger.info(
                        "enrollment.completed received",
                        enrollment_id=enrollment_id,
                        course_title=inner.get("course_title"),
                    )
                    self._mark_completed(inner)

                except Exception as exc:
                    span.record_exception(exc)
                    logger.error("failed to process enrollment.completed", error=str(exc))

    def _mark_completed(self, payload: dict) -> None:
        enrollment_id = payload["enrollment_id"]
        try:
            completed_at = datetime.fromisoformat(payload.get("completed_at", ""))
        except (ValueError, TypeError):
            completed_at = datetime.now(timezone.utc)

        with SyncSessionLocal() as session:
            repo = SyncEnrollmentFactRepository(session)
            updated = repo.mark_completed(
                enrollment_id=enrollment_id,
                completed_at=completed_at,
                course_title=payload.get("course_title", ""),
            )
            if updated:
                logger.info("enrollment_fact marked completed", enrollment_id=enrollment_id)
            else:
                logger.warning(
                    "enrollment_fact not found for completion — fact may arrive out of order",
                    enrollment_id=enrollment_id,
                )
