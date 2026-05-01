from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.config import Settings


def test_development_allows_local_model_artifact_only() -> None:
    settings = Settings(APP_ENVIRONMENT="development")

    assert settings.APP_ENVIRONMENT == "development"
    assert settings.HF_MODEL_REPOSITORY is None
    assert settings.HF_MODEL_FILENAME is None
    assert settings.MODEL_STARTUP_SMOKE_TEST is True


def test_production_requires_hugging_face_model_artifact_source() -> None:
    with pytest.raises(ValidationError, match="HF_MODEL_REPOSITORY, HF_MODEL_FILENAME"):
        Settings(APP_ENVIRONMENT="production")


def test_production_accepts_complete_hugging_face_model_artifact_source() -> None:
    settings = Settings(
        APP_ENVIRONMENT=" production ",
        HF_MODEL_REPOSITORY=" owner/repo ",
        HF_MODEL_REVISION=" abc123 ",
        HF_MODEL_FILENAME=" weights/model.pth ",
    )

    assert settings.APP_ENVIRONMENT == "production"
    assert settings.HF_MODEL_REPOSITORY == "owner/repo"
    assert settings.HF_MODEL_REVISION == "abc123"
    assert settings.HF_MODEL_FILENAME == "weights/model.pth"
