from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

import torch.nn as nn
import torchvision
from torchvision.transforms import InterpolationMode

from src.runtime import ImageTransform
from src.types import ModelSlug


@dataclass(frozen=True)
class ModelSpec:
    """Architecture and transform factory for one deployable Model Runtime."""

    slug: ModelSlug
    build_model: Callable[[int], nn.Module]
    build_transform: Callable[[], ImageTransform]
    input_shape: tuple[int, ...] = (3, 224, 224)


def build_effnetb0_model(num_classes: int) -> nn.Module:
    model = torchvision.models.efficientnet_b0(weights=None)
    classifier_head = model.classifier[-1]
    if not isinstance(classifier_head, nn.Linear):
        raise TypeError(f"Expected nn.Linear classifier head, got {type(classifier_head)}")

    model.classifier = nn.Sequential(
        nn.Dropout(p=0.3, inplace=True),
        nn.Linear(in_features=classifier_head.in_features, out_features=num_classes),
    )
    return cast(nn.Module, model)


def build_vitb16_model(num_classes: int) -> nn.Module:
    model = torchvision.models.vit_b_16(weights=None)
    original_classifier = next(
        (module for module in reversed(list(model.heads.modules())) if isinstance(module, nn.Linear)),
        None,
    )
    if original_classifier is None:
        raise TypeError(f"Expected nn.Linear inside model.heads, got {type(model.heads)}")

    model.heads = nn.Sequential(
        nn.Linear(in_features=original_classifier.in_features, out_features=num_classes),
    )
    return cast(nn.Module, model)


def build_effnetb0_transform() -> ImageTransform:
    return cast(
        ImageTransform,
        torchvision.transforms.Compose(
            [
                torchvision.transforms.Resize(256, interpolation=InterpolationMode.BICUBIC),
                torchvision.transforms.CenterCrop(224),
                torchvision.transforms.ToTensor(),
                torchvision.transforms.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225],
                ),
            ]
        ),
    )


def build_vitb16_transform() -> ImageTransform:
    return cast(
        ImageTransform,
        torchvision.transforms.Compose(
            [
                torchvision.transforms.Resize((224, 224), interpolation=InterpolationMode.BICUBIC),
                torchvision.transforms.ToTensor(),
                torchvision.transforms.Normalize(
                    mean=[0.485, 0.456, 0.406],
                    std=[0.229, 0.224, 0.225],
                ),
            ]
        ),
    )


MODEL_SPECS: dict[ModelSlug, ModelSpec] = {
    ModelSlug.EFFNETB0: ModelSpec(
        slug=ModelSlug.EFFNETB0,
        build_model=build_effnetb0_model,
        build_transform=build_effnetb0_transform,
    ),
    ModelSlug.VITB16: ModelSpec(
        slug=ModelSlug.VITB16,
        build_model=build_vitb16_model,
        build_transform=build_vitb16_transform,
    ),
}
