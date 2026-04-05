from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from core_api.routers.auth import router as auth_router
from core_api.schemas import PredictionRequest, PredictionResponse
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

app.include_router(auth_router)


@app.get(
    "/health",
    summary="Check API health",
    description="Return a simple readiness response for the API process and model bootstrap state.",
)
async def healthcheck() -> dict[str, str | bool]:
    return {"status": "ok", "model_ready": model_service.is_ready()}


@app.post(
    "/predict",
    response_model=PredictionResponse,
    summary="Generate a model prediction",
    description="Run the local PyTorch model against a single numeric input value.",
)
async def predict(payload: PredictionRequest) -> PredictionResponse:
    prediction = await model_service.predict(payload.value)
    return PredictionResponse(input_value=payload.value, prediction=prediction)
