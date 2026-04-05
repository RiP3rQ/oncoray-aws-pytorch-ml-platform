from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PredictionRequest(BaseModel):
    value: float = Field(..., description="Numeric input passed into the trained model.")


class PredictionResponse(BaseModel):
    input_value: float
    prediction: float
    model_ready: bool = True


class LivenessResponse(BaseModel):
    status: Literal["ok"] = "ok"


class ReadinessResponse(BaseModel):
    status: Literal["ok", "degraded"]
    model_ready: bool
    db_ready: bool
