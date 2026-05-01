from pydantic import BaseModel, Field


class ModelRuntimePrediction(BaseModel):
    """Normalized prediction payload returned to API orchestration."""

    prediction: str = Field(examples=["NORMAL", "PNEUMONIA"])
    confidence: float = Field(ge=0.0, le=1.0)
