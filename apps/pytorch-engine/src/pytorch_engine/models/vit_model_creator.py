"""ViT model creator for transfer learning image classification.

Provides :func:`create_vit_model` which builds a pre-trained
ViT feature extractor with a configurable classifier head.
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
class VitB16Model:
    """Return type for :func:`create_vit_model`.

    Attributes:
        model: ViTB16 feature extractor with frozen backbone and
            a fresh classifier head.
        transforms: Image transforms matching the pre-trained weights.
    """

    model: nn.Module
    transforms: torchvision.transforms.Compose


# ---------------------------------------------------------------------------
# Model creation
# ---------------------------------------------------------------------------


def create_vit_model(
    num_classes: int = 3,
    transforms: torchvision.transforms.Compose | None = None,
    seed: int = 42,
) -> VitB16Model:
    """Create a ViTB16 feature extractor model and transforms.

    Loads pre-trained ImageNet weights, freezes the backbone, and replaces
    the head with a dropout → linear layer suitable for
    fine-tuning on *num_classes* target classes.

    Args:
        num_classes: Number of output classes in the head.
            Defaults to 3.
        transforms: Image transforms to apply. When ``None``, uses the
            default transforms that correspond to the pre-trained weights.
        seed: Random seed for reproducible head initialisation.
            Defaults to 42.

    Returns:
        An :class:`VitB16Model` instance containing the model
        and its matching transforms.

    Example::

        result = create_vit_model(num_classes=10, seed=0)
        model = result.model
        transforms = result.transforms
    """
    logger.info(
        "Creating VitB16Model model — num_classes=%d seed=%d",
        num_classes,
        seed,
    )

    # 1. Load pre-trained ViTB16 weights
    weights = torchvision.models.ViT_B_16_Weights.IMAGENET1K_SWAG_LINEAR_V1
    logger.info("Loaded pre-trained %s", weights.__class__.__name__)
    # 2. Get image transforms from weights, or use custom transforms if provided
    image_transforms = transforms or weights.transforms()

    # 3. Build model from pre-trained weights
    model = torchvision.models.vit_b_16(weights=weights)

    # 4. Freeze all backbone layers (only head trains during fine-tuning)
    frozen_count = 0
    for param in model.parameters():
        param.requires_grad = False
        frozen_count += 1
    logger.info("Frozen %d parameter groups in backbone", frozen_count)

    # 5. Seed for reproducible head initialisation
    set_seeds(seed=seed)

    # 6. Replace head — extract in_features dynamically
    model_heads_classifier = model.heads
    logger.info("Original head: %s", model_heads_classifier)
    model.heads = nn.Sequential(
        nn.Linear(
            in_features=768,  # keep this the same as original model
            out_features=num_classes,
        )
    )  # update to reflect target number of classes
    logger.info(
        "Replaced head: in_features=%d → out_features=%d",
        768,
        num_classes,
    )

    # 7. Count trainable vs total parameters
    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    logger.info(
        "VitB16Model model ready — %d trainable / %d total parameters",
        trainable,
        total,
    )

    return VitB16Model(model=model, transforms=image_transforms)
