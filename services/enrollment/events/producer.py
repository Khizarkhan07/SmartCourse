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

_producer: "EnrollmentEventProducer | None" = None


def get_producer() -> "EnrollmentEventProducer":
    global _producer
    if _producer is None:
        _producer = EnrollmentEventProducer()
    return _producer


class EnrollmentEventProducer:
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

    def emit_enrollment_created(
        self,
        enrollment_id: str,
        student_id: str,
        course_id: str,
        enrolled_at: str,
    ) -> None:
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "enrollment.created",
            "event_version": 1,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "producer": "enrollment-service",
            "trace_id": "",
            "payload": {
                "enrollment_id": enrollment_id,
                "student_id": student_id,
                "course_id": course_id,
                "status": "enrolled",
                "progress_percentage": 0,
                "enrolled_at": enrolled_at,
            },
        }
        self._send("enrollment.created", enrollment_id, "enrollment_created.avsc", event)

    def emit_enrollment_completed(
        self,
        enrollment_id: str,
        student_id: str,
        student_name: str,
        course_id: str,
        course_title: str,
        completed_at: str,
    ) -> None:
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "enrollment.completed",
            "event_version": 1,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "producer": "enrollment-service",
            "trace_id": "",
            "payload": {
                "enrollment_id": enrollment_id,
                "student_id": student_id,
                "student_name": student_name,
                "course_id": course_id,
                "course_title": course_title,
                "completed_at": completed_at,
            },
        }
        self._send("enrollment.completed", enrollment_id, "enrollment_completed.avsc", event)
