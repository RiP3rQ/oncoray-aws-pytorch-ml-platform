from __future__ import annotations

import os
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from core_api.config import DEFAULT_DATABASE_URL, make_async_database_url


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


def get_database_url() -> str:
    return os.getenv("CORE_API_DATABASE_URL", DEFAULT_DATABASE_URL)


def get_async_database_url() -> str:
    return make_async_database_url(get_database_url())


def _connect_args(database_url: str) -> dict[str, bool]:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


engine: AsyncEngine = create_async_engine(
    get_async_database_url(),
    connect_args=_connect_args(get_async_database_url()),
)

SessionLocal = async_sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
