from __future__ import annotations

import asyncio
from dataclasses import dataclass

from src.core.errors import ServiceUnavailable
from src.core.logger import get_logger
from src.intake.chest_xray_upload import ChestXrayUpload
from src.services.model_runtime_client import ModelRuntimeClient
from src.types.enums import ModelSlug

logger = get_logger(__name__)


@dataclass(frozen=True)
class ModelRuntimeScore:
    prediction: str
    confidence: float


@dataclass(frozen=True)
class ModelRuntimeFailure:
    error: str


ModelRuntimeContribution = ModelRuntimeScore | ModelRuntimeFailure


class ModelRuntimePool:
    """Scores a Chest X-ray Upload with selected Model Runtimes."""

    def __init__(
        self,
        model_runtime_clients: dict[ModelSlug, ModelRuntimeClient] | None = None,
    ) -> None:
        self.model_runtime_clients = model_runtime_clients or {}

    async def score(
        self,
        slugs: tuple[ModelSlug, ...],
        upload: ChestXrayUpload,
    ) -> dict[ModelSlug, ModelRuntimeContribution]:
        tasks = {slug: asyncio.create_task(self._score_single_runtime(slug, upload)) for slug in slugs}
        return {slug: await task for slug, task in tasks.items()}

    def _get_runtime_client(self, slug: ModelSlug) -> ModelRuntimeClient:
        runtime_client = self.model_runtime_clients.get(slug)
        if runtime_client is None:
            raise ServiceUnavailable(f"Model Runtime for '{slug}' is not configured.")
        return runtime_client

    async def _score_single_runtime(
        self,
        slug: ModelSlug,
        upload: ChestXrayUpload,
    ) -> ModelRuntimeContribution:
        try:
            prediction = await self._get_runtime_client(slug).predict(
                image_data=upload.data,
                filename=upload.filename,
            )
        except ServiceUnavailable as exc:
            logger.warning("Prediction failed for slug=%s: %s", slug, exc.detail)
            return ModelRuntimeFailure(error=exc.detail)
        except Exception as exc:
            logger.warning("Prediction failed for slug=%s", slug, exc_info=True)
            detail = getattr(exc, "detail", "Prediction failed.")
            return ModelRuntimeFailure(error=detail)

        return ModelRuntimeScore(
            prediction=prediction.prediction,
            confidence=prediction.confidence,
        )
