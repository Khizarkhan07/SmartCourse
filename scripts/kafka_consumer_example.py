import json
from io import BytesIO
from urllib.request import urlopen

from avro import io, schema
from kafka import KafkaConsumer


SCHEMA_REGISTRY_URL = "http://localhost:8081"


def fetch_schema(schema_id: int) -> dict:
    with urlopen(f"{SCHEMA_REGISTRY_URL}/schemas/ids/{schema_id}", timeout=10) as response:
        body = json.loads(response.read().decode("utf-8"))
        return schema.parse(body["schema"])


def decode_confluent_message(value: bytes) -> dict:
    if len(value) < 5 or value[0] != 0:
        raise ValueError("Invalid Confluent Avro payload")
    schema_id = int.from_bytes(value[1:5], byteorder="big", signed=False)
    parsed_schema = fetch_schema(schema_id)
    decoder = io.BinaryDecoder(BytesIO(value[5:]))
    reader = io.DatumReader(parsed_schema)
    payload = reader.read(decoder)
    return {"schema_id": schema_id, "payload": payload}


def main() -> None:
    consumer = KafkaConsumer(
        "enrollment.created",
        "course.published",
        bootstrap_servers=["localhost:9092"],
        group_id="smartcourse-local-consumer",
        auto_offset_reset="earliest",
        enable_auto_commit=True,
    )

    print("Listening to enrollment.created and course.published...")
    for message in consumer:
        decoded = decode_confluent_message(message.value)
        print(
            json.dumps(
                {
                    "topic": message.topic,
                    "key": message.key.decode("utf-8") if message.key else None,
                    "schema_id": decoded["schema_id"],
                    "payload": decoded["payload"],
                },
                indent=2,
            )
        )


if __name__ == "__main__":
    main()