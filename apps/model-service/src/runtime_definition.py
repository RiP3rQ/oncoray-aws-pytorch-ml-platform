from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from src.config import Settings
from src.model_artifacts import HuggingFaceArtifactSource
from src.model_specs import ModelSpec
from src.types import ModelSlug


@dataclass(frozen=True)
class ModelRuntimeDefinition:
    """Deploy recipe for one Model Runtime."""

    slug: ModelSlug
    spec: ModelSpec
    artifact_path: Path
    artifact_source: HuggingFaceArtifactSource | None
    artifact_sha256: str | None
    device_name: str
    num_threads: int
    class_names: tuple[str, ...]
    strict_load: bool
    startup_smoke_test: bool

    @classmethod
    def from_settings(
        cls,
        settings: Settings,
        model_specs: dict[ModelSlug, ModelSpec],
    ) -> ModelRuntimeDefinition:
        spec = model_specs[settings.MODEL_SLUG]
        if spec.slug != settings.MODEL_SLUG:
            raise ValueError(f"ModelSpec slug mismatch settings={settings.MODEL_SLUG} spec={spec.slug}.")

        return cls(
            slug=settings.MODEL_SLUG,
            spec=spec,
            artifact_path=settings.MODEL_ARTIFACT_PATH,
            artifact_source=hugging_face_source_from_settings(settings),
            artifact_sha256=settings.MODEL_ARTIFACT_SHA256,
            device_name=settings.MODEL_DEVICE,
            num_threads=settings.MODEL_NUM_THREADS,
            class_names=settings.class_names,
            strict_load=settings.MODEL_STRICT_LOAD,
            startup_smoke_test=settings.MODEL_STARTUP_SMOKE_TEST,
        )


def hugging_face_source_from_settings(settings: Settings) -> HuggingFaceArtifactSource | None:
    if settings.HF_MODEL_REPOSITORY is None:
        return None
    return HuggingFaceArtifactSource(
        repo_id=settings.HF_MODEL_REPOSITORY,
        revision=settings.HF_MODEL_REVISION,
        filename=settings.HF_MODEL_FILENAME or settings.MODEL_ARTIFACT_PATH.name,
        token=settings.HF_TOKEN,
    )
