from src.api_types.enums import ModelSlug
from src.services.model_runtime_client import ModelRuntimeClient
from src.services.model_runtime_registry import ModelRuntimeRegistry


def test_model_runtime_registry_builds_adapters_from_runtime_urls() -> None:
    registry = ModelRuntimeRegistry(
        runtime_urls={
            ModelSlug.EFFNETB0: "http://effnet-service:8000",
            ModelSlug.VITB16: "http://vit-service:8000",
        },
        timeout_seconds=12.5,
    )

    adapters = registry.build_adapters()

    assert isinstance(adapters[ModelSlug.EFFNETB0], ModelRuntimeClient)
    assert isinstance(adapters[ModelSlug.VITB16], ModelRuntimeClient)
    assert adapters[ModelSlug.EFFNETB0].base_url == "http://effnet-service:8000"
    assert adapters[ModelSlug.VITB16].base_url == "http://vit-service:8000"
    assert adapters[ModelSlug.EFFNETB0].timeout_seconds == 12.5


def test_model_runtime_registry_returns_empty_map_without_runtime_urls() -> None:
    registry = ModelRuntimeRegistry(runtime_urls={}, timeout_seconds=12.5)

    assert registry.build_adapters() == {}
