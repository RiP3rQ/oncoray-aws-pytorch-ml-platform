# PyTorch Engine

This app is a small `uv` workspace for experimenting with our first PyTorch model inside the monorepo.

## Quick start

```powershell
cd D:\Pytorch-model\apps\pytorch-engine
uv sync
uv run --package first-model train-model
```

## Workspace layout

- `pyproject.toml` defines the `uv` workspace.
- `model/` contains the first trainable package and CLI entrypoint.
- `package.json` exposes monorepo-friendly scripts for Turbo users.

