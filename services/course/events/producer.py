import json
import uuid
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from avro import io, schema
from kafka import KafkaProducer
from opentelemetry import trace
from opentelemetry.propagate import inject

from config import settings
from core.logging import get_logger

logger = get_logger(__name__)

_SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"

_producer: "CourseEventProducer | None" = None


def get_producer() -> "CourseEventProducer":
    global _producer
    if _producer is None:
        _producer = CourseEventProducer()
    return _producer


class CourseEventProducer:
    def __init__(self) -> None:
        self._kafka = KafkaProducer(bootstrap_servers=settings.KAFKA_BROKERS.split(","))
        self._schema_cache: dict[str, tuple[int, schema.Schema]] = {}

    def _ensure_schema(self, schema_file: str, topic: str) -> tuple[int, schema.Schema]:
        if schema_file in self._schema_cache:
            return self._schema_cache[schema_file]

        schema_text = (_SCHEMA_DIR / schema_file).read_text(encoding="utf-8")
        subject = f"{topic}-value"
        payload = json.dumps({"schema": schema_text}).encode()
        req = Request(
            url=f"{settings.SCHEMA_REGISTRY_URL}/subjects/{subject}/versions",
            data=payload,
            headers={"Content-Type": "application/vnd.schemaregistry.v1+json"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=10) as resp:
                schema_id = int(json.loads(resp.read())["id"])
        except HTTPError as exc:
            raise RuntimeError(f"Schema registration failed: {exc.read().decode()}") from exc

        parsed = schema.parse(schema_text)
        self._schema_cache[schema_file] = (schema_id, parsed)
        return schema_id, parsed

    def _encode(self, schema_id: int, parsed: schema.Schema, data: dict) -> bytes:
        buf = BytesIO()
        buf.write(b"\x00")
        buf.write(schema_id.to_bytes(4, byteorder="big", signed=False))
        io.DatumWriter(parsed).write(data, io.BinaryEncoder(buf))
        return buf.getvalue()

    def _send(self, topic: str, key: str, schema_file: str, event: dict) -> None:
        carrier: dict[str, str] = {}
        inject(carrier)
        headers = [(k, v.encode()) for k, v in carrier.items()]

        span_ctx = trace.get_current_span().get_span_context()
        event["trace_id"] = format(span_ctx.trace_id, "032x") if span_ctx.is_valid else ""

        schema_id, parsed = self._ensure_schema(schema_file, topic)
        self._kafka.send(topic, key=key.encode(), value=self._encode(schema_id, parsed, event), headers=headers)
        self._kafka.flush(timeout=10)
        logger.info("kafka event published", topic=topic, event_type=event.get("event_type"))

    def emit_course_published(self, course_id: str, instructor_id: str, title: str) -> None:
        published_at = datetime.now(timezone.utc).isoformat()
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "course.published",
            "event_version": 1,
            "occurred_at": published_at,
            "producer": "course-service",
            "trace_id": "",
            "payload": {
                "course_id": course_id,
                "instructor_id": instructor_id,
                "title": title,
                "status": "published",
                "published_at": published_at,
            },
        }
        self._send("course.published", course_id, "course_published.avsc", event)
        logger.info("course.published emitted", course_id=course_id)
