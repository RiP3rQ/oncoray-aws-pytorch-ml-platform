from __future__ import annotations

from src.api_types.enums import ModelSlug
from src.services.model_runtime_client import ModelRuntimeClient
from src.services.model_runtime_pool import ModelRuntimeAdapter


class ModelRuntimeRegistry:
    """Build configured Model Runtime adapters."""

    def __init__(
        self,
        runtime_urls: dict[ModelSlug, str],
        timeout_seconds: float,
    ) -> None:
        self.runtime_urls = runtime_urls
        self.timeout_seconds = timeout_seconds

    def build_adapters(self) -> dict[ModelSlug, ModelRuntimeAdapter]:
        return {
            slug: ModelRuntimeClient(
                base_url=base_url,
                model_slug=slug,
                timeout_seconds=self.timeout_seconds,
            )
            for slug, base_url in self.runtime_urls.items()
        }
