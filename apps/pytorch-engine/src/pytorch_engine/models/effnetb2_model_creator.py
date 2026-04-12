"""EfficientNetB2 model creator for transfer learning image classification.

Provides :func:`create_effnetb2_model` which builds a pre-trained
EfficientNetB2 feature extractor with a configurable classifier head.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import torch.nn as nn
import torchvision

from pytorch_engine import set_seeds

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class EfficientNetB2Model:
    """Return type for :func:`create_effnetb2_model`.

    Attributes:
        model: EffNetB2 model with a fresh classifier head and optional
            partial fine-tuning.
        transforms: Image transforms matching the pre-trained weights.
    """

    model: nn.Module
    transforms: torchvision.transforms.Compose


# ---------------------------------------------------------------------------
# Model creation
# ---------------------------------------------------------------------------


def create_effnetb2_model(
    num_classes: int = 3,
    transforms: torchvision.transforms.Compose | None = None,
    seed: int = 42,
    dropout_p: float = 0.3,
    trainable_feature_blocks: int = 0,
) -> EfficientNetB2Model:
    """Create an EfficientNetB2 feature extractor model and transforms.

    Loads pre-trained ImageNet weights, freezes the backbone, replaces the
    classifier head, and optionally unfreezes the last feature blocks for
    partial fine-tuning.

    Args:
        num_classes: Number of output classes in the classifier head.
        transforms: Image transforms to apply. When ``None``, uses the
            default transforms that correspond to the pre-trained weights.
        seed: Random seed for reproducible classifier head initialisation.
        dropout_p: Dropout probability in the classifier head.
        trainable_feature_blocks: Number of trailing EfficientNet feature
            blocks to unfreeze for fine-tuning.

    Returns:
        An :class:`EfficientNetB2Model` instance containing the model
        and its matching transforms.
    """
    logger.info(
        "Creating EffNetB2 model - num_classes=%d seed=%d dropout_p=%.2f trainable_feature_blocks=%d",
        num_classes,
        seed,
        dropout_p,
        trainable_feature_blocks,
    )

    # 1. Load pre-trained EffNetB2 weights
    weights = torchvision.models.EfficientNet_B2_Weights.IMAGENET1K_V1
    logger.info("Loaded pre-trained %s", weights.__class__.__name__)

    # 2. Get image transforms from weights, or use custom transforms if provided
    image_transforms = transforms or weights.transforms()
    # 3. Build model from pre-trained weights
    model = torchvision.models.efficientnet_b2(weights=weights)

    # 4. Freeze all backbone layers (only classifier trains during fine-tuning)
    frozen_count = 0
    for param in model.parameters():
        param.requires_grad = False
        frozen_count += 1
    logger.info("Frozen %d parameter groups in backbone", frozen_count)

    # 5. Seed for reproducible classifier head initialisation
    set_seeds(seed=seed)

    # 6. Replace classifier head — extract in_features dynamically
    #    classifier[-1] is typed as Module | Tensor; we know it's nn.Linear
    classifier_head = model.classifier[-1]
    assert isinstance(classifier_head, nn.Linear), (
        f"Expected nn.Linear as last classifier layer, got {type(classifier_head)}"
    )
    in_features = classifier_head.in_features
    # Replace the ImageNet classifier head with one sized for HAM10000 labels.
    model.classifier = nn.Sequential(
        nn.Dropout(p=dropout_p, inplace=True),
        nn.Linear(in_features=in_features, out_features=num_classes),
    )
    logger.info(
        "Replaced classifier head: in_features=%d → out_features=%d",
        in_features,
        num_classes,
    )

    # 7. Count trainable vs total parameters
    feature_blocks = list(model.features.children())
    if trainable_feature_blocks < 0:
        raise ValueError("trainable_feature_blocks must be >= 0")
    if trainable_feature_blocks > len(feature_blocks):
        raise ValueError(
            f"trainable_feature_blocks={trainable_feature_blocks} exceeds available blocks={len(feature_blocks)}"
        )

    if trainable_feature_blocks:
        # Unfreezing only the last blocks is a common transfer-learning middle
        # ground: more flexibility than head-only training, less overfitting
        # risk than unfreezing the full backbone immediately.
        for block in feature_blocks[-trainable_feature_blocks:]:
            for param in block.parameters():
                param.requires_grad = True

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    logger.info(
        "EffNetB2 model ready - %d trainable / %d total parameters",
        trainable,
        total,
    )

    return EfficientNetB2Model(model=model, transforms=image_transforms)
