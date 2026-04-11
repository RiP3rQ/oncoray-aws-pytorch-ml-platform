"""PyTorch DataLoader creation for image classification datasets."""

import os
from typing import TypedDict

from torch.utils.data import DataLoader
from torchvision import datasets, transforms

NUM_WORKERS: int | None = os.cpu_count()


class DataLoadersResult(TypedDict):
    """Return type for :func:`create_dataloaders`.

    Attributes:
        train_dataloader: DataLoader iterating over shuffled training batches.
        test_dataloader: DataLoader iterating over ordered test batches.
        class_names: Ordered list of class labels derived from subdirectory names.
    """

    train_dataloader: DataLoader
    test_dataloader: DataLoader
    class_names: list[str]


def create_dataloaders(
    train_dir: str,
    test_dir: str,
    transform: transforms.Compose,
    batch_size: int,
    num_workers: int = NUM_WORKERS or 1,
) -> DataLoadersResult:
    """Create training and test DataLoaders from directory-structured image data.

    Expects data organised as::

        root/class_a/img1.png
        root/class_b/img2.png

    Uses :class:`~torchvision.datasets.ImageFolder` to infer class labels
    from subdirectory names.

    Args:
        train_dir: Path to the training image directory.
        test_dir: Path to the test image directory.
        transform: Torchvision transforms applied to every image.
        batch_size: Number of samples per batch.
        num_workers: Subprocess count for data loading. Defaults to
            ``os.cpu_count()`` or 1.

    Returns:
        A :class:`DataLoadersResult` dict with keys
        ``"train_dataloader"``, ``"test_dataloader"``, and ``"class_names"``.

    Example::

        result = create_dataloaders(
            train_dir="data/train",
            test_dir="data/test",
            transform=some_transform,
            batch_size=32,
            num_workers=4,
        )
        train_dl = result["train_dataloader"]
    """
    train_data = datasets.ImageFolder(root=train_dir, transform=transform)
    test_data = datasets.ImageFolder(root=test_dir, transform=transform)

    class_names: list[str] = train_data.classes

    train_dataloader = DataLoader(
        train_data,
        batch_size=batch_size,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=True,
    )
    test_dataloader = DataLoader(
        test_data,
        batch_size=batch_size,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=True,
    )

    return DataLoadersResult(
        train_dataloader=train_dataloader,
        test_dataloader=test_dataloader,
        class_names=class_names,
    )
