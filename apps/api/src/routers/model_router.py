from uuid import UUID

from fastapi import APIRouter
from src.core.dependencies import ModelServiceDep
from src.schemas.model_schemas import ModelRead
from src.types.enums import APITag

router = APIRouter(prefix="/model", tags=[APITag.MODEL])


### Read a model by id
@router.get("/{id}", response_model=ModelRead)
async def get_model_by_id(id: UUID, service: ModelServiceDep) -> ModelRead:
    """Get a model by id"""
    return await service.get(id)
