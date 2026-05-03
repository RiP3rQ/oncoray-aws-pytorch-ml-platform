from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.api_types.enums import ModelSlug

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
APP_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = PROJECT_DIR / "src" / "templates"
DEFAULT_MODEL_RUNTIME_TIMEOUT = 30.0
DEFAULT_MAIL_USES_STARTTLS = True
DEFAULT_MAIL_USES_SSL_TLS = False
DEFAULT_MAIL_USES_CREDENTIALS = True
DEFAULT_MAIL_VALIDATES_CERTS = True

_base_config = SettingsConfigDict(
    env_file=PROJECT_DIR / ".env",
    env_ignore_empty=True,
    extra="ignore",
)


class AppSettings(BaseSettings):
    """General application settings."""

    APP_HTTP_PROTOCOL: str = "http"
    APP_NAME: str = "Core API"
    APP_ENVIRONMENT: str = "development"
    APP_LOG_LEVEL: str = "INFO"
    CORS_ALLOWED_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    AUTH_RATE_LIMIT_MAX_REQUESTS: int = 5
    AUTH_RATE_LIMIT_WINDOW_SECONDS: int = 60
    ACCESS_TOKEN_TTL_MINUTES: int = 15
    EMAIL_VERIFICATION_TOKEN_TTL_HOURS: int = 24
    APP_DOMAIN: str = "localhost:8000"
    SCALAR_DOCS_ENABLED: bool = True

    model_config = _base_config

    @field_validator("APP_LOG_LEVEL", mode="after")
    @classmethod
    def normalize_app_log_level(cls, value: str) -> str:
        return value.upper()

    @property
    def cors_allowed_origins_tuple(self) -> tuple[str, ...]:
        return tuple(origin.strip() for origin in self.CORS_ALLOWED_ORIGINS.split(",") if origin.strip())


class DatabaseSettings(BaseSettings):
    """PostgreSQL connection settings."""

    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: int = 5433
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: str = "12345678"
    POSTGRES_DB: str = "pytorch-model"
    CORE_API_DATABASE_URL: str | None = None

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


class SecuritySettings(BaseSettings):
    """JWT and related security settings."""

    SECRET_KEY: str = Field(
        default="change-me-before-production",
        validation_alias=AliasChoices("SECRET_KEY", "JWT_SECRET"),
    )
    ALGORITHM: str = Field(
        default="HS256",
        validation_alias=AliasChoices("ALGORITHM", "JWT_ALGORITHM"),
    )

    model_config = _base_config

    @property
    def JWT_SECRET(self) -> str:
        """Backward-compatible access for legacy JWT secret references."""

        return self.SECRET_KEY

    @property
    def JWT_ALGORITHM(self) -> str:
        """Backward-compatible access for legacy JWT algorithm references."""

        return self.ALGORITHM


class NotificationSettings(BaseSettings):
    """Email (FastMail) and Twilio settings."""

    MAIL_USERNAME: str = ""
    MAIL_PASSWORD: str = ""
    MAIL_FROM: str = "noreply@localhost"
    MAIL_PORT: int = 587
    MAIL_SERVER: str = "localhost"
    MAIL_FROM_NAME: str = "Core API"

    model_config = _base_config


def notification_connection_config() -> dict[str, Any]:
    return {
        **notification_settings.model_dump(),
        "MAIL_" + "STARTTLS": DEFAULT_MAIL_USES_STARTTLS,
        "MAIL_" + "SSL_TLS": DEFAULT_MAIL_USES_SSL_TLS,
        "USE_" + "CREDENTIALS": DEFAULT_MAIL_USES_CREDENTIALS,
        "VALIDATE_" + "CERTS": DEFAULT_MAIL_VALIDATES_CERTS,
        "TEMPLATE_FOLDER": TEMPLATE_DIR,
    }


class S3Settings(BaseSettings):
    """AWS S3 settings for image uploads."""

    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = "model-predictions"
    S3_UPLOAD_MODE: str = "mock"

    model_config = _base_config

    @field_validator("S3_UPLOAD_MODE", mode="before")
    @classmethod
    def normalize_upload_mode(cls, value: str) -> str:
        return value.strip().lower()


class ModelServiceSettings(BaseSettings):
    """Internal model-service connection settings."""

    MODEL_SERVICE_URL: str = "http://127.0.0.1:8001"

    model_config = _base_config

    @field_validator("MODEL_SERVICE_URL", mode="before")
    @classmethod
    def normalize_model_service_url(cls, value: str) -> str:
        if value is None:
            raise ValueError("MODEL_SERVICE_URL must not be empty.")

        normalized = value.strip().rstrip("/")
        if not normalized:
            raise ValueError("MODEL_SERVICE_URL must not be empty.")
        return normalized

    @property
    def model_service_urls(self) -> dict[ModelSlug, str]:
        return {slug: self.MODEL_SERVICE_URL for slug in ModelSlug}


class ObservabilitySettings(BaseSettings):
    """OpenTelemetry configuration."""

    OTEL_ENABLED: bool = True
    OTEL_SERVICE_NAME: str = "core-api"
    OTEL_EXPORTER_OTLP_ENDPOINT: str | None = None
    OTEL_EXCLUDED_URLS: str = "/livez,/readyz,/startupz,/health,/healthz"

    model_config = _base_config

    @field_validator("OTEL_EXPORTER_OTLP_ENDPOINT", mode="before")
    @classmethod
    def normalize_optional_endpoint(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().rstrip("/")
        return normalized or None


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
s3_settings = S3Settings()
model_service_settings = ModelServiceSettings()
observability_settings = ObservabilitySettings()


def validate_production_settings() -> None:
    """Fail fast when production starts with unsafe local/demo configuration."""
    if app_settings.APP_ENVIRONMENT != "production":
        return

    errors: list[str] = []
    localhost_values = ("localhost", "127.0.0.1", "0.0.0.0")

    if app_settings.APP_HTTP_PROTOCOL != "https":
        errors.append("APP_HTTP_PROTOCOL must be 'https' in production.")
    if any(host in app_settings.APP_DOMAIN for host in localhost_values):
        errors.append("APP_DOMAIN must not point at localhost in production.")
    if app_settings.SCALAR_DOCS_ENABLED:
        errors.append("SCALAR_DOCS_ENABLED must be false in production.")
    for origin in app_settings.cors_allowed_origins_tuple:
        if not origin.startswith("https://") or any(host in origin for host in localhost_values):
            errors.append("CORS_ALLOWED_ORIGINS must contain only HTTPS non-localhost origins in production.")
            break

    if security_settings.SECRET_KEY == "change-me-before-production" or len(security_settings.SECRET_KEY) < 32:
        errors.append("SECRET_KEY must be a real production secret with at least 32 characters.")
    if not db_settings.CORE_API_DATABASE_URL:
        errors.append("CORE_API_DATABASE_URL must be set in production.")
    if s3_settings.S3_UPLOAD_MODE != "aws":
        errors.append("S3_UPLOAD_MODE must be 'aws' in production.")
    if not s3_settings.S3_BUCKET_NAME or s3_settings.S3_BUCKET_NAME == "model-predictions":
        errors.append("S3_BUCKET_NAME must be set to the production prediction artifacts bucket.")

    if any(host in model_service_settings.MODEL_SERVICE_URL for host in localhost_values):
        errors.append("MODEL_SERVICE_URL must point at the internal Model Runtime Host service in production.")

    required_mail_values = {
        "MAIL_USERNAME": notification_settings.MAIL_USERNAME,
        "MAIL_PASSWORD": notification_settings.MAIL_PASSWORD,
        "MAIL_FROM": notification_settings.MAIL_FROM,
        "MAIL_SERVER": notification_settings.MAIL_SERVER,
    }
    for name, value in required_mail_values.items():
        if not value or "localhost" in value:
            errors.append(f"{name} must be set to a production mail value.")

    if errors:
        raise RuntimeError("Invalid production configuration: " + " ".join(errors))
