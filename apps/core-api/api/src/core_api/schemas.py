from __future__ import annotations

from pydantic import BaseModel, Field


class PredictionRequest(BaseModel):
    value: float = Field(..., description="Numeric input passed into the trained model.")


class PredictionResponse(BaseModel):
    input_value: float
    prediction: float
    model_ready: bool = True
