import json
from io import BytesIO
from urllib.request import urlopen

from avro import io, schema

from config import settings

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
    if len(raw_bytes) < 5 or raw_bytes[0] != 0x00:
        raise ValueError(f"Invalid Confluent Avro message: {raw_bytes[:5]!r}")
    schema_id = int.from_bytes(raw_bytes[1:5], byteorder="big", signed=False)
    parsed_schema = _fetch_schema(schema_id)
    decoder = io.BinaryDecoder(BytesIO(raw_bytes[5:]))
    reader = io.DatumReader(parsed_schema)
    return {"schema_id": schema_id, "payload": reader.read(decoder)}
