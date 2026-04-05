# Core API

This app is a small `uv` workspace that exposes our local PyTorch model through a FastAPI backend.

## Quick start

```powershell
cd D:\Pytorch-model\apps\core-api
uv sync
uv run --package core-api-service uvicorn core_api.main:app --reload
uv run --package core-api-service alembic upgrade head
```

The service depends on the model package in `../pytorch-engine/model`, so both apps stay connected inside the monorepo.

## Endpoints

- `GET /health` confirms the API is up and the model is initialized.
- `POST /predict` returns a prediction for a single numeric input.
- `POST /auth/register` creates a user with email and password.
- `POST /auth/login` validates credentials and returns a bearer token.
- `POST /auth/logout` invalidates the current bearer token.

## Database and migrations

- SQLite is used as the default local database.
- Alembic migration files live in `alembic/versions`.
- Override the database location with `CORE_API_DATABASE_URL` when needed.

## Testing

```powershell
uv run --package core-api-service pytest
```

## Workspace layout

- `pyproject.toml` defines the local `uv` workspace.
- `api/` contains the FastAPI package and app entrypoint.
- `package.json` exposes monorepo-friendly scripts for Turbo users.
