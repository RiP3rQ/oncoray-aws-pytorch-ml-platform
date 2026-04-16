"""PyTorch DataLoader creation and data utilities for image classification datasets."""

import hashlib
import logging
import os
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any, TypedDict

import requests
import torch
from torch.utils.data import DataLoader
from torchvision import datasets, transforms

NUM_WORKERS: int | None = os.cpu_count()

logger = logging.getLogger(__name__)

DEFAULT_KAGGLE_HAM10000_URL = (
    "https://www.kaggle.com/api/v1/datasets/download/surajghuwalewala/ham1000-segmentation-and-classification"
)
DEFAULT_KAGGLE_CHEST_XRAY_PNEUMONIA_BALANCED_URL = (
    "https://www.kaggle.com/api/v1/datasets/download/yusufmurtaza01/chest-xray-pneumonia-balanced-dataset"
)
CHEST_XRAY_SPLITS = ("train", "val", "test")
CHEST_XRAY_CLASS_NAMES = ("NORMAL", "PNEUMONIA")


def download_with_curl(
    url: str,
    output_path: str | Path,
) -> Path:
    """Download file from internet using curl."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    command = ["curl", "-L", "-o", str(output), url]
    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(
                "curl download failed. "
                f"Command: {' '.join(command)}\n"
                f"stderr: {result.stderr.strip()}\n"
                "Ensure Kaggle API authentication is configured."
            )
    except FileNotFoundError:
        logger.warning("curl not found in PATH. Falling back to requests download.")
        response = requests.get(url, timeout=120)
        if response.status_code != 200:
            raise RuntimeError(
                "HTTP download failed. "
                f"status={response.status_code} url={url}. "
                "Ensure Kaggle API authentication is configured."
            ) from None
        output.write_bytes(response.content)

    return output


def download_and_prepare_kaggle_ham10000_dataset(
    destination: str | Path,
    download_url: str = DEFAULT_KAGGLE_HAM10000_URL,
    zip_name: str = "ham1000-segmentation-and-classification.zip",
    remove_masks_dir: bool = True,
    remove_zip: bool = True,
) -> Path:
    """Download HAM10000 Kaggle dataset zip from internet, extract, clean masks."""
    destination_path = Path(destination)
    destination_path.mkdir(parents=True, exist_ok=True)
    zip_path = destination_path / zip_name

    images_path = destination_path / "images"
    csv_path = destination_path / "GroundTruth.csv"
    if images_path.is_dir() and csv_path.is_file():
        if remove_masks_dir and (destination_path / "masks").exists():
            shutil.rmtree(destination_path / "masks")
        logger.info("Dataset already prepared in '%s'; skipping download.", destination_path)
        return destination_path

    download_with_curl(url=download_url, output_path=zip_path)
    return prepare_kaggle_ham10000_dataset(
        zip_path=zip_path,
        destination=destination_path,
        remove_masks_dir=remove_masks_dir,
        remove_zip=remove_zip,
    )


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


def _is_imagefolder_split_root(
    root: Path,
    *,
    split_names: tuple[str, ...],
    class_names: tuple[str, ...],
) -> bool:
    """Return True when *root* matches an ImageFolder train/val/test layout."""
    return all(
        (root / split_name).is_dir() and all((root / split_name / class_name).is_dir() for class_name in class_names)
        for split_name in split_names
    )


def _find_imagefolder_split_root(
    destination: Path,
    *,
    split_names: tuple[str, ...],
    class_names: tuple[str, ...],
) -> Path:
    """Find directory that contains expected split/class subdirectories."""
    candidates = [destination]
    candidates.extend(
        sorted(
            (path for path in destination.rglob("*") if path.is_dir()),
            key=lambda path: (len(path.parts), str(path).lower()),
        )
    )
    for candidate in candidates:
        if _is_imagefolder_split_root(
            candidate,
            split_names=split_names,
            class_names=class_names,
        ):
            return candidate

    expected_structure = ", ".join(f"{split_name}/<{'|'.join(class_names)}>" for split_name in split_names)
    raise FileNotFoundError(
        "Could not find extracted dataset root with expected directory layout under "
        f"'{destination}'. Expected split/class structure like: {expected_structure}."
    )


def download_and_prepare_kaggle_chest_xray_pneumonia_dataset(
    destination: str | Path,
    download_url: str = DEFAULT_KAGGLE_CHEST_XRAY_PNEUMONIA_BALANCED_URL,
    zip_name: str = "chest-xray-pneumonia-balanced-dataset.zip",
    remove_zip: bool = True,
) -> Path:
    """Download chest X-ray Kaggle archive and return extracted dataset root.

    The Kaggle archive may contain one or more wrapper directories. This helper
    extracts the archive into *destination* and returns the nested directory
    that directly contains ``train/``, ``val/``, and ``test/`` splits.
    """
    destination_path = Path(destination)
    destination_path.mkdir(parents=True, exist_ok=True)

    try:
        dataset_root = _find_imagefolder_split_root(
            destination_path,
            split_names=CHEST_XRAY_SPLITS,
            class_names=CHEST_XRAY_CLASS_NAMES,
        )
    except FileNotFoundError:
        dataset_root = None
    else:
        logger.info("Dataset already prepared in '%s'; skipping download.", dataset_root)
        return dataset_root

    zip_path = destination_path / zip_name
    download_with_curl(url=download_url, output_path=zip_path)
    return prepare_kaggle_chest_xray_pneumonia_dataset(
        zip_path=zip_path,
        destination=destination_path,
        remove_zip=remove_zip,
    )


def prepare_kaggle_chest_xray_pneumonia_dataset(
    zip_path: str | Path,
    destination: str | Path,
    remove_zip: bool = False,
) -> Path:
    """Extract chest X-ray Kaggle archive and return split-root directory.

    Expected extracted structure somewhere under *destination*:
      - ``train/NORMAL``
      - ``train/PNEUMONIA``
      - ``val/NORMAL``
      - ``val/PNEUMONIA``
      - ``test/NORMAL``
      - ``test/PNEUMONIA``
    """
    zip_path = Path(zip_path)
    destination_path = Path(destination)

    if not zip_path.is_file():
        raise FileNotFoundError(f"Dataset zip not found: {zip_path}")

    destination_path.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(zip_path, "r") as zip_ref:
        logger.info("Extracting dataset '%s' to '%s'", zip_path, destination_path)
        zip_ref.extractall(destination_path)

    dataset_root = _find_imagefolder_split_root(
        destination_path,
        split_names=CHEST_XRAY_SPLITS,
        class_names=CHEST_XRAY_CLASS_NAMES,
    )

    if remove_zip:
        zip_path.unlink(missing_ok=True)

    return dataset_root


def summarize_imagefolder_splits(
    dataset_root: str | Path,
    split_names: tuple[str, ...] = CHEST_XRAY_SPLITS,
    class_names: tuple[str, ...] | None = CHEST_XRAY_CLASS_NAMES,
) -> list[dict[str, int | str]]:
    """Return per-split file counts grouped by class directory.

    Each row contains the split name, one count per class directory, and a
    ``total`` key with the summed file count for the split.
    """
    root = Path(dataset_root)
    summaries: list[dict[str, int | str]] = []

    for split_name in split_names:
        split_dir = root / split_name
        if not split_dir.is_dir():
            raise FileNotFoundError(f"Expected split directory not found: {split_dir}")

        if class_names is None:
            resolved_class_names = tuple(sorted(path.name for path in split_dir.iterdir() if path.is_dir()))
        else:
            resolved_class_names = class_names

        row: dict[str, int | str] = {"split": split_name}
        total = 0
        for class_name in resolved_class_names:
            class_dir = split_dir / class_name
            count = sum(1 for file_path in class_dir.rglob("*") if file_path.is_file()) if class_dir.is_dir() else 0
            row[class_name] = count
            total += count
        row["total"] = total
        summaries.append(row)

    return summaries


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

    dataloader: DataLoader[Any]
    class_names: list[str]


class DuplicateImageRecord(TypedDict):
    """One hashed file occurrence inside a dataset split."""

    split: str
    path: str


class CrossSplitDuplicateGroup(TypedDict):
    """Exact duplicate files that appear in more than one dataset split."""

    sha256: str
    files: list[DuplicateImageRecord]


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
        pin_memory=torch.cuda.is_available(),
    )

    return DataLoaderResult(
        dataloader=dataloader,
        class_names=dataset.classes,
    )


def find_cross_split_duplicate_files(
    dataset_root: str | Path,
    split_names: tuple[str, ...] = CHEST_XRAY_SPLITS,
) -> list[CrossSplitDuplicateGroup]:
    """Find exact duplicate files that appear in more than one split.

    Hashes each file with SHA256 and returns only groups whose identical bytes
    span at least two distinct split roots. Duplicates within the same split are
    ignored because they do not create train/val/test leakage by themselves.
    """
    root = Path(dataset_root)
    records_by_hash: dict[str, list[DuplicateImageRecord]] = {}

    for split_name in split_names:
        split_dir = root / split_name
        if not split_dir.is_dir():
            raise FileNotFoundError(f"Expected split directory not found: {split_dir}")

        for file_path in sorted(path for path in split_dir.rglob("*") if path.is_file()):
            file_hash = hashlib.sha256(file_path.read_bytes()).hexdigest()
            records_by_hash.setdefault(file_hash, []).append(
                DuplicateImageRecord(split=split_name, path=str(file_path))
            )

    duplicate_groups: list[CrossSplitDuplicateGroup] = []
    for file_hash, file_records in records_by_hash.items():
        unique_splits = {record["split"] for record in file_records}
        if len(file_records) < 2 or len(unique_splits) < 2:
            continue
        duplicate_groups.append(
            CrossSplitDuplicateGroup(
                sha256=file_hash,
                files=sorted(file_records, key=lambda record: (record["split"], record["path"])),
            )
        )

    duplicate_groups.sort(key=lambda group: (len(group["files"]), group["sha256"]))
    return duplicate_groups
