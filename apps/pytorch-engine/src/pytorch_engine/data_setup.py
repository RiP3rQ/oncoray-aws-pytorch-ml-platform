"""PyTorch DataLoader creation and data utilities for image classification datasets."""

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any, TypedDict

import requests
import torch
from sklearn.model_selection import train_test_split
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
_AUGMENTATION_SUFFIX_PATTERN = re.compile(r"_aug_\d+$")
_GROUPED_SPLIT_MANIFEST_NAME = "grouped_split_manifest.json"


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


class ChestXrayGroupedSplitSummaryRow(TypedDict):
    """Summary row for grouped chest X-ray splits."""

    split: str
    NORMAL_images: int
    PNEUMONIA_images: int
    total_images: int
    NORMAL_groups: int
    PNEUMONIA_groups: int
    total_groups: int


class CrossSplitGroupLeak(TypedDict):
    """Patient/group identifier that appears in multiple dataset splits."""

    group_id: str
    class_name: str
    splits: list[str]


class ChestXrayImageRecord(TypedDict):
    """One chest X-ray file plus inferred grouping metadata."""

    split: str
    class_name: str
    group_id: str
    path: str


def _strip_augmentation_suffix(stem: str) -> str:
    """Remove repository-specific augmentation suffixes such as ``_aug_123``."""
    return _AUGMENTATION_SUFFIX_PATTERN.sub("", stem)


def infer_chest_xray_patient_group_id(path_or_name: str | Path) -> str:
    """Infer a patient-style grouping key from a chest X-ray filename.

    This dataset mixes several filename conventions:
      - ``person1003_bacteria_2934.jpeg`` for pneumonia images
      - ``IM-0678-0001.jpeg`` for normal images
      - ``NORMAL2-IM-0173-0001-0002.jpeg`` for normal images with extra view ids
      - ``*_aug_123.jpg`` for synthetic augmentations

    We group synthetic augmentations with their source image and collapse file
    names to a patient-style prefix so no patient/group can leak across
    train/val/test splits.
    """
    stem = _strip_augmentation_suffix(Path(path_or_name).stem)
    if stem.startswith("person"):
        return stem.split("_")[0]

    parts = stem.split("-")
    if stem.startswith("NORMAL2-IM-") and len(parts) >= 3:
        return "-".join(parts[:3])
    if stem.startswith("IM-") and len(parts) >= 2:
        return "-".join(parts[:2])
    return stem


def _iter_chest_xray_image_records(dataset_root: Path) -> list[ChestXrayImageRecord]:
    """Collect all chest X-ray image records from an ImageFolder split root."""
    records: list[ChestXrayImageRecord] = []
    for split_name in CHEST_XRAY_SPLITS:
        for class_name in CHEST_XRAY_CLASS_NAMES:
            class_dir = dataset_root / split_name / class_name
            if not class_dir.is_dir():
                raise FileNotFoundError(f"Expected class directory not found: {class_dir}")
            for file_path in sorted(path for path in class_dir.rglob("*") if path.is_file()):
                records.append(
                    ChestXrayImageRecord(
                        split=split_name,
                        class_name=class_name,
                        group_id=infer_chest_xray_patient_group_id(file_path.name),
                        path=str(file_path),
                    )
                )
    return records


def find_cross_split_group_leaks(
    dataset_root: str | Path,
) -> list[CrossSplitGroupLeak]:
    """Find patient/group identifiers that span more than one split."""
    root = Path(dataset_root)
    splits_by_group: dict[tuple[str, str], set[str]] = defaultdict(set)

    for record in _iter_chest_xray_image_records(root):
        splits_by_group[(record["group_id"], record["class_name"])].add(record["split"])

    leaks: list[CrossSplitGroupLeak] = []
    for (group_id, class_name), split_names in sorted(splits_by_group.items()):
        if len(split_names) < 2:
            continue
        leaks.append(
            CrossSplitGroupLeak(
                group_id=group_id,
                class_name=class_name,
                splits=sorted(split_names),
            )
        )
    return leaks


def summarize_chest_xray_group_splits(
    dataset_root: str | Path,
) -> list[ChestXrayGroupedSplitSummaryRow]:
    """Return per-split image counts plus inferred patient/group counts."""
    root = Path(dataset_root)
    summary_rows: list[ChestXrayGroupedSplitSummaryRow] = []

    for split_name in CHEST_XRAY_SPLITS:
        split_dir = root / split_name
        if not split_dir.is_dir():
            raise FileNotFoundError(f"Expected split directory not found: {split_dir}")

        image_counts: dict[str, int] = {}
        group_sets: dict[str, set[str]] = {}
        total_images = 0
        total_groups = 0

        for class_name in CHEST_XRAY_CLASS_NAMES:
            class_dir = split_dir / class_name
            if not class_dir.is_dir():
                raise FileNotFoundError(f"Expected class directory not found: {class_dir}")
            image_paths = [path for path in class_dir.rglob("*") if path.is_file()]
            groups = {infer_chest_xray_patient_group_id(path.name) for path in image_paths}
            image_counts[class_name] = len(image_paths)
            group_sets[class_name] = groups
            total_images += len(image_paths)
            total_groups += len(groups)

        summary_rows.append(
            ChestXrayGroupedSplitSummaryRow(
                split=split_name,
                NORMAL_images=image_counts["NORMAL"],
                PNEUMONIA_images=image_counts["PNEUMONIA"],
                total_images=total_images,
                NORMAL_groups=len(group_sets["NORMAL"]),
                PNEUMONIA_groups=len(group_sets["PNEUMONIA"]),
                total_groups=total_groups,
            )
        )

    return summary_rows


def _resolve_unique_destination_path(destination_dir: Path, source_path: Path) -> Path:
    """Return a non-conflicting output path for a copied image."""
    destination_path = destination_dir / source_path.name
    if not destination_path.exists():
        return destination_path

    prefixed_name = f"{source_path.parent.parent.name}_{source_path.name}"
    destination_path = destination_dir / prefixed_name
    if not destination_path.exists():
        return destination_path

    digest = hashlib.sha256(str(source_path).encode("utf-8")).hexdigest()[:8]
    return destination_dir / f"{source_path.stem}_{digest}{source_path.suffix}"


def prepare_grouped_chest_xray_pneumonia_dataset(
    source_root: str | Path,
    destination: str | Path,
    *,
    val_size: float = 0.1,
    test_size: float = 0.1,
    random_state: int = 42,
) -> Path:
    """Create a leakage-resistant grouped chest X-ray split dataset.

    Uses inferred patient-style group ids from filenames so all images from the
    same patient/group stay within a single split. The destination uses the
    same ImageFolder layout as the original dataset and is safe to train on
    without the known cross-split leakage present in the bundled Kaggle split.
    """
    if not (0.0 < val_size < 1.0):
        raise ValueError(f"val_size must be in (0, 1), got {val_size}")
    if not (0.0 < test_size < 1.0):
        raise ValueError(f"test_size must be in (0, 1), got {test_size}")
    if (val_size + test_size) >= 1.0:
        raise ValueError("val_size + test_size must be < 1")

    source_root_path = Path(source_root)
    destination_path = Path(destination)
    manifest_path = destination_path / _GROUPED_SPLIT_MANIFEST_NAME

    if manifest_path.is_file():
        logger.info("Grouped chest X-ray dataset already prepared in '%s'; skipping rebuild.", destination_path)
        return destination_path
    if destination_path.exists() and any(destination_path.iterdir()):
        raise FileExistsError(f"Destination already exists and is not a prepared grouped dataset: {destination_path}")

    image_records = _iter_chest_xray_image_records(source_root_path)
    if not image_records:
        raise ValueError(f"No chest X-ray images found under '{source_root_path}'")

    class_names_by_group: dict[str, set[str]] = defaultdict(set)
    file_paths_by_group: dict[str, list[Path]] = defaultdict(list)
    for record in image_records:
        class_names_by_group[record["group_id"]].add(record["class_name"])
        file_paths_by_group[record["group_id"]].append(Path(record["path"]))

    group_ids: list[str] = []
    group_labels: list[str] = []
    for group_id in sorted(class_names_by_group):
        class_names = class_names_by_group[group_id]
        if len(class_names) != 1:
            raise ValueError(
                f"Group '{group_id}' spans multiple classes: {sorted(class_names)}. Cannot build grouped split safely."
            )
        group_ids.append(group_id)
        group_labels.append(next(iter(class_names)))

    train_val_group_ids, test_group_ids = train_test_split(
        group_ids,
        test_size=test_size,
        random_state=random_state,
        stratify=group_labels,
    )
    train_val_labels = [next(iter(class_names_by_group[group_id])) for group_id in train_val_group_ids]
    relative_val_size = val_size / (1.0 - test_size)
    train_group_ids, val_group_ids = train_test_split(
        train_val_group_ids,
        test_size=relative_val_size,
        random_state=random_state,
        stratify=train_val_labels,
    )

    split_by_group = {
        **{group_id: "train" for group_id in train_group_ids},
        **{group_id: "val" for group_id in val_group_ids},
        **{group_id: "test" for group_id in test_group_ids},
    }

    for split_name in CHEST_XRAY_SPLITS:
        for class_name in CHEST_XRAY_CLASS_NAMES:
            (destination_path / split_name / class_name).mkdir(parents=True, exist_ok=True)

    for group_id, source_paths in file_paths_by_group.items():
        target_split = split_by_group[group_id]
        class_name = next(iter(class_names_by_group[group_id]))
        destination_dir = destination_path / target_split / class_name
        for source_path in sorted(source_paths):
            target_path = _resolve_unique_destination_path(destination_dir, source_path)
            shutil.copy2(source_path, target_path)

    manifest = {
        "source_root": str(source_root_path.resolve()),
        "destination_root": str(destination_path.resolve()),
        "random_state": random_state,
        "val_size": val_size,
        "test_size": test_size,
        "summary": summarize_chest_xray_group_splits(destination_path),
        "cross_split_group_leaks": find_cross_split_group_leaks(destination_path),
        "cross_split_duplicates": find_cross_split_duplicate_files(destination_path),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    logger.info("Prepared grouped chest X-ray dataset at '%s'", destination_path)

    return destination_path


def create_dataloader(
    data_dir: str,
    transform: transforms.Compose,
    batch_size: int,
    shuffle: bool = False,
    num_workers: int = NUM_WORKERS or 1,
    drop_last: bool = False,
    persistent_workers: bool | None = None,
    prefetch_factor: int | None = None,
    pin_memory: bool | None = None,
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
        drop_last: Whether to drop the final smaller batch.
        persistent_workers: Keep worker processes alive across epochs when
            ``num_workers > 0``. Defaults to ``True`` when workers are used.
        prefetch_factor: Number of batches loaded in advance by each worker.
            Only applies when ``num_workers > 0``.
        pin_memory: Override default CUDA-aware pin-memory behavior.

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

    resolved_pin_memory = torch.cuda.is_available() if pin_memory is None else pin_memory
    dataloader_kwargs: dict[str, Any] = {
        "dataset": dataset,
        "batch_size": batch_size,
        "shuffle": shuffle,
        "num_workers": num_workers,
        "drop_last": drop_last,
        "pin_memory": resolved_pin_memory,
    }
    if num_workers > 0:
        dataloader_kwargs["persistent_workers"] = True if persistent_workers is None else persistent_workers
        if prefetch_factor is not None:
            dataloader_kwargs["prefetch_factor"] = prefetch_factor

    dataloader = DataLoader(
        **dataloader_kwargs,
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
