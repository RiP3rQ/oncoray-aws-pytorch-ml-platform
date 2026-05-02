from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any, cast

from fastapi import FastAPI, File, HTTPException, Query, Request, UploadFile, status
from starlette.concurrency import run_in_threadpool

from src.config import Settings, settings, validate_production_settings
from src.model_runtime_factory import ModelRuntimeFactory
from src.runtime import ModelRuntime
from src.schemas import ModelRuntimePrediction
from src.types import ModelSlug


def configure_logging(log_level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, log_level, logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def create_app(
    runtime: ModelRuntime | None = None,
    runtimes: dict[ModelSlug, ModelRuntime] | None = None,
    runtime_settings: Settings | None = None,
) -> FastAPI:
    resolved_settings = runtime_settings or settings
    validate_production_settings(resolved_settings)
    configure_logging(resolved_settings.APP_LOG_LEVEL)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if runtime is None and runtimes is None:
            app.state.runtimes = {
                slug: ModelRuntimeFactory.from_settings_for_slug(resolved_settings, slug).build()
                for slug in resolved_settings.model_slugs
            }
        yield

    app = FastAPI(
        title="Model Service",
        description="Internal PyTorch inference runtime.",
        version="0.1.0",
        lifespan=lifespan,
    )
    if runtime is not None:
        app.state.runtimes = {runtime.slug: runtime}
    if runtimes is not None:
        app.state.runtimes = runtimes

    @app.get("/")
    async def get_root() -> dict[str, str | list[str]]:
        return {
            "service": resolved_settings.APP_NAME,
            **runtime_status(get_runtimes(app)),
        }

    @app.get("/livez")
    async def livez() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    async def readyz() -> dict[str, str | list[str]]:
        return runtime_status(get_runtimes(app))

    @app.get("/startupz")
    async def startupz() -> dict[str, str | list[str]]:
        return runtime_status(get_runtimes(app))

    @app.post("/predict", response_model=ModelRuntimePrediction)
    async def predict(
        image: Annotated[UploadFile, File(..., description="Image file (max 2 MB)")],
        model: Annotated[ModelSlug | None, Query(description="Model Runtime slug to use.")] = None,
    ) -> ModelRuntimePrediction:
        try:
            runtime = get_runtime(app, model)
            return await run_in_threadpool(runtime.predict, await image.read())
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


def get_runtimes(app: FastAPI | Request) -> dict[ModelSlug, ModelRuntime]:
    state: Any = app.state if isinstance(app, FastAPI) else app.app.state
    runtimes = getattr(state, "runtimes", None)
    if not isinstance(runtimes, dict) or not runtimes:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Model runtime not ready.")
    return cast(dict[ModelSlug, ModelRuntime], runtimes)


def get_runtime(app: FastAPI | Request, slug: ModelSlug | None = None) -> ModelRuntime:
    runtimes = get_runtimes(app)
    if slug is None:
        if len(runtimes) == 1:
            return next(iter(runtimes.values()))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Model Runtime slug is required when multiple runtimes are loaded.",
        )

    runtime = runtimes.get(slug)
    if runtime is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Model Runtime '{slug}' is not loaded.")
    return runtime


def runtime_status(runtimes: dict[ModelSlug, ModelRuntime]) -> dict[str, str | list[str]]:
    models = [slug.value for slug in sorted(runtimes, key=lambda item: item.value)]
    if len(models) == 1:
        return {"status": "ok", "model": models[0], "models": models}
    return {"status": "ok", "models": models}


app = create_app()
