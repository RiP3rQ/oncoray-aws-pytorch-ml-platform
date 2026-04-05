from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from core_api.config import get_settings


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


def get_database_url() -> str:
    return get_settings().database_url


def get_async_database_url() -> str:
    return get_settings().async_database_url


def _connect_args(database_url: str) -> dict[str, bool]:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


def _build_engine() -> AsyncEngine:
    settings = get_settings()
    engine_kwargs: dict[str, object] = {
        "connect_args": _connect_args(settings.async_database_url),
    }
    if not settings.is_sqlite:
        engine_kwargs.update(
            pool_pre_ping=True,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
        )

    return create_async_engine(settings.async_database_url, **engine_kwargs)


engine: AsyncEngine = _build_engine()

SessionLocal = async_sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
