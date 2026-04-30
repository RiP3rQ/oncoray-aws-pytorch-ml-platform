from __future__ import annotations

import asyncio
from uuid import uuid4

from src.core.errors import ServiceUnavailable
from src.core.logger import get_logger
from src.intake.chest_xray_upload import ChestXrayUpload
from src.schemas.model_schemas import PredictionResultStatus, PredictionUploadStatus, UnifiedPredictionResponse
from src.services.model_runtime_client import ModelRuntimeClient
from src.services.s3_service import S3Service
from src.types.enums import ModelSlug, PredictionMode

logger = get_logger(__name__)


class PredictionOrchestration:
    """API-owned public Prediction workflow."""

    def __init__(
        self,
        s3_service: S3Service,
        model_runtime_clients: dict[ModelSlug, ModelRuntimeClient] | None = None,
    ) -> None:
        self.s3_service = s3_service
        self.model_runtime_clients = model_runtime_clients or {}

    async def predict(
        self,
        mode: PredictionMode,
        upload: ChestXrayUpload,
    ) -> UnifiedPredictionResponse:
        request_id = uuid4()
        slugs = _slugs_for_mode(mode)
        upload_task = asyncio.create_task(self._upload_image_best_effort(upload))
        result_tasks = {slug: asyncio.create_task(self._predict_single_result(slug, upload)) for slug in slugs}

        results = {slug: await result_task for slug, result_task in result_tasks.items()}
        upload_status = await upload_task

        return UnifiedPredictionResponse(
            request_id=request_id,
            mode=mode,
            upload=upload_status,
            results=results,
        )

    def _get_runtime_client(self, slug: ModelSlug) -> ModelRuntimeClient:
        runtime_client = self.model_runtime_clients.get(slug)
        if runtime_client is None:
            raise ServiceUnavailable(f"Model Runtime for '{slug}' is not configured.")
        return runtime_client

    async def _predict_single_result(
        self,
        slug: ModelSlug,
        upload: ChestXrayUpload,
    ) -> PredictionResultStatus:
        try:
            prediction = await self._get_runtime_client(slug).predict(
                image_data=upload.data,
                filename=upload.filename,
            )
        except ServiceUnavailable as exc:
            logger.warning("Prediction failed for slug=%s: %s", slug, exc.detail)
            return PredictionResultStatus(status="error", error=exc.detail)
        except Exception as exc:
            logger.warning("Prediction failed for slug=%s", slug, exc_info=True)
            detail = getattr(exc, "detail", "Prediction failed.")
            return PredictionResultStatus(status="error", error=detail)

        return PredictionResultStatus(
            status="ok",
            prediction=prediction.prediction,
            confidence=prediction.confidence,
        )

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


def _slugs_for_mode(mode: PredictionMode) -> tuple[ModelSlug, ...]:
    if mode == PredictionMode.BOTH:
        return (ModelSlug.EFFNETB0, ModelSlug.VITB16)
    return (ModelSlug(mode.value),)
