from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SQLITE_PATH = PROJECT_ROOT / "core_api.db"
DEFAULT_DATABASE_URL = f"sqlite:///{DEFAULT_SQLITE_PATH.as_posix()}"
DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:4321",
    "http://127.0.0.1:4321",
)


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    app_env: Literal["local", "development", "test", "production"] = "local"
    database_url: str = DEFAULT_DATABASE_URL
    jwt_secret: SecretStr
    jwt_algorithm: Literal["HS256"] = "HS256"
    jwt_issuer: str = "core-api"
    jwt_audience: str = "core-api-clients"
    jwt_access_token_ttl_minutes: int = 15
    jwt_clock_skew_seconds: int = 5
    cors_allowed_origins: tuple[str, ...] = Field(default_factory=lambda: DEFAULT_CORS_ORIGINS)
    auth_rate_limit_max_requests: int = 5
    auth_rate_limit_window_seconds: int = 60
    database_pool_size: int = 5
    database_max_overflow: int = 10

    @property
    def async_database_url(self) -> str:
        return make_async_database_url(self.database_url)

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


def make_async_database_url(database_url: str) -> str:
    if database_url.startswith("sqlite:///") and not database_url.startswith("sqlite+aiosqlite:///"):
        return database_url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    if database_url.startswith("postgresql://") and "+asyncpg" not in database_url:
        return database_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if database_url.startswith("mysql://") and "+" not in database_url.split("://", 1)[0]:
        return database_url.replace("mysql://", "mysql+aiomysql://", 1)
    return database_url


def _parse_csv_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default

    parsed = tuple(item.strip() for item in raw_value.split(",") if item.strip())
    return parsed or default


def _load_jwt_secret(app_env: str) -> SecretStr:
    configured_secret = os.getenv("CORE_API_JWT_SECRET")
    if configured_secret:
        return SecretStr(configured_secret)

    if app_env in {"local", "development", "test"}:
        return SecretStr("change-me-before-production")

    raise RuntimeError("CORE_API_JWT_SECRET must be set when CORE_API_ENV=production.")


@lru_cache
def get_settings() -> Settings:
    app_env = os.getenv("CORE_API_ENV", "local")
    return Settings(
        app_env=app_env,
        database_url=os.getenv("CORE_API_DATABASE_URL", DEFAULT_DATABASE_URL),
        jwt_secret=_load_jwt_secret(app_env),
        jwt_issuer=os.getenv("CORE_API_JWT_ISSUER", "core-api"),
        jwt_audience=os.getenv("CORE_API_JWT_AUDIENCE", "core-api-clients"),
        jwt_access_token_ttl_minutes=int(os.getenv("CORE_API_JWT_ACCESS_TOKEN_TTL_MINUTES", "15")),
        jwt_clock_skew_seconds=int(os.getenv("CORE_API_JWT_CLOCK_SKEW_SECONDS", "5")),
        cors_allowed_origins=_parse_csv_env("CORE_API_CORS_ALLOWED_ORIGINS", DEFAULT_CORS_ORIGINS),
        auth_rate_limit_max_requests=int(os.getenv("CORE_API_AUTH_RATE_LIMIT_MAX_REQUESTS", "5")),
        auth_rate_limit_window_seconds=int(os.getenv("CORE_API_AUTH_RATE_LIMIT_WINDOW_SECONDS", "60")),
        database_pool_size=int(os.getenv("CORE_API_DATABASE_POOL_SIZE", "5")),
        database_max_overflow=int(os.getenv("CORE_API_DATABASE_MAX_OVERFLOW", "10")),
    )


def clear_settings_cache() -> None:
    get_settings.cache_clear()
