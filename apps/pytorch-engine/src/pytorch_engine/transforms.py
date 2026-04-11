"""Image transform pipelines for PyTorch models."""

from __future__ import annotations

from torchvision import transforms

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]
DEFAULT_IMAGE_SIZE: tuple[int, int] = (224, 224)


def get_default_transform(
    image_size: tuple[int, int] = DEFAULT_IMAGE_SIZE,
) -> transforms.Compose:
    """ImageNet-normalised resize + to-tensor pipeline."""
    return transforms.Compose(
        [
            transforms.Resize(image_size),
            transforms.ToTensor(),
            transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
        ]
    )


def get_train_transform(
    image_size: tuple[int, int] = DEFAULT_IMAGE_SIZE,
    normalize_mean: list[float] | None = None,
    normalize_std: list[float] | None = None,
) -> transforms.Compose:
    """Training image transform pipeline with augmentation.

    Args:
        image_size: Target image size (width, height).
        normalize_mean: Mean for normalization. Defaults to ImageNet mean.
        normalize_std: Std for normalization. Defaults to ImageNet std.

    Returns:
        Composed transform pipeline with augmentation.
    """
    return transforms.Compose(
        [
            transforms.Resize(image_size),
            transforms.RandomHorizontalFlip(),
            transforms.RandomVerticalFlip(),
            transforms.RandomRotation(20),
            transforms.ColorJitter(brightness=0.1, contrast=0.1, hue=0.1),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=normalize_mean if normalize_mean is not None else IMAGENET_MEAN,
                std=normalize_std if normalize_std is not None else IMAGENET_STD,
            ),
        ]
    )
