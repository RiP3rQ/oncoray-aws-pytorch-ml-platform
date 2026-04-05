from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from core_api.schemas import PredictionRequest, PredictionResponse
from core_api.service import model_service


@asynccontextmanager
async def lifespan(_: FastAPI):
    model_service.load()
    yield


app = FastAPI(
    title="Core API",
    description="FastAPI service for exposing the local PyTorch model.",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def healthcheck() -> dict[str, str | bool]:
    return {"status": "ok", "model_ready": model_service.is_ready()}


@app.post("/predict", response_model=PredictionResponse)
async def predict(payload: PredictionRequest) -> PredictionResponse:
    prediction = model_service.predict(payload.value)
    return PredictionResponse(input_value=payload.value, prediction=prediction)
