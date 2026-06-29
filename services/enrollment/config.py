from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_ENV: str = "development"
    SERVICE_NAME: str = "enrollment-service"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    REDIS_URL: str = "redis://localhost:6379/0"
    DATABASE_URL: str = "postgresql+asyncpg://enrollment_user:enrollment_pass@localhost:5438/enrollment_db"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://enrollment_user:enrollment_pass@localhost:5438/enrollment_db"
    KAFKA_BROKERS: str = "localhost:9092"
    SCHEMA_REGISTRY_URL: str = "http://localhost:8081"
    TEMPORAL_HOST: str = "localhost:7233"
    ENROLLMENT_TASK_QUEUE: str = "smartcourse-enrollment-service-queue"
    COURSE_SERVICE_URL: str = "http://localhost:8005"

    class Config:
        env_file = ".env"


settings = Settings()
