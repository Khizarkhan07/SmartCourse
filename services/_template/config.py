from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_ENV: str = "development"
    SERVICE_NAME: str = "template-service"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"

    class Config:
        env_file = ".env"


settings = Settings()
