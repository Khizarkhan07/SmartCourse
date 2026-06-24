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

TOPIC = "user.profile_updated"
SCHEMA_FILE = "user_profile_updated.avsc"
_SCHEMA_DIR = Path(__file__).resolve().parent / "schemas"

_producer: "KafkaEventProducer | None" = None


def get_producer() -> "KafkaEventProducer":
    global _producer
    if _producer is None:
        _producer = KafkaEventProducer()
    return _producer


class KafkaEventProducer:
    def __init__(self) -> None:
        self._kafka = KafkaProducer(bootstrap_servers=settings.KAFKA_BROKERS.split(","))
        self._schema_id: int | None = None
        self._parsed_schema: schema.Schema | None = None

    def _ensure_schema(self) -> tuple[int, schema.Schema]:
        if self._schema_id is not None:
            return self._schema_id, self._parsed_schema  # type: ignore[return-value]

        schema_text = (_SCHEMA_DIR / SCHEMA_FILE).read_text(encoding="utf-8")
        subject = f"{TOPIC}-value"
        payload = json.dumps({"schema": schema_text}).encode()
        req = Request(
            url=f"{settings.SCHEMA_REGISTRY_URL}/subjects/{subject}/versions",
            data=payload,
            headers={"Content-Type": "application/vnd.schemaregistry.v1+json"},
            method="POST",
        )
        try:
            with urlopen(req, timeout=10) as resp:
                self._schema_id = int(json.loads(resp.read())["id"])
        except HTTPError as exc:
            raise RuntimeError(f"Schema registration failed: {exc.read().decode()}") from exc

        self._parsed_schema = schema.parse(schema_text)
        return self._schema_id, self._parsed_schema

    def _encode(self, schema_id: int, parsed: schema.Schema, data: dict) -> bytes:
        buf = BytesIO()
        buf.write(b"\x00")
        buf.write(schema_id.to_bytes(4, byteorder="big", signed=False))
        io.DatumWriter(parsed).write(data, io.BinaryEncoder(buf))
        return buf.getvalue()

    def emit_user_profile_updated(
        self,
        user_id: str,
        name: str,
        email: str,
        role: str,
        is_active: bool,
    ) -> None:
        carrier: dict[str, str] = {}
        inject(carrier)
        headers = [(k, v.encode()) for k, v in carrier.items()]

        span_ctx = trace.get_current_span().get_span_context()
        trace_id = format(span_ctx.trace_id, "032x") if span_ctx.is_valid else ""

        event = {
            "event_id": str(uuid.uuid4()),
            "event_type": "user.profile_updated",
            "event_version": 1,
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "producer": "identity-service",
            "trace_id": trace_id,
            "payload": {
                "user_id": user_id,
                "name": name,
                "email": email,
                "role": role,
                "is_active": is_active,
            },
        }

        schema_id, parsed = self._ensure_schema()
        self._kafka.send(
            TOPIC,
            key=user_id.encode(),
            value=self._encode(schema_id, parsed, event),
            headers=headers,
        )
        self._kafka.flush(timeout=10)
        logger.info("user.profile_updated emitted", user_id=user_id, role=role)


def produce_user_profile_updated(
    user_id: str, name: str, email: str, role: str, is_active: bool
) -> None:
    get_producer().emit_user_profile_updated(user_id, name, email, role, is_active)
