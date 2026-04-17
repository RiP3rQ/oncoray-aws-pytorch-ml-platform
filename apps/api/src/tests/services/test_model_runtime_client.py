"""
Tests for internal model-service HTTP client.
"""

import sys
from pathlib import Path

import httpx
import pytest

# Add project root to Python path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.core.errors import ServiceUnavailable, UpstreamServiceError
from src.services.model_runtime_client import ModelRuntimeClient
from src.types.enums import ModelSlug


class TestModelRuntimeClient:
    """Tests for ModelRuntimeClient."""

    @pytest.mark.asyncio
    async def test_predict_returns_validated_payload(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            assert request.url == httpx.URL("http://model-service:8000/predict")
            return httpx.Response(
                status_code=200,
                json={"prediction": "cat", "confidence": 0.95},
            )

        client = ModelRuntimeClient(
            base_url="http://model-service:8000",
            model_slug=ModelSlug.EFFNETB0,
            transport=httpx.MockTransport(handler),
        )

        result = await client.predict(
            image_data=b"data",
            filename="test.jpg",
        )

        assert result.prediction == "cat"
        assert result.confidence == 0.95

    @pytest.mark.asyncio
    async def test_predict_raises_service_unavailable_on_request_error(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("boom", request=request)

        client = ModelRuntimeClient(
            base_url="http://model-service:8000",
            model_slug=ModelSlug.EFFNETB0,
            transport=httpx.MockTransport(handler),
        )

        with pytest.raises(ServiceUnavailable):
            await client.predict(
                image_data=b"data",
                filename="test.jpg",
            )

    @pytest.mark.asyncio
    async def test_predict_raises_upstream_error_on_bad_status(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(
                status_code=500,
                json={"detail": "failed"},
                request=request,
            )

        client = ModelRuntimeClient(
            base_url="http://model-service:8000",
            model_slug=ModelSlug.EFFNETB0,
            transport=httpx.MockTransport(handler),
        )

        with pytest.raises(UpstreamServiceError):
            await client.predict(
                image_data=b"data",
                filename="test.jpg",
            )

    @pytest.mark.asyncio
    async def test_predict_raises_upstream_error_on_invalid_payload(self):
        async def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(status_code=200, json={"prediction": "cat"})

        client = ModelRuntimeClient(
            base_url="http://model-service:8000",
            model_slug=ModelSlug.EFFNETB0,
            transport=httpx.MockTransport(handler),
        )

        with pytest.raises(UpstreamServiceError):
            await client.predict(
                image_data=b"data",
                filename="test.jpg",
            )
