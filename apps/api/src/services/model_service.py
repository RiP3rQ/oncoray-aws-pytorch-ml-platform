from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.errors import EntityNotFound, ServiceUnavailable
from src.core.logger import get_logger
from src.database.postgres import LLMModel
from src.intake.chest_xray_upload import ChestXrayUpload
from src.schemas.model_schemas import (
    ModelRead,
    PredictionResponse,
    PredictionUploadStatus,
    UnifiedPredictionResponse,
)
from src.services.base import BaseService
from src.services.model_runtime_client import ModelRuntimeClient
from src.services.prediction_orchestration import PredictionOrchestration
from src.services.s3_service import S3Service
from src.types.enums import ModelSlug, PredictionMode

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
        model_runtime_clients: dict[ModelSlug, ModelRuntimeClient] | None = None,
    ) -> None:
        super().__init__()
        self.model = model
        self.session = session
        self.s3_service = s3_service
        self.model_runtime_clients = model_runtime_clients or {}

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

    # ------------------------------------------------------------------
    # Prediction orchestration
    # ------------------------------------------------------------------

    async def predict_with_image(
        self,
        model_id: UUID,
        upload: ChestXrayUpload,
    ) -> PredictionResponse:
        """
        Run prediction through internal model-service.

        1. Validate model exists in metadata store.
        2. Forward image to internal model-service.
        3. Persist uploaded image metadata to S3.
        4. Return normalized prediction response.
        """
        model = await self._get_model_or_raise(model_id)
        runtime_client = self._get_runtime_client(ModelSlug(model.slug))
        prediction = await runtime_client.predict(image_data=upload.data, filename=upload.filename)
        upload_status = await self._upload_image_best_effort(upload)

        logger.info(
            "Prediction for model %s with image %s -> %s (confidence=%.4f)",
            model_id,
            upload_status.image_s3_key,
            prediction.prediction,
            prediction.confidence,
        )
        return PredictionResponse(
            model_id=model_id,
            prediction=prediction.prediction,
            confidence=prediction.confidence,
            image_s3_key=upload_status.image_s3_key,
        )

    async def predict(
        self,
        mode: PredictionMode,
        upload: ChestXrayUpload,
    ) -> UnifiedPredictionResponse:
        """Run public Prediction Orchestration."""
        orchestration = PredictionOrchestration(
            s3_service=self.s3_service,
            model_runtime_clients=self.model_runtime_clients,
        )
        return await orchestration.predict(mode=mode, upload=upload)

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

    def _get_runtime_client(self, slug: ModelSlug) -> ModelRuntimeClient:
        runtime_client = self.model_runtime_clients.get(slug)
        if runtime_client is None:
            raise ServiceUnavailable(f"Model-service for '{slug}' is not configured.")
        return runtime_client

    async def _upload_image_best_effort(
        self,
        upload: ChestXrayUpload,
    ) -> PredictionUploadStatus:
        try:
            s3_key = await self.s3_service.upload_chest_xray(upload)
        except Exception:
            logger.warning("Image upload failed for filename=%s", upload.filename, exc_info=True)
            return PredictionUploadStatus(status="error")

        return PredictionUploadStatus(status="ok", image_s3_key=s3_key)
