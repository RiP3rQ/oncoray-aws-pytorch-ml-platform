from __future__ import annotations

from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image

from src.app import create_app
from src.types import ModelSlug


class FixedPredictionRuntime:
    def __init__(self, slug: ModelSlug):
        self.slug = slug

    def predict(self, image_data: bytes):
        return {"prediction": "NORMAL", "confidence": 0.99}


def make_png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (32, 32), color=(240, 240, 240)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_health_endpoints_and_root():
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


def test_predict_endpoint_returns_normalized_payload():
    app = create_app(runtime=FixedPredictionRuntime(ModelSlug.VITB16))
    with TestClient(app) as client:
        response = client.post(
            "/predict",
            files={"image": ("scan.png", make_png_bytes(), "image/png")},
        )

        assert response.status_code == 200
        assert response.json() == {"prediction": "NORMAL", "confidence": 0.99}


def test_predict_endpoint_rejects_oversized_image():
    app = create_app(runtime=FixedPredictionRuntime(ModelSlug.EFFNETB0))
    with TestClient(app) as client:
        response = client.post(
            "/predict",
            files={"image": ("scan.png", b"x" * (3 * 1024 * 1024), "image/png")},
        )

        assert response.status_code == 413
