"""ViT model creator for transfer learning image classification.

Provides :func:`create_vit_model` which builds a pre-trained ViT model with a
configurable classifier head and optional partial fine-tuning.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import torch.nn as nn
import torchvision

from pytorch_engine.utils import set_seeds

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------


@dataclass
class VitB16Model:
    """Return type for :func:`create_vit_model`.

    Attributes:
        model: ViTB16 model with a fresh classifier head and optional
            partially unfrozen encoder blocks.
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
    trainable_encoder_blocks: int = 0,
) -> VitB16Model:
    """Create a ViTB16 transfer-learning model and matching transforms.

    Loads pre-trained ImageNet weights, freezes the full model, replaces the
    classifier head, and optionally unfreezes the last encoder blocks for
    partial fine-tuning.

    Args:
        num_classes: Number of output classes in the classifier head.
        transforms: Optional custom transforms. When ``None``, use the default
            transforms that match the pre-trained weights.
        seed: Random seed for reproducible head initialisation.
        trainable_encoder_blocks: Number of final transformer encoder blocks
            to unfreeze. ``0`` keeps the backbone frozen.

    Returns:
        A :class:`VitB16Model` instance containing the model and transforms.
    """
    logger.info(
        "Creating VitB16 model - num_classes=%d seed=%d trainable_encoder_blocks=%d",
        num_classes,
        seed,
        trainable_encoder_blocks,
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
    logger.info("Frozen %d parameter groups in ViT backbone", frozen_count)

    # 5. Seed for reproducible head initialisation
    set_seeds(seed=seed)

    original_classifier = next(
        (module for module in reversed(list(model.heads.modules())) if isinstance(module, nn.Linear)),
        None,
    )
    if original_classifier is None:
        raise TypeError(f"Expected nn.Linear inside model.heads, got {type(model.heads)}")

    in_features = original_classifier.in_features
    model.heads = nn.Sequential(
        nn.Linear(in_features=in_features, out_features=num_classes),
    )

    if trainable_encoder_blocks > 0:
        encoder_layers = getattr(model.encoder, "layers", None)
        if encoder_layers is None:
            raise AttributeError("ViT encoder does not expose encoder layers for partial fine-tuning.")

        encoder_blocks = list(encoder_layers.children())
        available_blocks = len(encoder_blocks)
        blocks_to_unfreeze = min(trainable_encoder_blocks, available_blocks)

        for encoder_block in encoder_blocks[-blocks_to_unfreeze:]:
            for param in encoder_block.parameters():
                param.requires_grad = True

        encoder_ln = getattr(model.encoder, "ln", None)
        if isinstance(encoder_ln, nn.Module):
            for param in encoder_ln.parameters():
                param.requires_grad = True

        class_token = getattr(model, "class_token", None)
        if isinstance(class_token, nn.Parameter):
            class_token.requires_grad = True

        pos_embedding = getattr(model.encoder, "pos_embedding", None)
        if isinstance(pos_embedding, nn.Parameter):
            pos_embedding.requires_grad = True

        logger.info("Unfroze last %d/%d ViT encoder blocks", blocks_to_unfreeze, available_blocks)

    logger.info("Replaced head: in_features=%d -> out_features=%d", in_features, num_classes)

    trainable = sum(p.numel() for p in model.parameters() if p.requires_grad)
    total = sum(p.numel() for p in model.parameters())
    logger.info("VitB16 model ready - %d trainable / %d total parameters", trainable, total)

    return VitB16Model(model=model, transforms=image_transforms)
