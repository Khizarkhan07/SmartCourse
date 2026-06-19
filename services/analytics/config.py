from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_ENV: str = "development"
    SERVICE_NAME: str = "analytics-service"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    DATABASE_URL: str = "postgresql+asyncpg://analytics_user:analytics_pass@localhost:5435/analytics_db"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://analytics_user:analytics_pass@localhost:5435/analytics_db"
    KAFKA_BROKERS: str = "localhost:9092"
    SCHEMA_REGISTRY_URL: str = "http://localhost:8081"

    class Config:
        env_file = ".env"


settings = Settings()
