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
    MODEL_SLUGS: str | None = None
    MODEL_SLUG: ModelSlug = ModelSlug.EFFNETB0
    MODEL_ARTIFACT_PATH: Path = DEFAULT_MODEL_ARTIFACT_PATH
    EFFNETB0_MODEL_ARTIFACT_URL: str = (
        "https://huggingface.co/RiP3rQ/effnetb0/resolve/main/effnetb0/effnetb0_epoch_008.pth"
    )
    VITB16_MODEL_ARTIFACT_URL: str = (
        "https://huggingface.co/RiP3rQ/vit_b_16/resolve/main/vit_b_16/vit_b_16_epoch_018.pth"
    )
    HF_MODEL_REPOSITORY: str | None = None
    HF_MODEL_REVISION: str = "main"
    HF_MODEL_FILENAME: str | None = None
    HF_TOKEN: str | None = None
    MODEL_ARTIFACT_SHA256: str | None = None
    MODEL_DEVICE: str = "cpu"
    MODEL_NUM_THREADS: int = 1
    MODEL_CLASS_NAMES: str = "NORMAL,PNEUMONIA"
    MODEL_STRICT_LOAD: bool = True
    MODEL_STARTUP_SMOKE_TEST: bool = True

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

    @field_validator("HF_MODEL_REPOSITORY", "HF_MODEL_FILENAME", "HF_TOKEN", "MODEL_ARTIFACT_SHA256", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: Any) -> str | None:
        if value is None:
            return None
        parsed = str(value).strip()
        return parsed or None

    @field_validator("HF_MODEL_REVISION", mode="before")
    @classmethod
    def normalize_revision(cls, value: str) -> str:
        parsed = value.strip()
        if not parsed:
            raise ValueError("HF_MODEL_REVISION must not be empty.")
        return parsed

    @field_validator("EFFNETB0_MODEL_ARTIFACT_URL", "VITB16_MODEL_ARTIFACT_URL", mode="before")
    @classmethod
    def normalize_required_url(cls, value: str) -> str:
        parsed = value.strip()
        if not parsed:
            raise ValueError("Model Artifact URL must not be empty.")
        return parsed

    @property
    def class_names(self) -> tuple[str, ...]:
        parsed = tuple(name.strip() for name in self.MODEL_CLASS_NAMES.split(",") if name.strip())
        if len(parsed) < 2:
            raise ValueError("MODEL_CLASS_NAMES must define at least 2 class labels.")
        return parsed

    @property
    def model_slugs(self) -> tuple[ModelSlug, ...]:
        if self.MODEL_SLUGS is None:
            return (self.MODEL_SLUG,)

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
