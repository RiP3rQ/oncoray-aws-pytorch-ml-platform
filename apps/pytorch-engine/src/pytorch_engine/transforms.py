"""Image transform pipelines for PyTorch models."""

from __future__ import annotations

from typing import Any

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


def get_simple_train_transform(
    image_size: tuple[int, int] = DEFAULT_IMAGE_SIZE,
    normalize_mean: list[float] | None = None,
    normalize_std: list[float] | None = None,
    interpolation: transforms.InterpolationMode = DEFAULT_INTERPOLATION,
    rotation_degrees: float = 7.0,
    horizontal_flip_probability: float = 0.5,
) -> transforms.Compose:
    """Training transform with light augmentation for clean transfer-learning runs.

    This keeps the pipeline readable for beginner notebooks: a small crop
    jitter, an optional horizontal flip, a small rotation, then tensor
    conversion and normalization.
    """
    return transforms.Compose(
        [
            transforms.RandomResizedCrop(
                image_size,
                scale=(0.9, 1.0),
                ratio=(0.95, 1.05),
                interpolation=interpolation,
                antialias=True,
            ),
            transforms.RandomHorizontalFlip(p=horizontal_flip_probability),
            transforms.RandomRotation(
                degrees=rotation_degrees,
                interpolation=interpolation,
                fill=0,
            ),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=normalize_mean if normalize_mean is not None else IMAGENET_MEAN,
                std=normalize_std if normalize_std is not None else IMAGENET_STD,
            ),
        ]
    )


def get_chest_xray_train_transform(
    image_size: tuple[int, int] = DEFAULT_IMAGE_SIZE,
    resize_size: tuple[int, int] = (256, 256),
    normalize_mean: list[float] | None = None,
    normalize_std: list[float] | None = None,
    interpolation: transforms.InterpolationMode = DEFAULT_INTERPOLATION,
    rotation_degrees: float = 7.0,
    translate: tuple[float, float] = (0.02, 0.02),
    scale: tuple[float, float] = (0.95, 1.05),
    brightness: float = 0.08,
    contrast: float = 0.12,
) -> transforms.Compose:
    """Training transform tuned for chest X-ray transfer learning.

    Chest X-rays are medically structured images, so we avoid horizontal
    flips and aggressive random crops that can remove diagnostic anatomy.
    The pipeline keeps framing close to evaluation preprocessing while adding
    small geometric and intensity perturbations for regularization.
    """
    return transforms.Compose(
        [
            transforms.Resize(resize_size, interpolation=interpolation, antialias=True),
            transforms.RandomCrop(image_size),
            transforms.RandomApply(
                [
                    transforms.RandomAffine(
                        degrees=rotation_degrees,
                        translate=translate,
                        scale=scale,
                        interpolation=interpolation,
                        fill=0,
                    )
                ],
                p=0.8,
            ),
            transforms.RandomApply(
                [
                    transforms.ColorJitter(
                        brightness=brightness,
                        contrast=contrast,
                        saturation=0.0,
                        hue=0.0,
                    )
                ],
                p=0.35,
            ),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=normalize_mean if normalize_mean is not None else IMAGENET_MEAN,
                std=normalize_std if normalize_std is not None else IMAGENET_STD,
            ),
        ]
    )


def get_train_transform(
    image_size: tuple[int, int] = DEFAULT_IMAGE_SIZE,
    normalize_mean: list[float] | None = None,
    normalize_std: list[float] | None = None,
    interpolation: transforms.InterpolationMode = DEFAULT_INTERPOLATION,
    use_random_erasing: bool = False,
    blur_probability: float = 0.1,
) -> transforms.Compose:
    """Training image transform pipeline with conservative augmentation.

    Args:
        image_size: Target image size (width, height).
        normalize_mean: Mean for normalization. Defaults to ImageNet mean.
        normalize_std: Std for normalization. Defaults to ImageNet std.
        interpolation: Resize interpolation method.
        use_random_erasing: Whether to apply light random erasing after
            normalization. Defaults to ``False`` for conservative medical-image
            training.
        blur_probability: Probability of applying slight Gaussian blur to mimic
            benign focus/lighting variation while preserving lesion structure.

    Returns:
        Composed transform pipeline with augmentation.
    """
    transform_steps: list[Any] = [
        # Keep crops close to the original framing so the lesion is rarely
        # cropped out, but still vary scale/position enough to fight memorising
        # small development subsets.
        transforms.RandomResizedCrop(
            image_size,
            scale=(0.9, 1.0),
            ratio=(0.95, 1.05),
            interpolation=interpolation,
            antialias=True,
        ),
        # Dermoscopy images are not orientation-sensitive in the same way as
        # natural scenes, so flips and small rotations are usually safe.
        transforms.RandomHorizontalFlip(p=0.5),
        transforms.RandomVerticalFlip(p=0.5),
        transforms.RandomApply(
            [
                transforms.RandomAffine(
                    degrees=20,
                    translate=(0.05, 0.05),
                    scale=(0.95, 1.05),
                    interpolation=interpolation,
                    fill=0,
                )
            ],
            p=0.7,
        ),
        transforms.RandomApply(
            [transforms.ColorJitter(brightness=0.15, contrast=0.15, saturation=0.08, hue=0.02)],
            p=0.5,
        ),
        transforms.RandomApply(
            [transforms.GaussianBlur(kernel_size=3, sigma=(0.1, 1.0))],
            p=blur_probability,
        ),
        transforms.ToTensor(),
        # Normalization must match the pretrained backbone statistics.
        transforms.Normalize(
            mean=normalize_mean if normalize_mean is not None else IMAGENET_MEAN,
            std=normalize_std if normalize_std is not None else IMAGENET_STD,
        ),
    ]
    if use_random_erasing:
        # Keep erasing light and shape-constrained because lesions are
        # diagnostic targets; this is meant to regularise background/context
        # reliance, not delete the lesion entirely.
        transform_steps.append(
            transforms.RandomErasing(
                p=0.15,
                scale=(0.01, 0.05),
                ratio=(0.8, 1.25),
                value="random",
            )
        )

    return transforms.Compose(transform_steps)
