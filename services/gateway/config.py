from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_ENV: str = "development"
    SERVICE_NAME: str = "gateway"
    OTEL_EXPORTER_OTLP_ENDPOINT: str = "http://localhost:4317"

    # Backend service URLs (Docker internal network)
    MONOLITH_URL: str = "http://host.docker.internal:8000"
    TEMPLATE_URL: str = "http://smartcourse_template:8000"
    CERTIFICATE_URL: str = "http://smartcourse_certificate:8000"
    ANALYTICS_URL: str = "http://smartcourse_analytics:8000"
    IDENTITY_URL: str = "http://smartcourse_identity:8000"
    COURSE_URL: str = "http://smartcourse_course:8000"

    class Config:
        env_file = ".env"


settings = Settings()

# Route table: first path segment → backend base URL
# Add a new entry here each time a service is extracted from the monolith.
ROUTE_TABLE: dict[str, str] = {
    "certificates": settings.CERTIFICATE_URL,
    "analytics": settings.ANALYTICS_URL,
    "identity": settings.IDENTITY_URL,
    "auth": settings.IDENTITY_URL,
    "users": settings.IDENTITY_URL,
    "courses": settings.COURSE_URL,
    "modules": settings.COURSE_URL,
    "lessons": settings.COURSE_URL,
    # "publishing" routes to course-service once Chunk 18 moves workflows there
}
