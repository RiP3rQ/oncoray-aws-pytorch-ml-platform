from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.errors import ServiceUnavailable
from src.intake.chest_xray_upload import ChestXrayUpload
from src.services.model_runtime_client import ModelRuntimeClient
from src.services.model_runtime_pool import ModelRuntimeFailure, ModelRuntimePool, ModelRuntimeScore
from src.types.enums import ModelSlug


@pytest.fixture
def chest_xray_upload() -> ChestXrayUpload:
    return ChestXrayUpload(data=b"fake_image_data", filename="scan.jpg")


def make_runtime_client(prediction: str, confidence: float) -> MagicMock:
    runtime_client = MagicMock(spec=ModelRuntimeClient)
    runtime_client.predict = AsyncMock(return_value=SimpleNamespace(prediction=prediction, confidence=confidence))
    return runtime_client


@pytest.mark.asyncio
async def test_score_routes_upload_to_selected_runtime(chest_xray_upload: ChestXrayUpload) -> None:
    effnet_client = make_runtime_client("NORMAL", 0.91)
    pool = ModelRuntimePool(model_runtime_adapters={ModelSlug.EFFNETB0: effnet_client})

    result = await pool.score(slugs=(ModelSlug.EFFNETB0,), upload=chest_xray_upload)

    assert result[ModelSlug.EFFNETB0] == ModelRuntimeScore(prediction="NORMAL", confidence=0.91)
    effnet_client.predict.assert_called_once_with(
        image_data=b"fake_image_data",
        filename="scan.jpg",
    )


@pytest.mark.asyncio
async def test_score_returns_partial_failure_when_one_runtime_fails(chest_xray_upload: ChestXrayUpload) -> None:
    effnet_client = make_runtime_client("NORMAL", 0.91)
    vit_client = make_runtime_client("PNEUMONIA", 0.87)
    vit_client.predict.side_effect = ServiceUnavailable("timeout")
    pool = ModelRuntimePool(
        model_runtime_adapters={
            ModelSlug.EFFNETB0: effnet_client,
            ModelSlug.VITB16: vit_client,
        }
    )

    result = await pool.score(slugs=(ModelSlug.EFFNETB0, ModelSlug.VITB16), upload=chest_xray_upload)

    assert result[ModelSlug.EFFNETB0] == ModelRuntimeScore(prediction="NORMAL", confidence=0.91)
    assert result[ModelSlug.VITB16] == ModelRuntimeFailure(error="timeout")


@pytest.mark.asyncio
async def test_missing_runtime_returns_runtime_failure(chest_xray_upload: ChestXrayUpload) -> None:
    pool = ModelRuntimePool(model_runtime_adapters={})

    result = await pool.score(slugs=(ModelSlug.VITB16,), upload=chest_xray_upload)

    assert result[ModelSlug.VITB16] == ModelRuntimeFailure(error="Model Runtime for 'vitb16' is not configured.")
