from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image
from pytest import MonkeyPatch

from src.app import create_app
from src.config import Settings
from src.schemas import ModelRuntimePrediction
from src.types import ModelSlug


class FixedPredictionRuntime:
    def __init__(self, slug: ModelSlug) -> None:
        self.slug = slug

    def predict(self, image_data: bytes) -> ModelRuntimePrediction:
        return ModelRuntimePrediction(prediction="NORMAL", confidence=0.99)


class InvalidImageRuntime:
    slug = ModelSlug.EFFNETB0

    def predict(self, image_data: bytes) -> ModelRuntimePrediction:
        raise ValueError("Invalid image data.")


def make_png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (32, 32), color=(240, 240, 240)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_health_endpoints_and_root() -> None:
    app = create_app(runtime=FixedPredictionRuntime(ModelSlug.EFFNETB0))
    with TestClient(app) as client:
        assert client.get("/").json() == {
            "service": "model-service",
            "status": "ok",
            "model": "effnetb0",
        }
        assert client.get("/livez").json() == {"status": "ok"}
        assert client.get("/readyz").json() == {"status": "ok", "model": "effnetb0"}
        assert client.get("/startupz").json() == {"status": "ok", "model": "effnetb0"}


def test_lifespan_loads_runtime_before_readiness(monkeypatch: MonkeyPatch) -> None:
    loaded_settings: list[Settings] = []
    runtime = FixedPredictionRuntime(ModelSlug.VITB16)

    class FakeFactory:
        def __init__(self, runtime_settings: Settings) -> None:
            self.runtime_settings = runtime_settings

        @classmethod
        def from_settings(cls, runtime_settings: Settings) -> FakeFactory:
            loaded_settings.append(runtime_settings)
            return cls(runtime_settings)

        def build(self) -> FixedPredictionRuntime:
            return runtime

    monkeypatch.setattr("src.app.ModelRuntimeFactory", FakeFactory)
    settings = Settings(MODEL_SLUG=ModelSlug.VITB16)
    app = create_app(runtime_settings=settings)

    with TestClient(app) as client:
        assert client.get("/readyz").json() == {"status": "ok", "model": "vitb16"}

    assert loaded_settings == [settings]


def test_predict_endpoint_returns_normalized_payload() -> None:
    app = create_app(runtime=FixedPredictionRuntime(ModelSlug.VITB16))
    with TestClient(app) as client:
        response = client.post(
            "/predict",
            files={"image": ("scan.png", make_png_bytes(), "image/png")},
        )

        assert response.status_code == 200
        assert response.json() == {"prediction": "NORMAL", "confidence": 0.99}


def test_predict_endpoint_maps_invalid_image_data_to_bad_request() -> None:
    app = create_app(runtime=InvalidImageRuntime())
    with TestClient(app) as client:
        response = client.post(
            "/predict",
            files={"image": ("scan.png", b"not-image", "image/png")},
        )

        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid image data."}


def test_predict_endpoint_treats_multipart_as_transport_only() -> None:
    app = create_app(runtime=FixedPredictionRuntime(ModelSlug.EFFNETB0))
    with TestClient(app) as client:
        response = client.post(
            "/predict",
            files={"image": ("scan.txt", make_png_bytes(), "text/plain")},
        )

        assert response.status_code == 200
