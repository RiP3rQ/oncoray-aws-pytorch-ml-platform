from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.errors import ServiceUnavailable
from src.intake.chest_xray_upload import ChestXrayUpload
from src.schemas.model_schemas import UnifiedPredictionResponse
from src.services.model_runtime_client import ModelRuntimeClient
from src.services.prediction_orchestration import PredictionOrchestration
from src.services.s3_service import S3Service
from src.types.enums import ModelSlug, PredictionMode


@pytest.fixture
def chest_xray_upload() -> ChestXrayUpload:
    return ChestXrayUpload(data=b"fake_image_data", filename="scan.jpg")


@pytest.fixture
def mock_s3_service() -> MagicMock:
    s3_service = MagicMock(spec=S3Service)
    s3_service.upload_chest_xray = AsyncMock(return_value="predictions/test-uuid.jpg")
    return s3_service


def make_runtime_client(prediction: str, confidence: float) -> MagicMock:
    runtime_client = MagicMock(spec=ModelRuntimeClient)
    runtime_client.predict = AsyncMock(return_value=SimpleNamespace(prediction=prediction, confidence=confidence))
    return runtime_client


@pytest.mark.asyncio
async def test_single_model_prediction_returns_public_prediction(
    mock_s3_service: MagicMock,
    chest_xray_upload: ChestXrayUpload,
) -> None:
    effnet_client = make_runtime_client("NORMAL", 0.91)
    orchestration = PredictionOrchestration(
        s3_service=mock_s3_service,
        model_runtime_clients={ModelSlug.EFFNETB0: effnet_client},
    )

    result = await orchestration.predict(mode=PredictionMode.EFFNETB0, upload=chest_xray_upload)

    assert isinstance(result, UnifiedPredictionResponse)
    assert result.mode == PredictionMode.EFFNETB0
    assert result.upload.status == "ok"
    assert result.upload.image_s3_key == "predictions/test-uuid.jpg"
    assert result.results[ModelSlug.EFFNETB0].status == "ok"
    assert result.results[ModelSlug.EFFNETB0].prediction == "NORMAL"
    effnet_client.predict.assert_called_once_with(
        image_data=b"fake_image_data",
        filename="scan.jpg",
    )


@pytest.mark.asyncio
async def test_both_mode_returns_partial_result_when_one_runtime_fails(
    mock_s3_service: MagicMock,
    chest_xray_upload: ChestXrayUpload,
) -> None:
    effnet_client = make_runtime_client("NORMAL", 0.91)
    vit_client = make_runtime_client("PNEUMONIA", 0.87)
    vit_client.predict.side_effect = ServiceUnavailable("timeout")
    orchestration = PredictionOrchestration(
        s3_service=mock_s3_service,
        model_runtime_clients={
            ModelSlug.EFFNETB0: effnet_client,
            ModelSlug.VITB16: vit_client,
        },
    )

    result = await orchestration.predict(mode=PredictionMode.BOTH, upload=chest_xray_upload)

    assert result.results[ModelSlug.EFFNETB0].status == "ok"
    assert result.results[ModelSlug.VITB16].status == "error"
    assert result.results[ModelSlug.VITB16].error == "timeout"


@pytest.mark.asyncio
async def test_single_model_missing_runtime_stays_inside_prediction_envelope(
    mock_s3_service: MagicMock,
    chest_xray_upload: ChestXrayUpload,
) -> None:
    orchestration = PredictionOrchestration(
        s3_service=mock_s3_service,
        model_runtime_clients={},
    )

    result = await orchestration.predict(mode=PredictionMode.VITB16, upload=chest_xray_upload)

    assert result.mode == PredictionMode.VITB16
    assert result.results[ModelSlug.VITB16].status == "error"
    assert result.results[ModelSlug.VITB16].error == "Model Runtime for 'vitb16' is not configured."


@pytest.mark.asyncio
async def test_upload_failure_is_best_effort(
    mock_s3_service: MagicMock,
    chest_xray_upload: ChestXrayUpload,
) -> None:
    mock_s3_service.upload_chest_xray.side_effect = RuntimeError("s3 down")
    orchestration = PredictionOrchestration(
        s3_service=mock_s3_service,
        model_runtime_clients={ModelSlug.EFFNETB0: make_runtime_client("NORMAL", 0.91)},
    )

    result = await orchestration.predict(mode=PredictionMode.EFFNETB0, upload=chest_xray_upload)

    assert result.upload.status == "error"
    assert result.upload.image_s3_key is None
    assert result.results[ModelSlug.EFFNETB0].status == "ok"
