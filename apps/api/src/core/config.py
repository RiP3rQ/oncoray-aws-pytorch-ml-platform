from __future__ import annotations

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
APP_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = APP_DIR  / "templates"

_base_config = SettingsConfigDict(
    env_file=PROJECT_DIR / ".env",
    env_ignore_empty=True,
    extra="ignore",
)


class AppSettings(BaseSettings):
    """General application settings."""

    APP_NAME: str = "Core API"
    APP_ENVIRONMENT: str = "development"
    APP_LOG_LEVEL: str = "INFO"
    CORS_ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    AUTH_RATE_LIMIT_MAX_REQUESTS: int = 5
    AUTH_RATE_LIMIT_WINDOW_SECONDS: int = 60
    ACCESS_TOKEN_TTL_MINUTES: int = 15
    APP_DOMAIN: str = "localhost:8000"

    model_config = _base_config

    @field_validator("APP_LOG_LEVEL", mode="after")
    @classmethod
    def normalize_app_log_level(cls, value: str) -> str:
        return value.upper()

    @property
    def cors_allowed_origins_tuple(self) -> tuple[str, ...]:
        return tuple(
            origin.strip()
            for origin in self.CORS_ALLOWED_ORIGINS.split(",")
            if origin.strip()
        )


class DatabaseSettings(BaseSettings):
    """PostgreSQL and Redis connection settings."""

    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5433
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "12345678"
    POSTGRES_DB: str = "pytorch-model"
    CORE_API_DATABASE_URL: str | None = None

    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379

    model_config = _base_config

    @property
    def POSTGRES_URL(self) -> str:
        if self.CORE_API_DATABASE_URL:
            return normalize_database_url(self.CORE_API_DATABASE_URL)
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def SYNC_POSTGRES_URL(self) -> str:
        return to_sync_database_url(self.POSTGRES_URL)

    def REDIS_URL(self, db: int) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{db}"


class SecuritySettings(BaseSettings):
    """JWT and related security settings."""

    JWT_SECRET: str = "change-me-before-production"
    JWT_ALGORITHM: str = "HS256"

    model_config = _base_config


class NotificationSettings(BaseSettings):
    """Email (FastMail) and Twilio settings."""

    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = "noreply@localhost"
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "localhost"
    MAIL_FROM_NAME: str = "Core API"
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False
    USE_CREDENTIALS: bool = True
    VALIDATE_CERTS: bool = True

    model_config = _base_config


def normalize_database_url(url: str) -> str:
    """Ensure override URLs use the asyncpg driver when appropriate."""
    trimmed = url.strip()
    if trimmed.startswith("postgresql+asyncpg://"):
        return trimmed
    if trimmed.startswith("postgresql://"):
        return trimmed.replace("postgresql://", "postgresql+asyncpg://", 1)
    if trimmed.startswith("postgres://"):
        return trimmed.replace("postgres://", "postgresql+asyncpg://", 1)
    return trimmed


def to_sync_database_url(database_url: str) -> str:
    """Convert an asynchronous PostgreSQL URL to a synchronous PostgreSQL URL."""
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql://")
    return database_url


app_settings = AppSettings()
db_settings = DatabaseSettings()
security_settings = SecuritySettings()
notification_settings = NotificationSettings()
