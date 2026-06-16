from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str
    DATABASE_URL_SYNC: str

    # App
    APP_ENV: str = "development"
    SECRET_KEY: str
    CORS_ORIGINS: str = "http://localhost:3000"  # comma-separated list

    # JWT
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    ALGORITHM: str = "HS256"

    # Temporal
    TEMPORAL_HOST: str = "localhost:7233"

    # Kafka
    KAFKA_BROKERS: str = "localhost:9092"
    SCHEMA_REGISTRY_URL: str = "http://localhost:8081"

    PUSHGATEWAY_URL: str = "http://localhost:9091"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # Celery / RabbitMQ
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"

    class Config:
        env_file = ".env"


# Single instance used throughout the app — import this everywhere you need config
settings = Settings()
