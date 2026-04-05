from __future__ import annotations

from pathlib import Path

from alembic import command
from alembic.config import Config
import pytest
from sqlalchemy import create_engine
from sqlalchemy import inspect

from core_api.config import clear_settings_cache


def test_alembic_upgrade_head_creates_hardened_auth_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_path = (Path.cwd() / "migration-test.db").resolve()
    if database_path.exists():
        database_path.unlink()

    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("CORE_API_DATABASE_URL", database_url)
    clear_settings_cache()

    alembic_config = Config("alembic.ini")
    command.upgrade(alembic_config, "head")

    engine = create_engine(database_url)
    with engine.begin() as connection:
        inspector = inspect(connection)
        session_columns = {column["name"] for column in inspector.get_columns("session_tokens")}
        user_columns = {column["name"] for column in inspector.get_columns("users")}

    engine.dispose()
    assert {"id", "user_id", "jti_hash", "created_at", "expires_at"} <= session_columns
    assert "token" not in session_columns
    assert "password_hash" in user_columns
    database_path.unlink(missing_ok=True)
