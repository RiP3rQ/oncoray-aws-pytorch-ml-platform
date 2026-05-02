from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.types import ModelSlug

PROJECT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MODEL_ARTIFACT_PATH = Path("/models/model.pth")


class Settings(BaseSettings):
    """Runtime configuration for the internal model-service."""

    APP_NAME: str = "model-service"
    APP_ENVIRONMENT: str = "development"
    APP_LOG_LEVEL: str = "INFO"
    MODEL_SLUGS: str = "effnetb0,vitb16"
    MODEL_ARTIFACT_PATH: Path = DEFAULT_MODEL_ARTIFACT_PATH
    EFFNETB0_MODEL_ARTIFACT_URL: str = (
        "https://huggingface.co/RiP3rQ/effnetb0/resolve/main/effnetb0/effnetb0_epoch_008.pth"
    )
    VITB16_MODEL_ARTIFACT_URL: str = (
        "https://huggingface.co/RiP3rQ/vit_b_16/resolve/main/vit_b_16/vit_b_16_epoch_018.pth"
    )
    MODEL_DEVICE: str = "cpu"
    HF_TOKEN: str | None = None
    HF_USERNAME: str = "RiP3rQ"
    MODEL_NUM_THREADS: int = 1
    MODEL_CLASS_NAMES: str = "NORMAL,PNEUMONIA"
    MODEL_STRICT_LOAD: bool = True
    MODEL_STARTUP_SMOKE_TEST: bool = True
    OTEL_ENABLED: bool = True
    OTEL_SERVICE_NAME: str = "model-runtime-host"
    OTEL_EXPORTER_OTLP_ENDPOINT: str | None = None
    OTEL_EXCLUDED_URLS: str = "/livez,/readyz,/startupz"

    model_config = SettingsConfigDict(
        env_file=PROJECT_DIR / ".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    @field_validator("APP_LOG_LEVEL", mode="before")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("APP_ENVIRONMENT", mode="before")
    @classmethod
    def normalize_environment(cls, value: str) -> str:
        return value.strip().lower()

    @field_validator("MODEL_SLUGS", mode="before")
    @classmethod
    def normalize_model_slugs(cls, value: Any) -> str | None:
        if value is None:
            return None
        parsed = str(value).strip()
        return parsed or None

    @field_validator("EFFNETB0_MODEL_ARTIFACT_URL", "VITB16_MODEL_ARTIFACT_URL", mode="before")
    @classmethod
    def normalize_artifact_url(cls, value: str) -> str:
        parsed = value.strip()
        if not parsed:
            raise ValueError("Model Artifact URL must not be empty.")
        return parsed

    @field_validator("HF_TOKEN", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Any) -> str | None:
        if value is None:
            return None
        parsed = str(value).strip()
        return parsed or None

    @field_validator("HF_USERNAME", mode="before")
    @classmethod
    def normalize_required_text(cls, value: str) -> str:
        parsed = value.strip()
        if not parsed:
            raise ValueError("HF_USERNAME must not be empty.")
        return parsed

    @field_validator("OTEL_EXPORTER_OTLP_ENDPOINT", mode="before")
    @classmethod
    def normalize_optional_endpoint(cls, value: Any) -> str | None:
        if value is None:
            return None
        parsed = str(value).strip().rstrip("/")
        return parsed or None

    @property
    def class_names(self) -> tuple[str, ...]:
        parsed = tuple(name.strip() for name in self.MODEL_CLASS_NAMES.split(",") if name.strip())
        if len(parsed) < 2:
            raise ValueError("MODEL_CLASS_NAMES must define at least 2 class labels.")
        return parsed

    @property
    def model_slugs(self) -> tuple[ModelSlug, ...]:
        slugs = tuple(ModelSlug(slug.strip()) for slug in self.MODEL_SLUGS.split(",") if slug.strip())
        if not slugs:
            raise ValueError("MODEL_SLUGS must define at least one model slug.")
        return slugs

    def artifact_path_for_slug(self, slug: ModelSlug) -> Path:
        if len(self.model_slugs) == 1:
            return self.MODEL_ARTIFACT_PATH

        suffix = self.MODEL_ARTIFACT_PATH.suffix or ".pth"
        return self.MODEL_ARTIFACT_PATH.parent / f"{slug.value}{suffix}"


settings = Settings()


def validate_production_settings(runtime_settings: Settings = settings) -> None:
    """Fail fast when production Model Runtime Host config is unsafe."""
    if runtime_settings.APP_ENVIRONMENT != "production":
        return

    errors: list[str] = []
    if not runtime_settings.model_slugs:
        errors.append("MODEL_SLUGS must define at least one Model Runtime.")
    if runtime_settings.MODEL_DEVICE == "cuda":
        errors.append("MODEL_DEVICE=cuda is not supported by the current CPU production node group.")

    for slug in runtime_settings.model_slugs:
        artifact_url = runtime_settings.EFFNETB0_MODEL_ARTIFACT_URL
        if slug == ModelSlug.VITB16:
            artifact_url = runtime_settings.VITB16_MODEL_ARTIFACT_URL
        if "/resolve/main/" in artifact_url:
            errors.append(f"{slug.value} Model Artifact URL must use an immutable Hugging Face revision, not main.")

    if runtime_settings.HF_USERNAME == "RiP3rQ" and runtime_settings.HF_TOKEN is None:
        errors.append("HF_USERNAME/HF_TOKEN must be explicitly reviewed for production Model Artifact access.")

    if errors:
        raise RuntimeError("Invalid production Model Runtime configuration: " + " ".join(errors))
