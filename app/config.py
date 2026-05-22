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

    class Config:
        env_file = ".env"


# Single instance used throughout the app — import this everywhere you need config
settings = Settings()
