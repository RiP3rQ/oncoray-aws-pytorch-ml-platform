"""Image transform pipelines for PyTorch models."""

from torchvision import transforms

_IMAGENET_MEAN = [0.485, 0.456, 0.406]
_IMAGENET_STD = [0.229, 0.224, 0.225]
_DEFAULT_IMAGE_SIZE: tuple[int, int] = (224, 224)


def get_default_transform(image_size: tuple[int, int]) -> transforms.Compose:
    """ImageNet-normalised resize + to-tensor pipeline."""
    return transforms.Compose(
        [
            transforms.Resize(image_size),
            transforms.ToTensor(),
            transforms.Normalize(mean=_IMAGENET_MEAN, std=_IMAGENET_STD),
        ]
    )
