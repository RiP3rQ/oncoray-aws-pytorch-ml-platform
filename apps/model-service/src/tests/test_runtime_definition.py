from __future__ import annotations

from pathlib import Path
from typing import cast

import torch.nn as nn
import torchvision

from src.config import Settings
from src.model_specs import ModelSpec
from src.runtime import ImageTransform
from src.runtime_definition import (
    ModelRuntimeDefinition,
    hugging_face_source_from_settings,
    hugging_face_source_from_url,
    model_artifact_url_from_settings,
)
from src.types import ModelSlug


def settings_without_env(**overrides: object) -> Settings:
    return Settings(**overrides, _env_file=None)  # type: ignore[call-arg,arg-type]


def build_identity_model(num_classes: int) -> nn.Module:
    return nn.Linear(2, num_classes)


def build_identity_transform() -> ImageTransform:
    return cast(ImageTransform, torchvision.transforms.ToTensor())


def make_spec(slug: ModelSlug) -> ModelSpec:
    return ModelSpec(
        slug=slug,
        build_model=build_identity_model,
        build_transform=build_identity_transform,
        input_shape=(2,),
    )


def test_runtime_definition_collects_deploy_recipe_from_settings() -> None:
    settings = settings_without_env(
        MODEL_SLUGS="vitb16",
        MODEL_ARTIFACT_PATH=Path("/models/vitb16.pth"),
        MODEL_DEVICE="cpu",
        MODEL_NUM_THREADS=2,
        MODEL_CLASS_NAMES="NORMAL,PNEUMONIA",
        MODEL_STRICT_LOAD=False,
        MODEL_STARTUP_SMOKE_TEST=False,
        VITB16_MODEL_ARTIFACT_SHA256="b" * 64,
        HF_TOKEN="secret-token",
    )

    definition = ModelRuntimeDefinition.from_settings(settings, {ModelSlug.VITB16: make_spec(ModelSlug.VITB16)})

    assert definition.slug == ModelSlug.VITB16
    assert definition.spec.slug == ModelSlug.VITB16
    assert definition.artifact_path == Path("/models/vitb16.pth")
    assert definition.artifact_source is not None
    assert definition.artifact_source.repo_id == "RiP3rQ/vit_b_16"
    assert definition.artifact_source.filename == "vit_b_16/vit_b_16_epoch_018.pth"
    assert definition.artifact_source.token == "secret-token"
    assert definition.artifact_sha256 == "b" * 64
    assert definition.device_name == "cpu"
    assert definition.num_threads == 2
    assert definition.class_names == ("NORMAL", "PNEUMONIA")
    assert definition.strict_load is False
    assert definition.startup_smoke_test is False


def test_runtime_definition_uses_configured_model_artifact_urls() -> None:
    settings = settings_without_env(
        EFFNETB0_MODEL_ARTIFACT_URL="https://huggingface.co/acme/effnet/resolve/main/weights/effnet.pth",
        VITB16_MODEL_ARTIFACT_URL="https://huggingface.co/acme/vit/resolve/main/weights/vit.pth",
        HF_TOKEN="secret-token",
    )

    assert model_artifact_url_from_settings(settings, ModelSlug.EFFNETB0).endswith("weights/effnet.pth")
    assert model_artifact_url_from_settings(settings, ModelSlug.VITB16).endswith("weights/vit.pth")
    assert hugging_face_source_from_settings(settings, ModelSlug.EFFNETB0).token == "secret-token"


def test_hugging_face_source_from_url_parses_resolve_url() -> None:
    source = hugging_face_source_from_url(
        "https://huggingface.co/RiP3rQ/vit_b_16/resolve/main/vit_b_16/vit_b_16_epoch_018.pth",
        token="secret-token",
    )

    assert source.repo_id == "RiP3rQ/vit_b_16"
    assert source.revision == "main"
    assert source.filename == "vit_b_16/vit_b_16_epoch_018.pth"
    assert source.token == "secret-token"


def test_runtime_definition_rejects_spec_slug_mismatch() -> None:
    settings = settings_without_env(MODEL_SLUGS="effnetb0")

    try:
        ModelRuntimeDefinition.from_settings(settings, {ModelSlug.EFFNETB0: make_spec(ModelSlug.VITB16)})
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected ModelSpec slug mismatch.")

    assert "ModelSpec slug mismatch" in message
