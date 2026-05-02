from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.api_types.enums import ModelSlug

PROJECT_DIR = Path(__file__).resolve().parent.parent.parent
APP_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = PROJECT_DIR / "src" / "templates"

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
    APP_DOMAIN: str = "localhost:8000"

    model_config = _base_config

    @field_validator("APP_LOG_LEVEL", mode="after")
    @classmethod
    def normalize_app_log_level(cls, value: str) -> str:
        return value.upper()

    @property
    def cors_allowed_origins_tuple(self) -> tuple[str, ...]:
        return tuple(origin.strip() for origin in self.CORS_ALLOWED_ORIGINS.split(",") if origin.strip())


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
    REDIS_SSL: bool = False

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
        scheme = "rediss" if self.REDIS_SSL else "redis"
        return f"{scheme}://{self.REDIS_HOST}:{self.REDIS_PORT}/{db}"


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
    MAIL_STARTTLS: bool = True
    MAIL_SSL_TLS: bool = False
    USE_CREDENTIALS: bool = True
    VALIDATE_CERTS: bool = True

    model_config = _base_config


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

    MODEL_RUNTIME_URLS: str | None = None
    MODEL_SERVICE_URL: str | None = None
    MODEL_SERVICE_EFFNETB0_URL: str | None = None
    MODEL_SERVICE_VITB16_URL: str | None = None
    MODEL_SERVICE_TIMEOUT_SECONDS: float = 30.0

    model_config = _base_config

    @field_validator(
        "MODEL_RUNTIME_URLS",
        "MODEL_SERVICE_URL",
        "MODEL_SERVICE_EFFNETB0_URL",
        "MODEL_SERVICE_VITB16_URL",
        mode="before",
    )
    @classmethod
    def normalize_model_service_url(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip().rstrip("/")
        return normalized or None

    @property
    def model_service_urls(self) -> dict[ModelSlug, str]:
        urls = parse_model_runtime_urls(self.MODEL_RUNTIME_URLS)
        if self.MODEL_SERVICE_URL:
            urls[ModelSlug.EFFNETB0] = self.MODEL_SERVICE_URL
        if self.MODEL_SERVICE_EFFNETB0_URL:
            urls[ModelSlug.EFFNETB0] = self.MODEL_SERVICE_EFFNETB0_URL
        if self.MODEL_SERVICE_VITB16_URL:
            urls[ModelSlug.VITB16] = self.MODEL_SERVICE_VITB16_URL
        return urls


class WorkerSettings(BaseSettings):
    """Celery worker and broker settings."""

    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None
    CELERY_QUEUE_NAME: str | None = None
    CELERY_VISIBILITY_TIMEOUT_SECONDS: int = 1800
    CELERY_WAIT_TIME_SECONDS: int = 10
    CELERY_POLLING_INTERVAL_SECONDS: float = 1.0
    AWS_REGION: str = "us-east-1"
    SQS_QUEUE_URL: str | None = None

    model_config = _base_config

    @field_validator(
        "CELERY_BROKER_URL",
        "CELERY_RESULT_BACKEND",
        "CELERY_QUEUE_NAME",
        "SQS_QUEUE_URL",
        mode="before",
    )
    @classmethod
    def normalize_optional_strings(cls, value: str | None) -> str | None:
        if value is None:
            return None

        normalized = value.strip()
        return normalized or None

    @property
    def resolved_broker_url(self) -> str:
        if self.CELERY_BROKER_URL:
            return self.CELERY_BROKER_URL
        if self.SQS_QUEUE_URL:
            return "sqs://"
        return db_settings.REDIS_URL(9)

    @property
    def uses_sqs(self) -> bool:
        return self.resolved_broker_url.startswith("sqs://")

    @property
    def should_dispatch_via_worker(self) -> bool:
        return self.uses_sqs or self.CELERY_BROKER_URL is not None

    @property
    def resolved_queue_name(self) -> str:
        if self.CELERY_QUEUE_NAME:
            return self.CELERY_QUEUE_NAME
        if self.SQS_QUEUE_URL:
            return extract_queue_name_from_url(self.SQS_QUEUE_URL)
        return "celery"


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


def extract_queue_name_from_url(queue_url: str) -> str:
    """Return queue name from a full SQS queue URL."""
    parsed = urlparse(queue_url)
    queue_name = parsed.path.strip("/").split("/")[-1]
    if not queue_name:
        raise ValueError(f"Could not extract queue name from URL: {queue_url!r}")
    return queue_name


def parse_model_runtime_urls(value: str | None) -> dict[ModelSlug, str]:
    if value is None:
        return {}

    urls: dict[ModelSlug, str] = {}
    for entry in value.split(","):
        parsed_entry = entry.strip()
        if not parsed_entry:
            continue
        if "=" not in parsed_entry:
            raise ValueError(f"Invalid MODEL_RUNTIME_URLS entry: {parsed_entry!r}")

        slug_value, url_value = (part.strip() for part in parsed_entry.split("=", 1))
        if not slug_value or not url_value:
            raise ValueError(f"Invalid MODEL_RUNTIME_URLS entry: {parsed_entry!r}")

        try:
            slug = ModelSlug(slug_value)
        except ValueError as exc:
            raise ValueError(f"Unsupported Model Runtime slug in MODEL_RUNTIME_URLS: {slug_value!r}") from exc

        urls[slug] = url_value.rstrip("/")

    return urls


app_settings = AppSettings()
db_settings = DatabaseSettings()
security_settings = SecuritySettings()
notification_settings = NotificationSettings()
s3_settings = S3Settings()
model_service_settings = ModelServiceSettings()
worker_settings = WorkerSettings()
