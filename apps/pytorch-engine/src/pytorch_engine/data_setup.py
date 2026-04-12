"""PyTorch DataLoader creation and data utilities for image classification datasets."""

import logging
import os
import shutil
import zipfile
from pathlib import Path
from typing import TypedDict

import requests
from torch.utils.data import DataLoader
from torchvision import datasets, transforms

NUM_WORKERS: int | None = os.cpu_count()

logger = logging.getLogger(__name__)


def prepare_kaggle_ham10000_dataset(
    zip_path: str | Path,
    destination: str | Path,
    remove_masks_dir: bool = True,
    remove_zip: bool = False,
) -> Path:
    """Extract Kaggle HAM10000 archive and normalize expected structure.

    Expected result inside *destination*:
      - ``images/`` (required for training)
      - ``GroundTruth.csv`` (metadata labels)
      - optional ``ATTRIBUTION.txt``
      - optional ``masks/`` (deleted when *remove_masks_dir* is True)
    """
    zip_path = Path(zip_path)
    destination_path = Path(destination)

    if not zip_path.is_file():
        raise FileNotFoundError(f"Dataset zip not found: {zip_path}")

    destination_path.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        logger.info("Extracting dataset '%s' to '%s'", zip_path, destination_path)
        zip_ref.extractall(destination_path)

    masks_path = destination_path / "masks"
    if remove_masks_dir and masks_path.exists():
        shutil.rmtree(masks_path)
        logger.info("Removed unused masks directory: %s", masks_path)

    images_path = destination_path / "images"
    csv_path = destination_path / "GroundTruth.csv"
    if not images_path.is_dir():
        raise FileNotFoundError(f"Expected images directory not found: {images_path}")
    if not csv_path.is_file():
        raise FileNotFoundError(f"Expected metadata CSV not found: {csv_path}")

    if remove_zip:
        zip_path.unlink(missing_ok=True)

    return destination_path


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


class DataLoaderResult(TypedDict):
    """Return type for :func:`create_dataloader`.

    Attributes:
        dataloader: DataLoader iterating over batches from the dataset.
        class_names: Ordered list of class labels derived from subdirectory names.
    """

    dataloader: DataLoader
    class_names: list[str]


def create_dataloader(
    data_dir: str,
    transform: transforms.Compose,
    batch_size: int,
    shuffle: bool = False,
    num_workers: int = NUM_WORKERS or 1,
) -> DataLoaderResult:
    """Create a single DataLoader from directory-structured image data.

    Expects data organised as::

        root/class_a/img1.png
        root/class_b/img2.png

    Uses :class:`~torchvision.datasets.ImageFolder` to infer class labels
    from subdirectory names.

    Args:
        data_dir: Path to the image directory.
        transform: Torchvision transforms applied to every image.
        batch_size: Number of samples per batch.
        shuffle: Whether to shuffle the data each epoch.
            Use ``True`` for training, ``False`` for validation/testing.
            Defaults to ``False``.
        num_workers: Subprocess count for data loading. Defaults to
            ``os.cpu_count()`` or 1.

    Returns:
        A :class:`DataLoaderResult` dict with keys
        ``"dataloader"`` and ``"class_names"``.

    Example::

        # Training loader (shuffled)
        train_result = create_dataloader(
            data_dir="data/train",
            transform=train_transform,
            batch_size=32,
            shuffle=True,
        )
        train_dl = train_result["dataloader"]

        # Test loader (ordered)
        test_result = create_dataloader(
            data_dir="data/test",
            transform=test_transform,
            batch_size=32,
        )
        test_dl = test_result["dataloader"]
    """
    dataset = datasets.ImageFolder(root=data_dir, transform=transform)

    dataloader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        pin_memory=True,
    )

    return DataLoaderResult(
        dataloader=dataloader,
        class_names=dataset.classes,
    )
