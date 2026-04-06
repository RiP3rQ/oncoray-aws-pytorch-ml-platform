from typing import Annotated
from fastapi import Depends
from src.services.model_service import ModelService


# Get model service
async def get_model_service() -> ModelService:
    """Get model service"""
    return ModelService()

# Model service dep annotation
ModelServiceDep = Annotated[
    ModelService,
    Depends(get_model_service),
]
