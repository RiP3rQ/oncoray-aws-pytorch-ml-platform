"""Image transform pipelines for PyTorch models."""

from __future__ import annotations

from torchvision import transforms

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]
DEFAULT_IMAGE_SIZE: tuple[int, int] = (224, 224)
DEFAULT_INTERPOLATION = transforms.InterpolationMode.BICUBIC


def get_default_transform(
    image_size: tuple[int, int] = DEFAULT_IMAGE_SIZE,
    interpolation: transforms.InterpolationMode = DEFAULT_INTERPOLATION,
) -> transforms.Compose:
    """ImageNet-normalised resize + to-tensor pipeline."""
    return transforms.Compose(
        [
            # Validation/test data should stay deterministic so metrics reflect
            # model quality, not random augmentation noise.
            transforms.Resize(image_size, interpolation=interpolation, antialias=True),
            transforms.ToTensor(),
            transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ]
    )


def get_train_transform(
    image_size: tuple[int, int] = DEFAULT_IMAGE_SIZE,
    normalize_mean: list[float] | None = None,
    normalize_std: list[float] | None = None,
    interpolation: transforms.InterpolationMode = DEFAULT_INTERPOLATION,
) -> transforms.Compose:
    """Training image transform pipeline with conservative augmentation.

    Args:
        image_size: Target image size (width, height).
        normalize_mean: Mean for normalization. Defaults to ImageNet mean.
        normalize_std: Std for normalization. Defaults to ImageNet std.
        interpolation: Resize interpolation method.

    Returns:
        Composed transform pipeline with augmentation.
    """
    return transforms.Compose(
        [
            # RandomResizedCrop keeps output size fixed while varying framing,
            # which is more realistic than always resizing from identical bounds.
            transforms.RandomResizedCrop(
                image_size,
                scale=(0.85, 1.0),
                ratio=(0.9, 1.1),
                interpolation=interpolation,
                antialias=True,
            ),
            # Dermoscopy images are not orientation-sensitive in the same way as
            # natural scenes, so flips and small rotations are usually safe.
            transforms.RandomHorizontalFlip(),
            transforms.RandomVerticalFlip(),
            transforms.RandomRotation(15, interpolation=interpolation),
            transforms.ColorJitter(brightness=0.15, contrast=0.15, saturation=0.1, hue=0.02),
            transforms.ToTensor(),
            # Normalization must match the pretrained backbone statistics.
            transforms.Normalize(
                mean=normalize_mean if normalize_mean is not None else IMAGENET_MEAN,
                std=normalize_std if normalize_std is not None else IMAGENET_STD,
            ),
            # Avoid RandomErasing here because lesions are the diagnostic target;
            # masking them can destroy clinically relevant structure.
            # transforms.RandomErasing(p=0.15, scale=(0.02, 0.08), value="random"),
        ]
    )
