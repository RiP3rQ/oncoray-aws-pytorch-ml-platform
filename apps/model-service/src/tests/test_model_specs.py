from __future__ import annotations

from typing import cast

import torch
import torch.nn as nn
from PIL import Image

from src.model_specs import MODEL_SPECS
from src.types import ModelSlug


def last_linear(module: nn.Module) -> nn.Linear:
    for child in reversed(list(module.modules())):
        if isinstance(child, nn.Linear):
            return child
    raise AssertionError(f"Expected nn.Linear inside {type(module)}.")


def test_model_specs_cover_supported_model_slugs() -> None:
    assert set(MODEL_SPECS) == set(ModelSlug)
    for slug, spec in MODEL_SPECS.items():
        assert spec.slug == slug


def test_model_specs_build_classifier_heads_for_requested_class_count() -> None:
    num_classes = 2

    effnet = MODEL_SPECS[ModelSlug.EFFNETB0].build_model(num_classes)
    vit = MODEL_SPECS[ModelSlug.VITB16].build_model(num_classes)

    assert last_linear(effnet).out_features == num_classes
    assert last_linear(vit).out_features == num_classes


def test_model_specs_build_image_transforms_with_expected_shape() -> None:
    image = Image.new("RGB", (320, 256), color=(128, 128, 128))

    for spec in MODEL_SPECS.values():
        transformed = spec.build_transform()(image)

        assert isinstance(transformed, torch.Tensor)
        assert cast(tuple[int, ...], transformed.shape) == spec.input_shape
        assert transformed.dtype == torch.float32
