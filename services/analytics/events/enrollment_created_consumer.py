from datetime import datetime, timezone

from kafka import KafkaConsumer
from opentelemetry import trace
from opentelemetry.propagate import extract

from config import settings
from core.logging import get_logger
from database import SyncSessionLocal
from events.avro_decoder import decode
from models.enrollment_fact import EnrollmentFact
from repositories.enrollment_fact_repository import SyncEnrollmentFactRepository

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

TOPIC = "enrollment.created"
GROUP_ID = "analytics-service-enrollment-created"


class EnrollmentCreatedConsumer:
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
                "enrollment.created process",
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
                        "enrollment.created received",
                        enrollment_id=enrollment_id,
                        student_id=inner.get("student_id"),
                        course_id=inner.get("course_id"),
                    )
                    self._upsert_fact(inner)

                except Exception as exc:
                    span.record_exception(exc)
                    logger.error("failed to process enrollment.created", error=str(exc))

    def _upsert_fact(self, payload: dict) -> None:
        enrollment_id = payload["enrollment_id"]
        with SyncSessionLocal() as session:
            repo = SyncEnrollmentFactRepository(session)
            if repo.get_by_enrollment_id(enrollment_id):
                logger.info("enrollment_fact already exists", enrollment_id=enrollment_id)
                return

            try:
                enrolled_at = datetime.fromisoformat(payload.get("enrolled_at", ""))
            except (ValueError, TypeError):
                enrolled_at = datetime.now(timezone.utc)

            fact = EnrollmentFact(
                enrollment_id=enrollment_id,
                student_id=payload["student_id"],
                course_id=payload["course_id"],
                course_title="",
                status="active",
                enrolled_at=enrolled_at,
                completed_at=None,
                updated_at=datetime.now(timezone.utc),
            )
            repo.create(fact)
            logger.info("enrollment_fact created", enrollment_id=enrollment_id)
