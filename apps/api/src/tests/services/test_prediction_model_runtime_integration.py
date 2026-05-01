from __future__ import annotations

from typing import Annotated

import httpx
import pytest
from fastapi import FastAPI, File, UploadFile

from src.api_types.enums import ModelSlug, PredictionMode
from src.intake.chest_xray_upload import ChestXrayUpload
from src.schemas.model_schemas import ModelRuntimePrediction, PredictionUploadStatus
from src.services.model_runtime_client import ModelRuntimeClient
from src.services.model_runtime_pool import ModelRuntimePool
from src.services.prediction_orchestration import PredictionOrchestration


class MemoryUploadPersistence:
    async def persist_chest_xray_upload(self, upload: ChestXrayUpload) -> PredictionUploadStatus:
        return PredictionUploadStatus(status="ok", image_s3_key=f"predictions/{upload.filename}")


def create_model_runtime_app() -> FastAPI:
    app = FastAPI()

    @app.post("/predict", response_model=ModelRuntimePrediction)
    async def predict(image: Annotated[UploadFile, File(...)]) -> ModelRuntimePrediction:
        image_data = await image.read()
        assert image.filename == "scan.png"
        assert image_data == b"png-bytes"
        return ModelRuntimePrediction(prediction="NORMAL", confidence=0.98)

    return app


@pytest.mark.asyncio
async def test_prediction_orchestration_calls_model_runtime_over_http() -> None:
    model_runtime_app = create_model_runtime_app()
    model_runtime_client = ModelRuntimeClient(
        base_url="http://model-runtime",
        model_slug=ModelSlug.EFFNETB0,
        transport=httpx.ASGITransport(app=model_runtime_app),
    )
    orchestration = PredictionOrchestration(
        upload_persistence=MemoryUploadPersistence(),
        model_runtime_pool=ModelRuntimePool({ModelSlug.EFFNETB0: model_runtime_client}),
    )

    result = await orchestration.predict(
        mode=PredictionMode.EFFNETB0,
        upload=ChestXrayUpload(data=b"png-bytes", filename="scan.png"),
    )

    assert result.mode == PredictionMode.EFFNETB0
    assert result.upload.status == "ok"
    assert result.upload.image_s3_key == "predictions/scan.png"
    assert result.results[ModelSlug.EFFNETB0].status == "ok"
    assert result.results[ModelSlug.EFFNETB0].prediction == "NORMAL"
    assert result.results[ModelSlug.EFFNETB0].confidence == 0.98
