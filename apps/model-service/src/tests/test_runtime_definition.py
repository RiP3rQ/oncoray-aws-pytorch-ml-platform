from __future__ import annotations

from pathlib import Path
from typing import cast

import torch.nn as nn
import torchvision

from src.config import Settings
from src.model_specs import ModelSpec
from src.runtime import ImageTransform
from src.runtime_definition import ModelRuntimeDefinition
from src.types import ModelSlug


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
    settings = Settings(
        MODEL_SLUG=ModelSlug.VITB16,
        MODEL_ARTIFACT_PATH=Path("/models/vitb16.pth"),
        HF_MODEL_REPOSITORY="owner/vitb16",
        HF_MODEL_REVISION="abc123",
        HF_MODEL_FILENAME="weights/vitb16.pth",
        HF_TOKEN="secret-token",
        MODEL_ARTIFACT_SHA256="0" * 64,
        MODEL_DEVICE="cpu",
        MODEL_NUM_THREADS=2,
        MODEL_CLASS_NAMES="NORMAL,PNEUMONIA",
        MODEL_STRICT_LOAD=False,
        MODEL_STARTUP_SMOKE_TEST=False,
    )

    definition = ModelRuntimeDefinition.from_settings(settings, {ModelSlug.VITB16: make_spec(ModelSlug.VITB16)})

    assert definition.slug == ModelSlug.VITB16
    assert definition.spec.slug == ModelSlug.VITB16
    assert definition.artifact_path == Path("/models/vitb16.pth")
    assert definition.artifact_source is not None
    assert definition.artifact_source.repo_id == "owner/vitb16"
    assert definition.artifact_source.revision == "abc123"
    assert definition.artifact_source.filename == "weights/vitb16.pth"
    assert definition.artifact_source.token == "secret-token"
    assert definition.artifact_sha256 == "0" * 64
    assert definition.device_name == "cpu"
    assert definition.num_threads == 2
    assert definition.class_names == ("NORMAL", "PNEUMONIA")
    assert definition.strict_load is False
    assert definition.startup_smoke_test is False


def test_runtime_definition_rejects_spec_slug_mismatch() -> None:
    settings = Settings(MODEL_SLUG=ModelSlug.EFFNETB0)

    try:
        ModelRuntimeDefinition.from_settings(settings, {ModelSlug.EFFNETB0: make_spec(ModelSlug.VITB16)})
    except ValueError as exc:
        message = str(exc)
    else:
        raise AssertionError("Expected ModelSpec slug mismatch.")

    assert "ModelSpec slug mismatch" in message
