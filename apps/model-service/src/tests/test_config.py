from __future__ import annotations

from pathlib import Path

from src.config import Settings
from src.types import ModelSlug


def settings_without_env(**overrides: object) -> Settings:
    return Settings(**overrides, _env_file=None)  # type: ignore[call-arg,arg-type]


def test_development_allows_local_model_artifact_only() -> None:
    settings = settings_without_env(APP_ENVIRONMENT="development")

    assert settings.APP_ENVIRONMENT == "development"
    assert settings.HF_MODEL_REPOSITORY is None
    assert settings.HF_MODEL_FILENAME is None
    assert settings.MODEL_STARTUP_SMOKE_TEST is True
    assert settings.EFFNETB0_MODEL_ARTIFACT_URL.endswith("effnetb0/effnetb0_epoch_008.pth")
    assert settings.VITB16_MODEL_ARTIFACT_URL.endswith("vit_b_16/vit_b_16_epoch_018.pth")


def test_production_uses_default_hugging_face_model_artifact_source() -> None:
    settings = settings_without_env(APP_ENVIRONMENT="production")

    assert settings.APP_ENVIRONMENT == "production"
    assert settings.HF_MODEL_REPOSITORY is None
    assert settings.HF_MODEL_FILENAME is None


def test_production_accepts_complete_hugging_face_model_artifact_source() -> None:
    settings = settings_without_env(
        APP_ENVIRONMENT=" production ",
        HF_MODEL_REPOSITORY=" owner/repo ",
        HF_MODEL_REVISION=" abc123 ",
        HF_MODEL_FILENAME=" weights/model.pth ",
    )

    assert settings.APP_ENVIRONMENT == "production"
    assert settings.HF_MODEL_REPOSITORY == "owner/repo"
    assert settings.HF_MODEL_REVISION == "abc123"
    assert settings.HF_MODEL_FILENAME == "weights/model.pth"


def test_model_slugs_defaults_to_single_model_slug() -> None:
    settings = settings_without_env(MODEL_SLUG=ModelSlug.VITB16)

    assert settings.model_slugs == (ModelSlug.VITB16,)


def test_model_slugs_parses_comma_separated_values() -> None:
    settings = settings_without_env(MODEL_SLUGS="effnetb0, vitb16")

    assert settings.model_slugs == (ModelSlug.EFFNETB0, ModelSlug.VITB16)


def test_multi_runtime_artifact_paths_are_slug_scoped() -> None:
    settings = settings_without_env(
        MODEL_SLUGS="effnetb0,vitb16",
        MODEL_ARTIFACT_PATH=Path("/models/model.pth"),
    )

    assert settings.artifact_path_for_slug(ModelSlug.EFFNETB0) == Path("/models/effnetb0.pth")
    assert settings.artifact_path_for_slug(ModelSlug.VITB16) == Path("/models/vitb16.pth")
