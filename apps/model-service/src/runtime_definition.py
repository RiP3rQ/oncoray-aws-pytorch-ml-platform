from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

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
        return cls.from_settings_for_slug(settings, settings.MODEL_SLUG, model_specs)

    @classmethod
    def from_settings_for_slug(
        cls,
        settings: Settings,
        slug: ModelSlug,
        model_specs: dict[ModelSlug, ModelSpec],
    ) -> ModelRuntimeDefinition:
        spec = model_specs[slug]
        if spec.slug != slug:
            raise ValueError(f"ModelSpec slug mismatch settings={slug} spec={spec.slug}.")

        return cls(
            slug=slug,
            spec=spec,
            artifact_path=settings.artifact_path_for_slug(slug),
            artifact_source=hugging_face_source_from_settings(settings, slug=slug),
            artifact_sha256=settings.MODEL_ARTIFACT_SHA256,
            device_name=settings.MODEL_DEVICE,
            num_threads=settings.MODEL_NUM_THREADS,
            class_names=settings.class_names,
            strict_load=settings.MODEL_STRICT_LOAD,
            startup_smoke_test=settings.MODEL_STARTUP_SMOKE_TEST,
        )


def hugging_face_source_from_settings(
    settings: Settings,
    slug: ModelSlug | None = None,
) -> HuggingFaceArtifactSource | None:
    if settings.HF_MODEL_REPOSITORY is None:
        return hugging_face_source_from_url(
            model_artifact_url_from_settings(settings, slug=slug),
            token=settings.HF_TOKEN,
        )

    return HuggingFaceArtifactSource(
        repo_id=settings.HF_MODEL_REPOSITORY,
        revision=settings.HF_MODEL_REVISION,
        filename=settings.HF_MODEL_FILENAME,
        token=settings.HF_TOKEN,
    )


def model_artifact_url_from_settings(settings: Settings, slug: ModelSlug | None = None) -> str:
    resolved_slug = slug or settings.MODEL_SLUG
    match resolved_slug:
        case ModelSlug.EFFNETB0:
            return settings.EFFNETB0_MODEL_ARTIFACT_URL
        case ModelSlug.VITB16:
            return settings.VITB16_MODEL_ARTIFACT_URL


def hugging_face_source_from_url(url: str, *, token: str | None = None) -> HuggingFaceArtifactSource:
    parsed_url = urlparse(url.strip())
    path_parts = [unquote(part) for part in parsed_url.path.split("/") if part]
    if parsed_url.netloc.lower() != "huggingface.co" or len(path_parts) < 5 or path_parts[2] != "resolve":
        raise ValueError(f"Expected Hugging Face resolve URL, got: {url}")

    return HuggingFaceArtifactSource(
        repo_id=f"{path_parts[0]}/{path_parts[1]}",
        revision=path_parts[3],
        filename="/".join(path_parts[4:]),
        token=token,
    )
