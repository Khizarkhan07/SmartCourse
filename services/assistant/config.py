from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_ENV: str = "development"
    SERVICE_NAME: str = "assistant-service"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    REDIS_URL: str = "redis://localhost:6379/0"
    DATABASE_URL: str = (
        "postgresql+asyncpg://assistant_user:assistant_pass@localhost:5439/assistant_db"
    )
    DATABASE_URL_SYNC: str = (
        "postgresql+psycopg2://assistant_user:assistant_pass@localhost:5439/assistant_db"
    )
    KAFKA_BROKERS: str = "localhost:9092"
    SCHEMA_REGISTRY_URL: str = "http://localhost:8081"

    # Embeddings — self-hosted all-MiniLM-L6-v2 via fastembed (ONNX, no torch).
    # EMBEDDING_DIM here must equal the chunks.embedding column dimension.
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    EMBEDDING_DIM: int = 384
    EMBEDDING_CACHE_DIR: str = "/app/.fastembed_cache"

    # Chunking — sizes are in TOKENS, counted with the model's real tokenizer.
    # Target stays under the model's 256-token hard cap (the model adds 2 special
    # tokens at embed time, so 200 content tokens -> 202, safely under 256).
    CHUNK_TARGET_TOKENS: int = 200
    CHUNK_MAX_TOKENS: int = 256
    CHUNK_OVERLAP_TOKENS: int = 30

    class Config:
        env_file = ".env"


settings = Settings()
