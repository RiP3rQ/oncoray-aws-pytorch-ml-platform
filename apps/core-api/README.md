# Core API

This workspace contains a minimal FastAPI auth service focused on logging, JWT authentication, and Alembic-managed persistence.

## Quick start

```powershell
cd D:\Pytorch-model\apps\core-api
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
uv sync
uv run --package core-api-service alembic upgrade head
uv run --package core-api-service uvicorn core_api.main:app --reload
```

## Endpoints

- `GET /livez` confirms the process is running.
- `GET /readyz` checks runtime and database readiness.
- `GET /health` mirrors readiness for compatibility.
- `POST /auth/register` creates a new user account.
- `POST /auth/login` returns a signed JWT bearer token.
- `POST /auth/logout` invalidates the active JWT session server-side.

## Database and migrations

- SQLite is the default local database.
- Override the database with `CORE_API_DATABASE_URL`.
- Alembic revision files live in `alembic/versions`.

## Security notes

- Set a strong `CORE_API_JWT_SECRET` before production use.
- Passwords are stored with bcrypt hashes.
- Login attempts are rate limited with `CORE_API_AUTH_RATE_LIMIT_MAX_REQUESTS` and `CORE_API_AUTH_RATE_LIMIT_WINDOW_SECONDS`.

## Testing

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
uv run --package core-api-service pytest
```

## Workspace layout

- `pyproject.toml` defines the `uv` workspace.
- `api/` contains the Python package.
- `alembic/` contains migration configuration and revisions.
