from datetime import datetime, timezone

from kafka import KafkaConsumer
from opentelemetry import trace
from opentelemetry.propagate import extract

from config import settings
from core.logging import get_logger
from database import SyncSessionLocal
from events.avro_decoder import decode
from models.course_fact import CourseFact
from repositories.course_fact_repository import SyncCourseFactRepository

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

TOPIC = "course.published"
GROUP_ID = "analytics-service-course-published"


class CoursePublishedConsumer:
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
                "course.published process",
                context=ctx,
                kind=trace.SpanKind.CONSUMER,
            ) as span:
                span.set_attribute("messaging.system", "kafka")
                span.set_attribute("messaging.destination", TOPIC)

                try:
                    result = decode(message.value)
                    inner = result["payload"].get("payload", {})
                    course_id = inner.get("course_id", "")
                    span.set_attribute("course.id", course_id)

                    logger.info(
                        "course.published received",
                        course_id=course_id,
                        title=inner.get("title"),
                    )
                    self._upsert_fact(inner)

                except Exception as exc:
                    span.record_exception(exc)
                    logger.error("failed to process course.published", error=str(exc))

    def _upsert_fact(self, payload: dict) -> None:
        try:
            published_at = datetime.fromisoformat(payload.get("published_at", ""))
        except (ValueError, TypeError):
            published_at = datetime.now(timezone.utc)

        fact = CourseFact(
            course_id=payload["course_id"],
            title=payload["title"],
            instructor_id=payload["instructor_id"],
            status=payload.get("status", "published"),
            published_at=published_at,
            updated_at=datetime.now(timezone.utc),
        )
        with SyncSessionLocal() as session:
            repo = SyncCourseFactRepository(session)
            repo.upsert(fact)
            logger.info("course_fact upserted", course_id=fact.course_id, title=fact.title)
