"""PyTorch DataLoader creation and data utilities for image classification datasets."""

import logging
import os
import zipfile
from pathlib import Path
from typing import TypedDict

import requests
from torch.utils.data import DataLoader
from torchvision import datasets, transforms

NUM_WORKERS: int | None = os.cpu_count()

logger = logging.getLogger(__name__)


def walk_through_dir(dir_path: str | Path) -> None:
    """Walk through *dir_path* and print the number of directories and images.

    Useful for inspecting image classification directory structures before
    creating data loaders.

    Args:
        dir_path: Target directory to inspect.

    Example::

        walk_through_dir("data/pizza_steak_sushi")
        # There are 2 directories and 750 images in 'data/pizza_steak_sushi'
    """
    for dirpath, dirnames, filenames in os.walk(dir_path):
        logger.info(
            "There are %d directories and %d images in '%s'",
            len(dirnames),
            len(filenames),
            dirpath,
        )


def download_data(
    source: str,
    destination: str,
    remove_source: bool = True,
) -> Path:
    """Download a zipped dataset from *source* and extract to *destination*.

    Creates ``data/<destination>`` if it does not exist, downloads the zip
    archive, extracts it, and optionally removes the downloaded zip.

    Args:
        source: URL pointing to a zipped file containing data.
        destination: Target directory name under ``data/``.
        remove_source: Whether to delete the zip after extraction.
            Defaults to ``True``.

    Returns:
        The :class:`~pathlib.Path` to the extracted data directory.

    Example::

        image_path = download_data(
            source="LINK_TO_ZIP_FILE",
            destination="pizza_steak_sushi",
        )
    """
    data_path = Path("data/")
    image_path = data_path / destination

    if image_path.is_dir():
        logger.info("%s directory exists, skipping download.", image_path)
    else:
        logger.info("Did not find %s directory, creating one…", image_path)
        image_path.mkdir(parents=True, exist_ok=True)

        target_file = Path(source).name
        with open(data_path / target_file, "wb") as f:
            logger.info("Downloading %s from %s…", target_file, source)
            f.write(requests.get(source).content)

        with zipfile.ZipFile(data_path / target_file, "r") as zip_ref:
            logger.info("Unzipping %s data…", target_file)
            zip_ref.extractall(image_path)

        if remove_source:
            os.remove(data_path / target_file)

    return image_path


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
