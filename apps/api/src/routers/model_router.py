from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from src.core.dependencies import ModelServiceDep
from src.core.logger import get_logger
from src.schemas.model_schemas import ModelRead
from src.types.enums import APITag

router = APIRouter(prefix="/model", tags=[APITag.MODEL])
logger = get_logger(__name__)


### Read a model by id
@router.get("/", response_model=ModelRead)
async def get_model_by_id(id: Annotated[UUID, Query(...)], service: ModelServiceDep) -> ModelRead:
    """Get a model by id"""
    logger.info("Received model request via path parameter for id=%s", id)
    return await service.get(id)


