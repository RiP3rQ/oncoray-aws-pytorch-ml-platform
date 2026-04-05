from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from core_api.config import clear_settings_cache, make_async_database_url


@pytest.mark.asyncio
async def test_alembic_upgrade_head_creates_hardened_auth_schema(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "migration-test.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("CORE_API_DATABASE_URL", database_url)
    clear_settings_cache()

    alembic_config = Config("alembic.ini")
    command.upgrade(alembic_config, "head")

    engine = create_async_engine(make_async_database_url(database_url))
    async with engine.begin() as connection:
        def inspect_schema(sync_connection):
            inspector = inspect(sync_connection)
            session_columns = {column["name"] for column in inspector.get_columns("session_tokens")}
            user_columns = {column["name"] for column in inspector.get_columns("users")}
            return session_columns, user_columns

        session_columns, user_columns = await connection.run_sync(inspect_schema)

    await engine.dispose()
    assert {"id", "user_id", "jti_hash", "created_at", "expires_at"} <= session_columns
    assert "token" not in session_columns
    assert "password_hash" in user_columns
