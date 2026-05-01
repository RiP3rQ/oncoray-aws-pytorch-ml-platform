from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile, status

from src.config import Settings, settings
from src.model_runtime_factory import ModelRuntimeFactory
from src.runtime import InferenceRuntime
from src.schemas import ModelRuntimePrediction


def configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def create_app(
    runtime: InferenceRuntime | None = None,
    runtime_settings: Settings | None = None,
) -> FastAPI:
    resolved_settings = runtime_settings or settings
    configure_logging(resolved_settings.APP_LOG_LEVEL)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if runtime is None:
            app.state.runtime = ModelRuntimeFactory.from_settings(resolved_settings).build()
        yield

    app = FastAPI(
        title="Model Service",
        description="Internal PyTorch inference runtime.",
        version="0.1.0",
        lifespan=lifespan,
    )
    if runtime is not None:
        app.state.runtime = runtime

    @app.get("/")
    async def get_root() -> dict[str, str]:
        model_runtime = get_runtime(app)
        return {
            "service": resolved_settings.APP_NAME,
            "status": "ok",
            "model": model_runtime.slug.value,
        }

    @app.get("/livez")
    async def livez() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict[str, str]:
        model_runtime = get_runtime(app)
        return {"status": "ok", "model": model_runtime.slug.value}

    @app.get("/startupz")
    async def startupz() -> dict[str, str]:
        model_runtime = get_runtime(app)
        return {"status": "ok", "model": model_runtime.slug.value}

    @app.post("/predict", response_model=ModelRuntimePrediction)
    async def predict(
        image: Annotated[UploadFile, File(..., description="Image file (max 2 MB)")],
    ) -> ModelRuntimePrediction:
        try:
            return get_runtime(app).predict(await image.read())
        except HTTPException:
            raise
        except ValueError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Prediction failed.",
            ) from exc

    return app


def get_runtime(app: FastAPI | Request) -> InferenceRuntime:
    state: Any = app.state if isinstance(app, FastAPI) else app.app.state
    runtime = getattr(state, "runtime", None)
    if runtime is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Model runtime not ready.")
    return runtime


app = create_app()
