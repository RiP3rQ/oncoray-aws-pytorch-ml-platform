from __future__ import annotations

from contextlib import asynccontextmanager
import logging
import time
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import master_router
from app.config import app_settings
from app.core.logging import setup_logging
from app.database.session import get_session, ping_database


class ModelService:
    async def load(self) -> None:
        return None

    def is_ready(self) -> bool:
        return True


model_service = ModelService()


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging(app_settings.APP_LOG_LEVEL)
    await model_service.load()
    yield


app = FastAPI(
    title=app_settings.APP_NAME,
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(app_settings.CORS_ALLOWED_ORIGINS),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(master_router)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = uuid4().hex
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (time.perf_counter() - start) * 1000
        logging.getLogger("core_api.request").exception(
            "request failed request_id=%s method=%s path=%s duration_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            duration_ms,
        )
        raise

    duration_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Request-ID"] = request_id
    logging.getLogger("core_api.request").info(
        "request completed request_id=%s method=%s path=%s status_code=%s duration_ms=%.2f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "core-api", "status": "ok"}


@app.get("/livez")
async def livez() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/readyz")
async def readyz(session=Depends(get_session)):
    db_ready = await ping_database(session)
    model_ready = model_service.is_ready()
    payload = {
        "status": "ok" if db_ready and model_ready else "degraded",
        "model_ready": model_ready,
        "db_ready": db_ready,
    }
    if not (db_ready and model_ready):
        raise HTTPException(status_code=503, detail=payload)
    return payload


@app.get("/health")
async def health(session=Depends(get_session)):
    return await readyz(session)
