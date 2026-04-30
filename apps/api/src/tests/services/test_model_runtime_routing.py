from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.errors import ServiceUnavailable
from src.intake.chest_xray_upload import ChestXrayUpload
from src.services.model_runtime_client import ModelRuntimeClient
from src.services.model_runtime_routing import ModelRuntimeRouting
from src.types.enums import ModelSlug


@pytest.fixture
def chest_xray_upload() -> ChestXrayUpload:
    return ChestXrayUpload(data=b"fake_image_data", filename="scan.jpg")


def make_runtime_client(prediction: str, confidence: float) -> MagicMock:
    runtime_client = MagicMock(spec=ModelRuntimeClient)
    runtime_client.predict = AsyncMock(return_value=SimpleNamespace(prediction=prediction, confidence=confidence))
    return runtime_client


@pytest.mark.asyncio
async def test_predict_routes_upload_to_selected_runtime(chest_xray_upload: ChestXrayUpload) -> None:
    effnet_client = make_runtime_client("NORMAL", 0.91)
    routing = ModelRuntimeRouting(model_runtime_clients={ModelSlug.EFFNETB0: effnet_client})

    result = await routing.predict(slugs=(ModelSlug.EFFNETB0,), upload=chest_xray_upload)

    assert result[ModelSlug.EFFNETB0].status == "ok"
    assert result[ModelSlug.EFFNETB0].prediction == "NORMAL"
    assert result[ModelSlug.EFFNETB0].confidence == 0.91
    effnet_client.predict.assert_called_once_with(
        image_data=b"fake_image_data",
        filename="scan.jpg",
    )


@pytest.mark.asyncio
async def test_predict_returns_partial_result_when_one_runtime_fails(chest_xray_upload: ChestXrayUpload) -> None:
    effnet_client = make_runtime_client("NORMAL", 0.91)
    vit_client = make_runtime_client("PNEUMONIA", 0.87)
    vit_client.predict.side_effect = ServiceUnavailable("timeout")
    routing = ModelRuntimeRouting(
        model_runtime_clients={
            ModelSlug.EFFNETB0: effnet_client,
            ModelSlug.VITB16: vit_client,
        }
    )

    result = await routing.predict(slugs=(ModelSlug.EFFNETB0, ModelSlug.VITB16), upload=chest_xray_upload)

    assert result[ModelSlug.EFFNETB0].status == "ok"
    assert result[ModelSlug.VITB16].status == "error"
    assert result[ModelSlug.VITB16].error == "timeout"


@pytest.mark.asyncio
async def test_missing_runtime_stays_inside_prediction_result(chest_xray_upload: ChestXrayUpload) -> None:
    routing = ModelRuntimeRouting(model_runtime_clients={})

    result = await routing.predict(slugs=(ModelSlug.VITB16,), upload=chest_xray_upload)

    assert result[ModelSlug.VITB16].status == "error"
    assert result[ModelSlug.VITB16].error == "Model Runtime for 'vitb16' is not configured."
