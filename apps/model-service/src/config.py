from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.types import ModelSlug

PROJECT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Runtime configuration for the internal model-service."""

    APP_NAME: str = "model-service"
    APP_ENVIRONMENT: str = "development"
    APP_LOG_LEVEL: str = "INFO"
    MODEL_SLUG: ModelSlug = ModelSlug.EFFNETB0
    MODEL_ARTIFACT_PATH: Path = Path("/models/model.pth")
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

    @model_validator(mode="after")
    def require_hugging_face_source_in_production(self) -> Settings:
        if self.APP_ENVIRONMENT != "production":
            return self

        missing = [
            field_name
            for field_name, value in (
                ("HF_MODEL_REPOSITORY", self.HF_MODEL_REPOSITORY),
                ("HF_MODEL_FILENAME", self.HF_MODEL_FILENAME),
            )
            if value is None
        ]
        if missing:
            raise ValueError(
                "Production Model Runtime requires Hugging Face Model Artifact config: " + ", ".join(missing)
            )
        return self

    @property
    def class_names(self) -> tuple[str, ...]:
        parsed = tuple(name.strip() for name in self.MODEL_CLASS_NAMES.split(",") if name.strip())
        if len(parsed) < 2:
            raise ValueError("MODEL_CLASS_NAMES must define at least 2 class labels.")
        return parsed


settings = Settings()
