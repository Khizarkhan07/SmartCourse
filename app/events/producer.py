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

from app.config import settings
from app.core.logging import get_logger


logger = get_logger(__name__)


class SchemaRegistryClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = (base_url or settings.SCHEMA_REGISTRY_URL).rstrip("/")

    def register_schema(self, subject: str, schema_str: str) -> int:
        payload = json.dumps({"schema": schema_str}).encode("utf-8")
        request = Request(
            url=f"{self.base_url}/subjects/{subject}/versions",
            data=payload,
            headers={"Content-Type": "application/vnd.schemaregistry.v1+json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=10) as response:
                body = json.loads(response.read().decode("utf-8"))
                return int(body["id"])
        except HTTPError as exc:
            details = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Schema registration failed for subject '{subject}': {details}"
            ) from exc


class KafkaEventProducer:
    def __init__(
        self,
        brokers: str | None = None,
        schema_registry_url: str | None = None,
    ) -> None:
        _brokers = brokers or settings.KAFKA_BROKERS
        self._producer = KafkaProducer(bootstrap_servers=_brokers.split(","))
        self._registry = SchemaRegistryClient(schema_registry_url)
        self._schema_cache: dict[str, tuple[int, schema.Schema]] = {}

    @staticmethod
    def _schema_path(schema_file_name: str) -> Path:
        return Path(__file__).resolve().parent / "schemas" / schema_file_name

    def _load_schema(
        self,
        schema_file_name: str,
        subject: str,
    ) -> tuple[int, schema.Schema]:
        if schema_file_name in self._schema_cache:
            return self._schema_cache[schema_file_name]

        schema_path = self._schema_path(schema_file_name)
        schema_text = schema_path.read_text(encoding="utf-8")
        schema_id = self._registry.register_schema(subject, schema_text)
        parsed_schema = schema.parse(schema_text)
        self._schema_cache[schema_file_name] = (schema_id, parsed_schema)
        return schema_id, parsed_schema

    @staticmethod
    def _encode_value(schema_id: int, parsed_schema: schema.Schema, payload: dict) -> bytes:
        # Confluent wire format: magic byte + 4-byte schema ID + Avro payload.
        out = BytesIO()
        out.write(b"\x00")
        out.write(schema_id.to_bytes(4, byteorder="big", signed=False))
        encoder = io.BinaryEncoder(out)
        writer = io.DatumWriter(parsed_schema)
        writer.write(payload, encoder)
        return out.getvalue()

    def _send(self, topic: str, key: str, schema_file_name: str, payload: dict) -> None:
        # Inject W3C TraceContext into Kafka headers so consumers can link their
        # spans back to the originating API request trace
        carrier: dict[str, str] = {}
        inject(carrier)
        kafka_headers = [(k, v.encode("utf-8")) for k, v in carrier.items()]

        # Populate trace_id in the event envelope for structured log correlation
        span_ctx = trace.get_current_span().get_span_context()
        if span_ctx.is_valid:
            payload["trace_id"] = format(span_ctx.trace_id, "032x")

        subject = f"{topic}-value"
        schema_id, parsed_schema = self._load_schema(schema_file_name, subject)
        encoded_value = self._encode_value(schema_id, parsed_schema, payload)
        self._producer.send(topic, key=key.encode("utf-8"), value=encoded_value, headers=kafka_headers)
        self._producer.flush(timeout=10)

        logger.info(
            "kafka event published",
            topic=topic,
            key=key,
            schema_id=schema_id,
            event_type=payload.get("event_type"),
            event_id=payload.get("event_id"),
            event_version=payload.get("event_version"),
        )

    def emit_enrollment_created(
        self,
        enrollment_id: str,
        student_id: str,
        course_id: str,
        status: str,
        progress_percentage: int,
    ) -> None:
        occurred_at = datetime.now(timezone.utc).isoformat()
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "enrollment.created",
            "event_version": 1,
            "occurred_at": occurred_at,
            "producer": "smartcourse-api",
            "trace_id": "",
            "payload": {
                "enrollment_id": enrollment_id,
                "student_id": student_id,
                "course_id": course_id,
                "status": status,
                "progress_percentage": progress_percentage,
                "enrolled_at": occurred_at,
            },
        }
        self._send("enrollment.created", student_id, "enrollment_created.avsc", event)

    def emit_course_published(
        self,
        course_id: str,
        instructor_id: str,
        title: str,
    ) -> None:
        published_at = datetime.now(timezone.utc).isoformat()
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "course.published",
            "event_version": 1,
            "occurred_at": published_at,
            "producer": "smartcourse-api",
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

    def emit_enrollment_completed(
        self,
        enrollment_id: str,
        student_id: str,
        student_name: str,
        course_id: str,
        course_title: str,
    ) -> None:
        completed_at = datetime.now(timezone.utc).isoformat()
        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "enrollment.completed",
            "event_version": 1,
            "occurred_at": completed_at,
            "producer": "smartcourse-api",
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