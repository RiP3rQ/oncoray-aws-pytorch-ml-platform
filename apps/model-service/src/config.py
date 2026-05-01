from __future__ import annotations

from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from src.types import ModelSlug

PROJECT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Runtime configuration for the internal model-service."""

    APP_NAME: str = "model-service"
    APP_LOG_LEVEL: str = "INFO"
    MODEL_SLUG: ModelSlug = ModelSlug.EFFNETB0
    MODEL_ARTIFACT_PATH: Path = Path("/models/model.pth")
    MODEL_DEVICE: str = "cpu"
    MODEL_NUM_THREADS: int = 1
    MODEL_CLASS_NAMES: str = "NORMAL,PNEUMONIA"
    MODEL_STRICT_LOAD: bool = True

    model_config = SettingsConfigDict(
        env_file=PROJECT_DIR / ".env",
        env_ignore_empty=True,
        extra="ignore",
    )

    @field_validator("APP_LOG_LEVEL", mode="before")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        return value.strip().upper()

    @property
    def class_names(self) -> tuple[str, ...]:
        parsed = tuple(name.strip() for name in self.MODEL_CLASS_NAMES.split(",") if name.strip())
        if len(parsed) < 2:
            raise ValueError("MODEL_CLASS_NAMES must define at least 2 class labels.")
        return parsed


settings = Settings()
