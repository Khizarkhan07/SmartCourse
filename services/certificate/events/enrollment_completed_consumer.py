import asyncio
from datetime import datetime, timezone

from kafka import KafkaConsumer
from opentelemetry import trace
from opentelemetry.propagate import extract

from config import settings
from core.logging import get_logger
from database import AsyncSessionLocal
from events.avro_decoder import decode
from models.certificate import Certificate
from repositories.certificate_repository import CertificateRepository

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

TOPIC = "enrollment.completed"
GROUP_ID = "certificate-service-enrollment-completed"


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
        logger.info("enrollment.completed consumer started", topic=TOPIC, group_id=GROUP_ID)
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
                span.set_attribute("messaging.kafka.partition", message.partition)

                try:
                    result = decode(message.value)
                    event = result["payload"]
                    inner = event.get("payload", {})

                    enrollment_id = inner.get("enrollment_id", "")
                    span.set_attribute("enrollment.id", enrollment_id)

                    logger.info(
                        "enrollment.completed received",
                        schema_id=result["schema_id"],
                        event_id=event.get("event_id"),
                        enrollment_id=enrollment_id,
                        student_id=inner.get("student_id"),
                        course_id=inner.get("course_id"),
                    )

                    asyncio.run(self._issue_certificate(inner))

                except Exception as exc:
                    span.record_exception(exc)
                    logger.error(
                        "failed to process enrollment.completed",
                        offset=message.offset,
                        partition=message.partition,
                        error=str(exc),
                    )

    async def _issue_certificate(self, payload: dict) -> None:
        enrollment_id = payload["enrollment_id"]

        async with AsyncSessionLocal() as session:
            repo = CertificateRepository(session)

            # Idempotency guard — skip if a cert already exists for this enrollment
            existing = await repo.get_by_enrollment_id(enrollment_id)
            if existing:
                logger.info(
                    "certificate already exists, skipping",
                    enrollment_id=enrollment_id,
                    certificate_id=existing.id,
                )
                return

            completed_at_str = payload.get("completed_at", "")
            try:
                completed_at = datetime.fromisoformat(completed_at_str)
            except (ValueError, TypeError):
                completed_at = datetime.now(timezone.utc)

            cert = Certificate(
                enrollment_id=enrollment_id,
                student_id=payload["student_id"],
                student_name=payload["student_name"],
                course_id=payload["course_id"],
                course_title=payload["course_title"],
                completed_at=completed_at,
            )
            await repo.create(cert)
            logger.info(
                "certificate issued",
                certificate_id=cert.id,
                enrollment_id=enrollment_id,
                student_id=cert.student_id,
            )
