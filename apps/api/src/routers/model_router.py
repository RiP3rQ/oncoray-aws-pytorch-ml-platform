import asyncio
import random
from uuid import UUID

from fastapi import APIRouter
from src.types.enums import APITag
from src.schemas.model_schemas import ModelRead
from src.core.dependencies import ModelServiceDep

router = APIRouter(prefix="/model", tags=[APITag.MODEL])


### Read a model by id
@router.get("/", response_model=ModelRead)
async def get_model_by_id(id: UUID, service: ModelServiceDep) -> dict[str, str | int]:
    """Get a model by id"""
    # Simluate delay
    await asyncio.sleep(random.randint(1, 3))
    # Check for model with given id
    return await service.get(id)