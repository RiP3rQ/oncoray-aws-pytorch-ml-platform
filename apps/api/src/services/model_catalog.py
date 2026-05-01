from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api_types.enums import ModelSlug
from src.core.errors import EntityNotFound
from src.core.logger import get_logger
from src.database.postgres import LLMModel
from src.schemas.model_schemas import ModelRead

logger = get_logger(__name__)


class ModelCatalog:
    """API-owned read model describing available Model Runtimes."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_models(self) -> list[ModelRead]:
        logger.info("Fetching Model Catalog from database")
        result = await self.session.execute(select(LLMModel).order_by(desc("created_at")))
        models = result.scalars().all()
        logger.info("Found %d Model Catalog items", len(models))
        return [self._to_model_read(model) for model in models]

    async def get_model(self, model_id: UUID) -> ModelRead:
        logger.info("Fetching Model Catalog item with id=%s from database", model_id)
        model = await self.session.get(LLMModel, model_id)
        if model is None:
            logger.warning("Model Catalog item not found for id=%s", model_id)
            raise EntityNotFound(f"Model '{model_id}' was not found.")
        logger.info("Returning Model Catalog item with id=%s", model_id)
        return self._to_model_read(model)

    def _to_model_read(self, model: LLMModel) -> ModelRead:
        return ModelRead(
            id=model.id,
            name=model.name,
            slug=ModelSlug(model.slug),
            description=model.description,
            version=model.version,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
