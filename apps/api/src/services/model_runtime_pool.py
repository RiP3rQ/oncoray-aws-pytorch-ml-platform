from __future__ import annotations

import asyncio
from dataclasses import dataclass
from time import perf_counter
from typing import Protocol

from src.api_types.enums import ModelSlug
from src.core.errors import ServiceUnavailable, UpstreamServiceError
from src.core.logger import get_logger
from src.intake.chest_xray_upload import ChestXrayUpload
from src.schemas.model_schemas import ModelRuntimePrediction

logger = get_logger(__name__)


@dataclass(frozen=True)
class ModelRuntimeScore:
    prediction: str
    confidence: float
    latency_ms: float | None = None


@dataclass(frozen=True)
class ModelRuntimeFailure:
    error: str
    error_kind: str = "unknown"
    status_code: int | None = None
    latency_ms: float | None = None


ModelRuntimeContribution = ModelRuntimeScore | ModelRuntimeFailure


class ModelRuntimeAdapter(Protocol):
    """Adapter that can score a Chest X-ray Upload for one Model Runtime."""

    async def predict(
        self,
        image_data: bytes,
        filename: str,
    ) -> ModelRuntimePrediction: ...


class ModelRuntimePool:
    """Scores a Chest X-ray Upload with selected Model Runtimes."""

    def __init__(
        self,
        model_runtime_adapters: dict[ModelSlug, ModelRuntimeAdapter] | None = None,
    ) -> None:
        self.model_runtime_adapters = model_runtime_adapters or {}

    async def score(
        self,
        slugs: tuple[ModelSlug, ...],
        upload: ChestXrayUpload,
    ) -> dict[ModelSlug, ModelRuntimeContribution]:
        tasks = {slug: asyncio.create_task(self._score_single_runtime(slug, upload)) for slug in slugs}
        return {slug: await task for slug, task in tasks.items()}

    def _get_runtime_adapter(self, slug: ModelSlug) -> ModelRuntimeAdapter:
        runtime_adapter = self.model_runtime_adapters.get(slug)
        if runtime_adapter is None:
            raise ServiceUnavailable(f"Model Runtime for '{slug}' is not configured.")
        return runtime_adapter

    async def _score_single_runtime(
        self,
        slug: ModelSlug,
        upload: ChestXrayUpload,
    ) -> ModelRuntimeContribution:
        started_at = perf_counter()
        try:
            prediction = await self._get_runtime_adapter(slug).predict(
                image_data=upload.data,
                filename=upload.filename,
            )
        except ServiceUnavailable as exc:
            latency_ms = elapsed_ms(started_at)
            logger.warning(
                "Prediction failed for slug=%s kind=unavailable latency_ms=%.2f detail=%s",
                slug,
                latency_ms,
                exc.detail,
            )
            return ModelRuntimeFailure(error=exc.detail, error_kind="unavailable", latency_ms=latency_ms)
        except UpstreamServiceError as exc:
            latency_ms = elapsed_ms(started_at)
            logger.warning(
                "Prediction failed for slug=%s kind=upstream_error status_code=%s latency_ms=%.2f detail=%s",
                slug,
                exc.upstream_status_code,
                latency_ms,
                exc.detail,
            )
            return ModelRuntimeFailure(
                error=exc.detail,
                error_kind="upstream_error",
                status_code=exc.upstream_status_code,
                latency_ms=latency_ms,
            )
        except Exception as exc:
            latency_ms = elapsed_ms(started_at)
            logger.warning(
                "Prediction failed for slug=%s kind=unexpected latency_ms=%.2f",
                slug,
                latency_ms,
                exc_info=True,
            )
            detail = getattr(exc, "detail", "Prediction failed.")
            return ModelRuntimeFailure(error=detail, error_kind="unexpected", latency_ms=latency_ms)

        latency_ms = elapsed_ms(started_at)
        logger.info("Prediction succeeded for slug=%s latency_ms=%.2f", slug, latency_ms)
        return ModelRuntimeScore(
            prediction=prediction.prediction,
            confidence=prediction.confidence,
            latency_ms=latency_ms,
        )


def elapsed_ms(started_at: float) -> float:
    return (perf_counter() - started_at) * 1000
