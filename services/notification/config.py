from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_ENV: str = "development"
    SERVICE_NAME: str = "notification-service"
    RABBITMQ_URL: str = "amqp://guest:guest@localhost:5672/"
    REDIS_URL: str = "redis://localhost:6379/0"

    class Config:
        env_file = ".env"


settings = Settings()
