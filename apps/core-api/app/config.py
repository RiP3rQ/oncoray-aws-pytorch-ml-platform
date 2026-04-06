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
    APP_NAME: str
    APP_ENVIRONMENT: str
    APP_LOG_LEVEL: str
    CORS_ALLOWED_ORIGINS: tuple[str, ...]
    AUTH_RATE_LIMIT_MAX_REQUESTS: int
    AUTH_RATE_LIMIT_WINDOW_SECONDS: int
    ACCESS_TOKEN_TTL_MINUTES: int


@dataclass(frozen=True)
class DatabaseSettings:
    POSTGRES_SERVER: str
    POSTGRES_PORT: int
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_DB: str
    DATABASE_URL_OVERRIDE: str | None

    @property
    def POSTGRES_URL(self) -> str:
        if self.DATABASE_URL_OVERRIDE:
            return self.DATABASE_URL_OVERRIDE
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def SYNC_POSTGRES_URL(self) -> str:
        return to_sync_database_url(self.POSTGRES_URL)

@dataclass(frozen=True)
class RedisSettings:
    REDIS_HOST: str
    REDIS_PORT: int

    @property
    def REDIS_URL(self, db: int) -> str:
        return f"redis://{self.REDIS_HOST}:{self.REDIS_PORT}/{db}"


@dataclass(frozen=True)
class SecuritySettings:
    JWT_SECRET: str
    JWT_ALGORITHM: str


@lru_cache(maxsize=1)
def get_app_settings() -> AppSettings:
    return AppSettings(
        APP_NAME=_get_setting("APP_NAME", "Core API"),
        APP_ENVIRONMENT=_get_setting("APP_ENVIRONMENT", "development"),
        APP_LOG_LEVEL=_get_setting("APP_LOG_LEVEL", "INFO").upper(),
        CORS_ALLOWED_ORIGINS=_parse_origins(
            _get_setting("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:3000"),
        ),
        AUTH_RATE_LIMIT_MAX_REQUESTS=int(_get_setting("AUTH_RATE_LIMIT_MAX_REQUESTS", "5")),
        AUTH_RATE_LIMIT_WINDOW_SECONDS=int(_get_setting("AUTH_RATE_LIMIT_WINDOW_SECONDS", "60")),
        ACCESS_TOKEN_TTL_MINUTES=int(_get_setting("ACCESS_TOKEN_TTL_MINUTES", "15")),
    )


@lru_cache(maxsize=1)
def get_db_settings() -> DatabaseSettings:
    database_override = _get_setting("CORE_API_DATABASE_URL", "")
    return DatabaseSettings(
        POSTGRES_SERVER=_get_setting("POSTGRES_SERVER", "localhost"),
        POSTGRES_PORT=int(_get_setting("POSTGRES_PORT", "5433")),
        POSTGRES_USER=_get_setting("POSTGRES_USER", "postgres"),
        POSTGRES_PASSWORD=_get_setting("POSTGRES_PASSWORD", "12345678"),
        POSTGRES_DB=_get_setting("POSTGRES_DB", "pytorch-model"),
        DATABASE_URL_OVERRIDE=_normalize_database_url(database_override) if database_override else None,
    )

@lru_cache(maxsize=1)
def get_redis_settings() -> RedisSettings:
    return RedisSettings(
        REDIS_HOST=_get_setting("REDIS_HOST", "localhost"),
        REDIS_PORT=int(_get_setting("REDIS_PORT", "6379")),
    )


@lru_cache(maxsize=1)
def get_security_settings() -> SecuritySettings:
    return SecuritySettings(
        JWT_SECRET=_get_setting("JWT_SECRET", "change-me-before-production"),
        JWT_ALGORITHM=_get_setting("JWT_ALGORITHM", "HS256"),
    )


def clear_settings_cache() -> None:
    get_app_settings.cache_clear()
    get_db_settings.cache_clear()
    get_security_settings.cache_clear()


def to_sync_database_url(database_url: str) -> str:
    if database_url.startswith("sqlite+aiosqlite:///"):
        return database_url.replace("sqlite+aiosqlite:///", "sqlite:///")
    if database_url.startswith("postgresql+asyncpg://"):
        return database_url.replace("postgresql+asyncpg://", "postgresql://")
    return database_url


app_settings = get_app_settings()
db_settings = get_db_settings()
security_settings = get_security_settings()
redis_settings = get_redis_settings()
