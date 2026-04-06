FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY pyproject.toml alembic.ini README.md ./
COPY app ./app
COPY alembic ./alembic

RUN uv sync

CMD ["uv", "run", "--package", "core-api-service", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
