FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml alembic.ini README.md ./
COPY api ./api
COPY alembic ./alembic

RUN uv sync

CMD ["uv", "run", "--package", "core-api-service", "uvicorn", "core_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
