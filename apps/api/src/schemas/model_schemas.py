from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from src.api_types.enums import ModelSlug, PredictionMode


class BaseModelSchema(BaseModel):
    name: str = Field(max_length=100)
    slug: ModelSlug = Field(max_length=50)
    description: str = Field(max_length=100)
    version: str = Field(
        description="Model version",
        examples=["v1", "v2", "v3"],
    )


class ModelRead(BaseModelSchema):
    id: UUID
    created_at: datetime
    updated_at: datetime


class ModelRuntimePrediction(BaseModel):
    """Normalized prediction payload returned by model-service."""

    prediction: str = Field(
        description="Predicted label returned by model-service.",
        examples=["cat", "dog"],
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score between 0 and 1.",
    )


class PredictionUploadStatus(BaseModel):
    """Best-effort image upload status."""

    status: Literal["ok", "error"]
    image_s3_key: str | None = None


class PredictionResultStatus(BaseModel):
    """Per-model prediction status."""

    status: Literal["ok", "error"]
    prediction: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    error: str | None = None


class UnifiedPredictionResponse(BaseModel):
    """Public prediction envelope for single-model and compare mode."""

    request_id: UUID
    mode: PredictionMode
    upload: PredictionUploadStatus
    results: dict[ModelSlug, PredictionResultStatus]
