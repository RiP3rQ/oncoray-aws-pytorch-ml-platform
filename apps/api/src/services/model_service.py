from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.errors import EntityNotFound, ServiceUnavailable
from src.core.logger import get_logger
from src.database.postgres import LLMModel
from src.schemas.model_schemas import ModelRead, PredictionResponse
from src.services.base import BaseService
from src.services.model_runtime_client import ModelRuntimeClient
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
        model_runtime_client: ModelRuntimeClient | None = None,
    ) -> None:
        super().__init__()
        self.model = model
        self.session = session
        self.s3_service = s3_service
        self.model_runtime_client = model_runtime_client

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    async def get_all(self) -> list[ModelRead]:
        """Return all models from the database."""
        logger.info("Fetching all models from database")
        result = await self.session.execute(select(LLMModel).order_by(desc(LLMModel.created_at)))
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
    # Prediction orchestration
    # ------------------------------------------------------------------

    async def predict_with_image(
        self,
        model_id: UUID,
        image_data: bytes,
        filename: str,
    ) -> PredictionResponse:
        """
        Run prediction through internal model-service.

        1. Validate model exists in metadata store.
        2. Forward image to internal model-service.
        3. Persist uploaded image metadata to S3.
        4. Return normalized prediction response.
        """
        model = await self.session.get(LLMModel, model_id)
        if model is None:
            raise EntityNotFound(f"Model '{model_id}' was not found.")

        if self.model_runtime_client is None:
            raise ServiceUnavailable("Model-service URL is not configured.")

        prediction = await self.model_runtime_client.predict(
            model_id=model_id,
            image_data=image_data,
            filename=filename,
        )

        s3_key = await self.s3_service.upload_image(image_data, filename)

        logger.info(
            "Prediction for model %s with image %s -> %s (confidence=%.4f)",
            model_id,
            s3_key,
            prediction.prediction,
            prediction.confidence,
        )
        return PredictionResponse(
            model_id=model_id,
            prediction=prediction.prediction,
            confidence=prediction.confidence,
            image_s3_key=s3_key,
        )
