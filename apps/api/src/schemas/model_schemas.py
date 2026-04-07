from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class BaseModelSchema(BaseModel):
    name: str = Field(max_length=100)
    description: str = Field(max_length=100)
    version: str = Field(
        description="Model version",
        examples=["v1", "v2", "v3"],
    )


class ModelRead(BaseModelSchema):
    id: UUID
    created_at: datetime
    updated_at: datetime


class PredictionResponse(BaseModel):
    """Response returned after a (mocked) image prediction."""

    model_id: UUID
    prediction: str = Field(
        description="Mocked prediction label.",
        examples=["cat", "dog"],
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Mocked confidence score between 0 and 1.",
    )
    image_s3_key: str = Field(
        description="S3 key where the uploaded image is stored.",
    )
