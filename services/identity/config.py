from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_ENV: str = "development"
    SERVICE_NAME: str = "identity-service"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    DATABASE_URL: str = "postgresql+asyncpg://identity_user:identity_pass@localhost:5436/identity_db"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://identity_user:identity_pass@localhost:5436/identity_db"
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REDIS_URL: str = "redis://localhost:6379/0"
    KAFKA_BROKERS: str = "localhost:9092"
    SCHEMA_REGISTRY_URL: str = "http://localhost:8081"

    class Config:
        env_file = ".env"


settings = Settings()
