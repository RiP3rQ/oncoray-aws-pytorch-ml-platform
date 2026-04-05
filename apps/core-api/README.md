# Core API

This app is a small `uv` workspace that exposes our local PyTorch model through a FastAPI backend.

## Quick start

```powershell
cd D:\Pytorch-model\apps\core-api
uv sync
uv run --package core-api-service uvicorn core_api.main:app --reload
```

The service depends on the model package in `../pytorch-engine/model`, so both apps stay connected inside the monorepo.

## Endpoints

- `GET /health` confirms the API is up and the model is initialized.
- `POST /predict` returns a prediction for a single numeric input.

## Workspace layout

- `pyproject.toml` defines the local `uv` workspace.
- `api/` contains the FastAPI package and app entrypoint.
- `package.json` exposes monorepo-friendly scripts for Turbo users.
