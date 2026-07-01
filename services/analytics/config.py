from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_ENV: str = "development"
    SERVICE_NAME: str = "analytics-service"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    DATABASE_URL: str = "postgresql+asyncpg://analytics_user:analytics_pass@localhost:5435/analytics_db"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://analytics_user:analytics_pass@localhost:5435/analytics_db"
    KAFKA_BROKERS: str = "localhost:9092"
    SCHEMA_REGISTRY_URL: str = "http://localhost:8081"
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    REDIS_URL: str = "redis://localhost:6379/0"
    TEMPORAL_HOST: str = "localhost:7233"
    CONSUMER_MAX_RETRIES: int = 3
    CONSUMER_BASE_RETRY_DELAY_SECONDS: int = 2
    DLQ_RETRY_INTERVAL_SECONDS: int = 60
    DLQ_MAX_ATTEMPTS: int = 3

    class Config:
        env_file = ".env"


settings = Settings()
