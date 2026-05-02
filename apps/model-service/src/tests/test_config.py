from __future__ import annotations

from src.config import Settings


def test_development_allows_local_model_artifact_only() -> None:
    settings = Settings(APP_ENVIRONMENT="development")

    assert settings.APP_ENVIRONMENT == "development"
    assert settings.HF_MODEL_REPOSITORY is None
    assert settings.HF_MODEL_FILENAME is None
    assert settings.MODEL_STARTUP_SMOKE_TEST is True
    assert settings.EFFNETB0_MODEL_ARTIFACT_URL.endswith("effnetb0/effnetb0_epoch_008.pth")
    assert settings.VITB16_MODEL_ARTIFACT_URL.endswith("vit_b_16/vit_b_16_epoch_018.pth")


def test_production_uses_default_hugging_face_model_artifact_source() -> None:
    settings = Settings(APP_ENVIRONMENT="production")

    assert settings.APP_ENVIRONMENT == "production"
    assert settings.HF_MODEL_REPOSITORY is None
    assert settings.HF_MODEL_FILENAME is None


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
