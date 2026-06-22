from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_ENV: str = "development"
    SERVICE_NAME: str = "identity-service"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"
    DATABASE_URL: str = "postgresql+asyncpg://identity_user:identity_pass@localhost:5436/identity_db"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://identity_user:identity_pass@localhost:5436/identity_db"

    class Config:
        env_file = ".env"


settings = Settings()
