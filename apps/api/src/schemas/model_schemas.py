from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class BaseModelSchema(BaseModel):
    name: str = Field(max_length=100)
    description: str = Field(max_length=100)
    version: int = Field(
        description="Model version",
        examples=['v1', 'v2', 'v3'],
    )

class ModelRead(BaseModelSchema):
    id: UUID
    created_at: datetime
    updated_at: datetime