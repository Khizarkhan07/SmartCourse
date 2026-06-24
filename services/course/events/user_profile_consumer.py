from kafka import KafkaConsumer
from opentelemetry import trace
from opentelemetry.propagate import extract

from config import settings
from core.logging import get_logger
from database import SyncSessionLocal
from events.avro_decoder import decode
from repositories.instructor_profile_repository import SyncInstructorProfileRepository

logger = get_logger(__name__)
tracer = trace.get_tracer(__name__)

TOPIC = "user.profile_updated"
GROUP_ID = "course-service-user-profile"


class UserProfileConsumer:
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
                "user.profile_updated process",
                context=ctx,
                kind=trace.SpanKind.CONSUMER,
            ) as span:
                span.set_attribute("messaging.system", "kafka")
                span.set_attribute("messaging.destination", TOPIC)

                try:
                    result = decode(message.value)
                    payload = result["payload"].get("payload", {})
                    user_id = payload.get("user_id", "")
                    span.set_attribute("user.id", user_id)

                    logger.info(
                        "user.profile_updated received",
                        user_id=user_id,
                        role=payload.get("role"),
                        is_active=payload.get("is_active"),
                    )
                    self._upsert_profile(payload)

                except Exception as exc:
                    span.record_exception(exc)
                    logger.error("failed to process user.profile_updated", error=str(exc))

    def _upsert_profile(self, payload: dict) -> None:
        with SyncSessionLocal() as session:
            repo = SyncInstructorProfileRepository(session)
            repo.upsert(
                user_id=payload["user_id"],
                name=payload["name"],
                email=payload["email"],
                is_active=payload["is_active"],
            )
            logger.info("instructor_profile upserted", user_id=payload["user_id"])
