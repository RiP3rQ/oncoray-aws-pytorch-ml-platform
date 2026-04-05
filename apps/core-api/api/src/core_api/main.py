from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from core_api.config import get_settings
from core_api.deps import DbSession
from core_api.routers.auth import router as auth_router
from core_api.schemas import LivenessResponse, PredictionRequest, PredictionResponse, ReadinessResponse
from core_api.service import model_service


@asynccontextmanager
async def lifespan(_: FastAPI):
    await model_service.load()
    yield


app = FastAPI(
    title="Core API",
    description=(
        "FastAPI service for exposing the local PyTorch model and a minimal "
        "email/password authentication workflow."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

settings = get_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=list(settings.cors_allowed_origins),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth_router)


@app.get(
    "/livez",
    response_model=LivenessResponse,
    summary="Check API liveness",
    description="Return a simple liveness response for the running API process.",
)
async def livez() -> LivenessResponse:
    return LivenessResponse()


async def _build_readiness_response(db: DbSession) -> JSONResponse:
    model_ready = model_service.is_ready()
    db_ready = False
    try:
        await db.execute(text("SELECT 1"))
        db_ready = True
    except Exception:
        db_ready = False

    payload = ReadinessResponse(
        status="ok" if model_ready and db_ready else "degraded",
        model_ready=model_ready,
        db_ready=db_ready,
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK if payload.status == "ok" else status.HTTP_503_SERVICE_UNAVAILABLE,
        content=payload.model_dump(),
    )


@app.get(
    "/readyz",
    response_model=ReadinessResponse,
    summary="Check API readiness",
    description="Return dependency-aware readiness information for the API process.",
)
async def readyz(db: DbSession) -> JSONResponse:
    return await _build_readiness_response(db)


@app.get(
    "/health",
    response_model=ReadinessResponse,
    summary="Check API health",
    description="Compatibility health endpoint that mirrors readiness state for callers expecting /health.",
)
async def healthcheck(db: DbSession) -> JSONResponse:
    return await _build_readiness_response(db)


@app.post(
    "/predict",
    response_model=PredictionResponse,
    summary="Generate a model prediction",
    description="Run the local PyTorch model against a single numeric input value.",
)
async def predict(payload: PredictionRequest) -> PredictionResponse:
    prediction = await model_service.predict(payload.value)
    return PredictionResponse(input_value=payload.value, prediction=prediction, model_ready=model_service.is_ready())
