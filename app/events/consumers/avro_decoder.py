import json
from io import BytesIO
from urllib.request import urlopen

from avro import io, schema

from app.config import settings

# Schema cache: schema_id → parsed Schema object.
# Schema Registry schemas are immutable — a given ID always maps to the same schema —
# so caching for the process lifetime is always correct.
_schema_cache: dict[int, schema.Schema] = {}


def _fetch_schema(schema_id: int) -> schema.Schema:
    if schema_id in _schema_cache:
        return _schema_cache[schema_id]

    url = f"{settings.SCHEMA_REGISTRY_URL}/schemas/ids/{schema_id}"
    with urlopen(url, timeout=10) as response:
        body = json.loads(response.read().decode("utf-8"))

    parsed = schema.parse(body["schema"])
    _schema_cache[schema_id] = parsed
    return parsed


def decode(raw_bytes: bytes) -> dict:
    """Decode a Confluent Avro message into a plain dict.

    Confluent wire format:
        byte 0      — magic byte (0x00)
        bytes 1–4   — schema ID (big-endian uint32)
        bytes 5+    — Avro binary payload

    Returns {"schema_id": int, "payload": dict}.
    Raises ValueError if the magic byte is wrong or the payload is too short.
    """
    if len(raw_bytes) < 5 or raw_bytes[0] != 0x00:
        raise ValueError(
            f"Not a valid Confluent Avro message — "
            f"expected magic byte 0x00, got {raw_bytes[:5]!r}"
        )

    schema_id = int.from_bytes(raw_bytes[1:5], byteorder="big", signed=False)
    parsed_schema = _fetch_schema(schema_id)

    decoder = io.BinaryDecoder(BytesIO(raw_bytes[5:]))
    reader = io.DatumReader(parsed_schema)
    payload = reader.read(decoder)

    return {"schema_id": schema_id, "payload": payload}
