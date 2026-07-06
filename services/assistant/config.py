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

    class Config:
        env_file = ".env"


settings = Settings()
