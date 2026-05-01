from __future__ import annotations

import asyncio
from typing import Protocol
from uuid import uuid4

from src.intake.chest_xray_upload import ChestXrayUpload
from src.schemas.model_schemas import PredictionResultStatus, PredictionUploadStatus, UnifiedPredictionResponse
from src.services.model_runtime_pool import (
    ModelRuntimeContribution,
    ModelRuntimeFailure,
    ModelRuntimePool,
    ModelRuntimeScore,
)
from src.types.enums import ModelSlug, PredictionMode


class ChestXrayUploadPersistence(Protocol):
    """Adapter that persists a Chest X-ray Upload for a public Prediction."""

    async def persist_chest_xray_upload(
        self,
        upload: ChestXrayUpload,
    ) -> PredictionUploadStatus: ...


class PredictionOrchestration:
    """API-owned public Prediction workflow."""

    def __init__(
        self,
        upload_persistence: ChestXrayUploadPersistence,
        model_runtime_pool: ModelRuntimePool,
    ) -> None:
        self.upload_persistence = upload_persistence
        self.model_runtime_pool = model_runtime_pool

    async def predict(
        self,
        mode: PredictionMode,
        upload: ChestXrayUpload,
    ) -> UnifiedPredictionResponse:
        request_id = uuid4()
        slugs = _slugs_for_mode(mode)
        upload_task = asyncio.create_task(self.upload_persistence.persist_chest_xray_upload(upload))
        contributions = await self.model_runtime_pool.score(slugs=slugs, upload=upload)
        upload_status = await upload_task

        return UnifiedPredictionResponse(
            request_id=request_id,
            mode=mode,
            upload=upload_status,
            results=_prediction_results_from_contributions(contributions),
        )


def _slugs_for_mode(mode: PredictionMode) -> tuple[ModelSlug, ...]:
    if mode == PredictionMode.BOTH:
        return (ModelSlug.EFFNETB0, ModelSlug.VITB16)
    return (ModelSlug(mode.value),)


def _prediction_results_from_contributions(
    contributions: dict[ModelSlug, ModelRuntimeContribution],
) -> dict[ModelSlug, PredictionResultStatus]:
    return {slug: _prediction_result_from_contribution(contribution) for slug, contribution in contributions.items()}


def _prediction_result_from_contribution(contribution: ModelRuntimeContribution) -> PredictionResultStatus:
    if isinstance(contribution, ModelRuntimeScore):
        return PredictionResultStatus(
            status="ok",
            prediction=contribution.prediction,
            confidence=contribution.confidence,
        )
    if isinstance(contribution, ModelRuntimeFailure):
        return PredictionResultStatus(status="error", error=contribution.error)
    raise TypeError(f"Unsupported Model Runtime contribution: {type(contribution)}")
