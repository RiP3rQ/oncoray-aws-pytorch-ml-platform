from __future__ import annotations

import os
from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from core_api.config import DEFAULT_DATABASE_URL


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


def get_database_url() -> str:
    return os.getenv("CORE_API_DATABASE_URL", DEFAULT_DATABASE_URL)


def _connect_args(database_url: str) -> dict[str, bool]:
    if database_url.startswith("sqlite"):
        return {"check_same_thread": False}
    return {}


engine = create_engine(
    get_database_url(),
    connect_args=_connect_args(get_database_url()),
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def get_db_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
