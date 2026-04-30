from unittest.mock import AsyncMock, MagicMock

import pytest

from src.intake.chest_xray_upload import ChestXrayUpload
from src.schemas.model_schemas import UnifiedPredictionResponse
from src.services.model_runtime_pool import ModelRuntimeFailure, ModelRuntimePool, ModelRuntimeScore
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


def make_runtime_pool(results: dict[ModelSlug, ModelRuntimeScore | ModelRuntimeFailure]) -> MagicMock:
    runtime_pool = MagicMock(spec=ModelRuntimePool)
    runtime_pool.score = AsyncMock(return_value=results)
    return runtime_pool


@pytest.mark.asyncio
async def test_single_model_prediction_returns_public_prediction(
    mock_s3_service: MagicMock,
    chest_xray_upload: ChestXrayUpload,
) -> None:
    runtime_pool = make_runtime_pool(
        {
            ModelSlug.EFFNETB0: ModelRuntimeScore(
                prediction="NORMAL",
                confidence=0.91,
            )
        }
    )
    orchestration = PredictionOrchestration(
        s3_service=mock_s3_service,
        model_runtime_pool=runtime_pool,
    )

    result = await orchestration.predict(mode=PredictionMode.EFFNETB0, upload=chest_xray_upload)

    assert isinstance(result, UnifiedPredictionResponse)
    assert result.mode == PredictionMode.EFFNETB0
    assert result.upload.status == "ok"
    assert result.upload.image_s3_key == "predictions/test-uuid.jpg"
    assert result.results[ModelSlug.EFFNETB0].status == "ok"
    assert result.results[ModelSlug.EFFNETB0].prediction == "NORMAL"
    runtime_pool.score.assert_called_once_with(
        slugs=(ModelSlug.EFFNETB0,),
        upload=chest_xray_upload,
    )


@pytest.mark.asyncio
async def test_both_mode_expands_to_both_model_runtimes(
    mock_s3_service: MagicMock,
    chest_xray_upload: ChestXrayUpload,
) -> None:
    runtime_pool = make_runtime_pool(
        {
            ModelSlug.EFFNETB0: ModelRuntimeScore(prediction="NORMAL", confidence=0.91),
            ModelSlug.VITB16: ModelRuntimeFailure(error="timeout"),
        }
    )
    orchestration = PredictionOrchestration(
        s3_service=mock_s3_service,
        model_runtime_pool=runtime_pool,
    )

    result = await orchestration.predict(mode=PredictionMode.BOTH, upload=chest_xray_upload)

    runtime_pool.score.assert_called_once_with(
        slugs=(ModelSlug.EFFNETB0, ModelSlug.VITB16),
        upload=chest_xray_upload,
    )
    assert result.results[ModelSlug.EFFNETB0].status == "ok"
    assert result.results[ModelSlug.VITB16].status == "error"
    assert result.results[ModelSlug.VITB16].error == "timeout"


@pytest.mark.asyncio
async def test_single_model_runtime_errors_stay_inside_prediction_envelope(
    mock_s3_service: MagicMock,
    chest_xray_upload: ChestXrayUpload,
) -> None:
    runtime_pool = make_runtime_pool(
        {ModelSlug.VITB16: ModelRuntimeFailure(error="Model Runtime for 'vitb16' is not configured.")}
    )
    orchestration = PredictionOrchestration(
        s3_service=mock_s3_service,
        model_runtime_pool=runtime_pool,
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
    runtime_pool = make_runtime_pool(
        {
            ModelSlug.EFFNETB0: ModelRuntimeScore(
                prediction="NORMAL",
                confidence=0.91,
            )
        }
    )
    orchestration = PredictionOrchestration(
        s3_service=mock_s3_service,
        model_runtime_pool=runtime_pool,
    )

    result = await orchestration.predict(mode=PredictionMode.EFFNETB0, upload=chest_xray_upload)

    assert result.upload.status == "error"
    assert result.upload.image_s3_key is None
    assert result.results[ModelSlug.EFFNETB0].status == "ok"
