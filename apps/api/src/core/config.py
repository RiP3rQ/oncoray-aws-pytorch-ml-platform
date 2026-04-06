from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import os
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_DIR / ".env"


def _load_env_file(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip("\"'")
    return values


def _get_setting(name: str, default: str) -> str:
    env_values = _load_env_file(ENV_FILE)
    return os.getenv(name, env_values.get(name, default))


def _normalize_database_url(value: str) -> str:
    return os.path.expandvars(value).replace("\\", "/")


def _parse_origins(value: str) -> tuple[str, ...]:
    return tuple(origin.strip() for origin in value.split(",") if origin.strip())


@dataclass(frozen=True)
class AppSettings:
    """
    General application settings
    """
    app_name: str
    app_environment: str
    app_log_level: str
    cors_allowed_origins: tuple[str, ...]
    auth_rate_limit_max_requests: int
    auth_rate_limit_window_seconds: int
    access_token_ttl_minutes: int


@dataclass(frozen=True)
class DatabaseSettings:
    """
    Database settings
    """
    postgres_server: str
    postgres_port: int
    postgres_user: str
    postgres_password: str
    postgres_db: str
    database_url_override: str | None

    @property
    def postgres_url(self) -> str:
        """
        Get the PostgreSQL URL
        """
        if self.database_url_override:
            return self.database_url_override
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_server}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def sync_postgres_url(self) -> str:
        """
        Get the synchronous PostgreSQL URL
        """
        return to_sync_database_url(self.postgres_url)

@dataclass(frozen=True)
class RedisSettings:
    """
    Redis settings
    """
    redis_host: str
    redis_port: int

    @property
    def redis_url(self, db: int) -> str:
        """
        Get the Redis URL
        """
        return f"redis://{self.redis_host}:{self.redis_port}/{db}"


@dataclass(frozen=True)
class SecuritySettings:
    """
    Security settings
    """
    jwt_secret: str
    jwt_algorithm: str


@lru_cache(maxsize=1)
def get_app_settings() -> AppSettings:
    """
    Get the application settings
    """
    return AppSettings(
        app_name=_get_setting("APP_NAME", "Core API"),
        app_environment=_get_setting("APP_ENVIRONMENT", "development"),
        app_log_level=_get_setting("APP_LOG_LEVEL", "INFO").upper(),
        cors_allowed_origins=_parse_origins(
            _get_setting("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000"),
        ),
        auth_rate_limit_max_requests=int(_get_setting("AUTH_RATE_LIMIT_MAX_REQUESTS", "5")),
        auth_rate_limit_window_seconds=int(_get_setting("AUTH_RATE_LIMIT_WINDOW_SECONDS", "60")),
        access_token_ttl_minutes=int(_get_setting("ACCESS_TOKEN_TTL_MINUTES", "15")),
    )


@lru_cache(maxsize=1)
def get_db_settings() -> DatabaseSettings:
    """
    Get the database settings
    """
    database_override = _get_setting("CORE_API_DATABASE_URL", "")
    return DatabaseSettings(
        postgres_server=_get_setting("POSTGRES_SERVER", "localhost"),
        postgres_port=int(_get_setting("POSTGRES_PORT", "5433")),
        postgres_user=_get_setting("POSTGRES_USER", "postgres"),
        postgres_password=_get_setting("POSTGRES_PASSWORD", "12345678"),
        postgres_db=_get_setting("POSTGRES_DB", "pytorch-model"),
        database_url_override=_normalize_database_url(database_override) if database_override else None,
    )

@lru_cache(maxsize=1)
def get_redis_settings() -> RedisSettings:
    """
    Get the Redis settings
    """
    return RedisSettings(
        redis_host=_get_setting("REDIS_HOST", "localhost"),
        redis_port=int(_get_setting("REDIS_PORT", "6379")),
    )


@lru_cache(maxsize=1)
def get_security_settings() -> SecuritySettings:
    """
    Get the security settings
    """
    return SecuritySettings(
        jwt_secret=_get_setting("JWT_SECRET", "change-me-before-production"),
        jwt_algorithm=_get_setting("JWT_ALGORITHM", "HS256"),
    )


def clear_settings_cache() -> None:
    """
    Clear the settings cache
    """
    get_app_settings.cache_clear()
    get_db_settings.cache_clear()
    get_security_settings.cache_clear()


def to_sync_database_url(database_url: str) -> str:
    """
    Convert an asynchronous PostgreSQL URL to a synchronous PostgreSQL URL
    """
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql://")
    return database_url


app_settings = get_app_settings()
db_settings = get_db_settings()
security_settings = get_security_settings()
redis_settings = get_redis_settings()
