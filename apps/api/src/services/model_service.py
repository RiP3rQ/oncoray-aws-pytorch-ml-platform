from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.errors import EntityNotFound
from src.core.logger import get_logger
from src.database.postgres import LLMModel
from src.schemas.model_schemas import ModelRead, PredictionResponse
from src.services.base import BaseService
from src.services.s3_service import S3Service

logger = get_logger(__name__)


class ModelService(BaseService):
    """
    Service for managing models.
    """

    def __init__(
            self,
            model: type[LLMModel],
            session: AsyncSession,
            s3_service: S3Service,
    ) -> None:
        super().__init__()
        self.model = model
        self.session = session
        self.s3_service = s3_service

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def get_all(self) -> list[ModelRead]:
        """Return all models from the database."""
        logger.info("Fetching all models from database")
        result = await self.session.execute(
            select(LLMModel).order_by(desc(LLMModel.created_at))
        )
        models = result.scalars().all()
        logger.info("Found %d models", len(models))
        return [
            ModelRead(
                id=m.id,
                name=m.name,
                description=m.description,
                version=m.version,
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
            for m in models
        ]

    async def get(self, id: UUID) -> ModelRead:
        """Get a model by id from the database."""
        logger.info("Fetching model with id=%s from database", id)
        model = await self.session.get(LLMModel, id)
        if model is None:
            logger.warning("Model not found for id=%s", id)
            raise EntityNotFound(f"Model '{id}' was not found.")
        logger.info("Returning model with id=%s", id)
        return ModelRead(
            id=model.id,
            name=model.name,
            description=model.description,
            version=model.version,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    # ------------------------------------------------------------------
    # Prediction (mocked)
    # ------------------------------------------------------------------

    async def predict_with_image(
        self,
        model_id: UUID,
        image_data: bytes,
        filename: str,
    ) -> PredictionResponse:
        """
        Run a mocked prediction.

        1. Validate the model exists.
        2. Upload the image to S3 (currently mocked).
        3. Return a hard-coded prediction response.
        """
        # 1. Validate model exists
        model = await self.session.get(LLMModel, model_id)
        if model is None:
            raise EntityNotFound(f"Model '{model_id}' was not found.")

        # 2. Upload image to S3 (mocked)
        s3_key = await self.s3_service.upload_image(image_data, filename)

        # 3. Return mocked prediction
        logger.info(
            "[MOCK] Prediction for model %s with image %s -> cat (confidence=0.95)",
            model_id,
            s3_key,
        )
        return PredictionResponse(
            model_id=model_id,
            prediction="cat",
            confidence=0.95,
            image_s3_key=s3_key,
        )
