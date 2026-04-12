"""EfficientNetB0 model creator for transfer learning image classification.

Provides :func:`create_effnetb0_model` which builds a pre-trained
EfficientNetB0 feature extractor with a configurable classifier head.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import torch.nn as nn
import torchvision

from pytorch_engine import set_seeds

logger = logging.getLogger(__name__)


@dataclass
class EfficientNetB0Model:
    """Return type for :func:`create_effnetb0_model`.

    Attributes:
        model: EffNetB0 model with a fresh classifier head and frozen backbone.
        transforms: Image transforms matching the pre-trained weights.
    """

    model: nn.Module
    transforms: torchvision.transforms.Compose


def create_effnetb0_model(
    num_classes: int = 3,
    transforms: torchvision.transforms.Compose | None = None,
    seed: int = 42,
    dropout_p: float = 0.3,
) -> EfficientNetB0Model:
    """Create an EfficientNetB0 feature extractor model and transforms.

    Loads pre-trained ImageNet weights, freezes the full backbone, and replaces
    the classifier head so only the final output layer is trainable.

    Args:
        num_classes: Number of output classes in the classifier head.
        transforms: Image transforms to apply. When ``None``, uses the
            default transforms that correspond to the pre-trained weights.
        seed: Random seed for reproducible classifier head initialisation.
        dropout_p: Dropout probability in the classifier head.

    Returns:
        An :class:`EfficientNetB0Model` instance containing the model
        and its matching transforms.
    """
    logger.info(
        "Creating EffNetB0 model - num_classes=%d seed=%d dropout_p=%.2f classifier_only=True",
        num_classes,
        seed,
        dropout_p,
    )

    weights = torchvision.models.EfficientNet_B0_Weights.IMAGENET1K_V1
    logger.info("Loaded pre-trained %s", weights.__class__.__name__)

    image_transforms = transforms or weights.transforms()
    model = torchvision.models.efficientnet_b0(weights=weights)

    frozen_count = 0
    for param in model.parameters():
        param.requires_grad = False
        frozen_count += 1
    logger.info("Frozen %d parameter groups in backbone", frozen_count)

    set_seeds(seed=seed)

    classifier_head = model.classifier[-1]
    assert isinstance(classifier_head, nn.Linear), (
        f"Expected nn.Linear as last classifier layer, got {type(classifier_head)}"
    )
    in_features = classifier_head.in_features
    model.classifier = nn.Sequential(
        nn.Dropout(p=dropout_p, inplace=True),
        nn.Linear(in_features=in_features, out_features=num_classes),
    )
    logger.info(
        "Replaced classifier head: in_features=%d -> out_features=%d",
        in_features,
        num_classes,
    )

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    logger.info(
        "EffNetB0 model ready - %d trainable / %d total parameters",
        trainable,
        total,
    )

    return EfficientNetB0Model(model=model, transforms=image_transforms)
