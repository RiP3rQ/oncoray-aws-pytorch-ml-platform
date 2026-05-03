from __future__ import annotations

from pathlib import Path

import pytest

import src.config as config
from src.config import Settings, validate_production_settings
from src.types import ModelSlug


def settings_without_env(**overrides: object) -> Settings:
    return Settings(**overrides, _env_file=None)  # type: ignore[call-arg,arg-type]


def test_development_allows_local_model_artifact_only() -> None:
    settings = settings_without_env(APP_ENVIRONMENT="development")

    assert settings.APP_ENVIRONMENT == "development"
    assert settings.MODEL_STARTUP_SMOKE_TEST is True
    assert settings.model_slugs == (ModelSlug.EFFNETB0, ModelSlug.VITB16)
    assert settings.EFFNETB0_MODEL_ARTIFACT_URL.endswith("effnetb0/effnetb0_epoch_008.pth")
    assert settings.VITB16_MODEL_ARTIFACT_URL.endswith("vit_b_16/vit_b_16_epoch_018.pth")
    assert settings.HF_TOKEN is None
    assert settings.HF_USERNAME == "RiP3rQ"


def test_production_uses_same_minimal_runtime_defaults() -> None:
    settings = settings_without_env(APP_ENVIRONMENT="production")

    assert settings.APP_ENVIRONMENT == "production"
    assert settings.model_slugs == (ModelSlug.EFFNETB0, ModelSlug.VITB16)


def test_production_validation_rejects_mutable_main_artifacts() -> None:
    settings = settings_without_env(APP_ENVIRONMENT="production")

    with pytest.raises(RuntimeError, match="immutable Hugging Face revision"):
        validate_production_settings(settings)


def test_production_validation_accepts_pinned_artifacts() -> None:
    settings = settings_without_env(
        APP_ENVIRONMENT="production",
        EFFNETB0_MODEL_ARTIFACT_URL=(
            "https://huggingface.co/RiP3rQ/effnetb0/resolve/abc123/effnetb0/effnetb0_epoch_008.pth"
        ),
        VITB16_MODEL_ARTIFACT_URL=(
            "https://huggingface.co/RiP3rQ/vit_b_16/resolve/def456/vit_b_16/vit_b_16_epoch_018.pth"
        ),
        HF_USERNAME="RiP3rQ",
        HF_TOKEN="token",
    )

    validate_production_settings(settings)


def test_model_slugs_defaults_to_single_model_slug() -> None:
    settings = settings_without_env(MODEL_SLUGS="vitb16")

    assert settings.model_slugs == (ModelSlug.VITB16,)


def test_model_slugs_parses_comma_separated_values() -> None:
    settings = settings_without_env(MODEL_SLUGS="effnetb0, vitb16")

    assert settings.model_slugs == (ModelSlug.EFFNETB0, ModelSlug.VITB16)


def test_multi_runtime_artifact_paths_are_slug_scoped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "DEFAULT_ARTIFACT_PATH", Path("/models/model.pth"))
    settings = settings_without_env(MODEL_SLUGS="effnetb0,vitb16")

    assert settings.artifact_path_for_slug(ModelSlug.EFFNETB0) == Path("/models/effnetb0.pth")
    assert settings.artifact_path_for_slug(ModelSlug.VITB16) == Path("/models/vitb16.pth")
