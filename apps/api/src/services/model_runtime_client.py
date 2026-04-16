from __future__ import annotations

from uuid import UUID

import httpx
from pydantic import ValidationError

from src.core.errors import ServiceUnavailable, UpstreamServiceError
from src.core.logger import get_logger
from src.schemas.model_schemas import ModelRuntimePrediction

logger = get_logger(__name__)


class ModelRuntimeClient:
    """HTTP client for the internal model-service."""

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def predict(
        self,
        model_id: UUID,
        image_data: bytes,
        filename: str,
    ) -> ModelRuntimePrediction:
        request_url = f"{self.base_url}/predict"
        logger.info("Requesting prediction from model-service for model_id=%s", model_id)

        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.post(
                    request_url,
                    data={"model_id": str(model_id)},
                    files={
                        "image": (
                            filename,
                            image_data,
                            "application/octet-stream",
                        )
                    },
                )
                response.raise_for_status()
        except httpx.RequestError as exc:
            logger.error(
                "Model-service request failed for model_id=%s",
                model_id,
                exc_info=True,
            )
            raise ServiceUnavailable("Model-service is unavailable.") from exc
        except httpx.HTTPStatusError as exc:
            logger.error(
                "Model-service returned %s for model_id=%s",
                exc.response.status_code,
                model_id,
            )
            raise UpstreamServiceError(
                "Model-service failed to generate a prediction.",
            ) from exc

        try:
            return ModelRuntimePrediction.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            logger.error("Model-service returned invalid payload for model_id=%s", model_id)
            raise UpstreamServiceError(
                "Model-service returned an invalid prediction payload.",
            ) from exc
