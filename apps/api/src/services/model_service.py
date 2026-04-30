from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.errors import EntityNotFound
from src.core.logger import get_logger
from src.database.postgres import LLMModel
from src.schemas.model_schemas import ModelRead
from src.services.base import BaseService

logger = get_logger(__name__)


class ModelService(BaseService):
    """
    Service for managing models.
    """

    def __init__(
        self,
        model: type[LLMModel],
        session: AsyncSession,
    ) -> None:
        super().__init__()
        self.model = model
        self.session = session

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def get_all(self) -> list[ModelRead]:
        """Return all models from the database."""
        logger.info("Fetching all models from database")
        result = await self.session.execute(select(LLMModel).order_by(desc(LLMModel.created_at)))
        models = result.scalars().all()
        logger.info("Found %d models", len(models))
        return [self._to_model_read(model) for model in models]

    async def get(self, id: UUID) -> ModelRead:
        """Get a model by id from the database."""
        logger.info("Fetching model with id=%s from database", id)
        model = await self.session.get(LLMModel, id)
        if model is None:
            logger.warning("Model not found for id=%s", id)
            raise EntityNotFound(f"Model '{id}' was not found.")
        logger.info("Returning model with id=%s", id)
        return self._to_model_read(model)

    def _to_model_read(self, model: LLMModel) -> ModelRead:
        return ModelRead(
            id=model.id,
            name=model.name,
            slug=model.slug,
            description=model.description,
            version=model.version,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def _get_model_or_raise(self, model_id: UUID) -> LLMModel:
        model = await self.session.get(LLMModel, model_id)
        if model is None:
            raise EntityNotFound(f"Model '{model_id}' was not found.")
        return model
