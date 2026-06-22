from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_ENV: str = "development"
    SERVICE_NAME: str = "certificate-service"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    DATABASE_URL: str = "postgresql+asyncpg://cert_user:cert_pass@localhost:5434/certificate_db"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://cert_user:cert_pass@localhost:5434/certificate_db"
    KAFKA_BROKERS: str = "localhost:9092"
    SCHEMA_REGISTRY_URL: str = "http://localhost:8081"
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    REDIS_URL: str = "redis://localhost:6379/0"

    class Config:
        env_file = ".env"


settings = Settings()
