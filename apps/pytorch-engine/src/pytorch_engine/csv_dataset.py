"""Generic CSV-backed image dataset for flat-directory image classification."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING, Any

import pandas as pd
from PIL import Image
from torch.utils.data import Dataset

if TYPE_CHECKING:
    from torchvision import transforms

from pytorch_engine.data_setup import DataLoaderResult

logger = logging.getLogger(__name__)

HAM10000_ONE_HOT_COLUMNS = ("akiec", "bcc", "bkl", "df", "mel", "nv", "vasc")
IMAGE_ID_COLUMN_CANDIDATES = (
    "image_id",
    "image",
    "image_name",
    "isic_id",
    "img_id",
    "id",
    "filename",
)
LABEL_COLUMN_CANDIDATES = (
    "dx",
    "label",
    "class",
    "diagnosis",
    "lesion_type",
    "target",
)


def _pick_existing_column(
    columns: list[str],
    preferred: str | None,
    candidates: tuple[str, ...],
) -> str:
    if preferred and preferred in columns:
        return preferred

    lowered = {column.lower(): column for column in columns}
    if preferred:
        preferred_lower = preferred.lower()
        if preferred_lower in lowered:
            return lowered[preferred_lower]

    for candidate in candidates:
        if candidate in lowered:
            return lowered[candidate]

    if preferred:
        raise ValueError(f"Column '{preferred}' not found in CSV columns: {', '.join(columns)}")
    raise ValueError(f"Could not infer column from CSV columns: {', '.join(columns)}")


def _infer_one_hot_label_columns(df: pd.DataFrame) -> list[str]:
    lowered_map = {column.lower(): column for column in df.columns}
    preferred = [lowered_map[name] for name in HAM10000_ONE_HOT_COLUMNS if name in lowered_map]
    if len(preferred) >= 2:
        return preferred
    return []


def _maybe_create_label_column(df: pd.DataFrame, label_col: str | None) -> tuple[pd.DataFrame, str]:
    resolved_label_col = (
        _pick_existing_column(
            columns=df.columns.tolist(),
            preferred=label_col,
            candidates=LABEL_COLUMN_CANDIDATES,
        )
        if label_col
        else None
    )

    if resolved_label_col is not None:
        return df, resolved_label_col

    one_hot_columns = _infer_one_hot_label_columns(df)
    if len(one_hot_columns) < 2:
        raise ValueError(
            f"Could not infer label column. Provide label_col or include one of {LABEL_COLUMN_CANDIDATES} in CSV."
        )

    numeric_one_hot = df[one_hot_columns].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    active_per_row = (numeric_one_hot > 0.5).sum(axis=1)
    valid_mask = active_per_row == 1
    invalid_rows = int((~valid_mask).sum())
    if invalid_rows > 0:
        logger.warning(
            "Dropping %d rows with invalid one-hot labels (need exactly one active class).",
            invalid_rows,
        )
        df = df[valid_mask].copy()
        numeric_one_hot = numeric_one_hot.loc[df.index]

    df = df.copy()
    df["label"] = numeric_one_hot.idxmax(axis=1).astype(str).str.lower()
    return df, "label"


def _to_image_filename(image_id: Any, file_extension: str) -> str:
    image_id_str = str(image_id).strip()
    if Path(image_id_str).suffix:
        return image_id_str
    return f"{image_id_str}{file_extension}"


def _sanitize_dataset_dataframe(
    df: pd.DataFrame,
    image_id_col: str,
    label_col: str,
    image_dir: Path,
    file_extension: str,
) -> pd.DataFrame:
    sanitized = df.copy()
    sanitized[image_id_col] = sanitized[image_id_col].astype(str).str.strip()
    sanitized = sanitized[sanitized[image_id_col] != ""].copy()

    conflicting_ids = (
        sanitized.groupby(image_id_col)[label_col]
        .nunique(dropna=True)
        .loc[lambda unique_counts: unique_counts > 1]
        .index
    )
    conflicting_count = len(conflicting_ids)
    if conflicting_count:
        logger.warning(
            "Dropping %d image ids with conflicting duplicate labels.",
            conflicting_count,
        )
        sanitized = sanitized[~sanitized[image_id_col].isin(conflicting_ids)].copy()

    duplicate_mask = sanitized.duplicated(subset=[image_id_col], keep="first")
    duplicate_count = int(duplicate_mask.sum())
    if duplicate_count:
        logger.warning(
            "Dropping %d duplicate rows by image id column '%s'.",
            duplicate_count,
            image_id_col,
        )
        sanitized = sanitized.loc[~duplicate_mask].copy()

    sanitized["__image_filename__"] = sanitized[image_id_col].map(
        lambda value: _to_image_filename(value, file_extension)
    )
    existing_mask = sanitized["__image_filename__"].map(lambda filename: (image_dir / filename).is_file())
    missing_count = int((~existing_mask).sum())
    if missing_count:
        logger.warning(
            "Dropping %d rows because image file is missing under '%s'.",
            missing_count,
            image_dir,
        )
        sanitized = sanitized.loc[existing_mask].copy()

    return sanitized.drop(columns=["__image_filename__"])


class CSVDataset(Dataset):
    """CSV-backed image dataset for flat-directory image structures.

    Reads images from a **flat** directory (no class sub-directories) and
    retrieves labels from a CSV file.  Class labels are inferred from the
    unique values in the designated label column and assigned a sorted,
    deterministic integer index.

    Attributes:
        class_names: Sorted list of unique label values found in the CSV.
        class_to_idx: Mapping from label value to integer index.
        dataframe: The underlying :class:`pandas.DataFrame` used for loading.

    Args:
        image_dir: Directory containing the image files.
        csv_path: Path to the CSV file with at least an image-ID column and a
            label column.
        image_id_col: Optional CSV column containing the image identifier.
            If omitted, common column names are auto-detected.
        label_col: Optional CSV column containing class labels.
            If omitted, common names are auto-detected or derived from
            HAM10000 one-hot columns.
        file_extension: File extension to append when resolving filenames.
            Defaults to ``".jpg"``.
        transform: Optional torchvision transform pipeline to apply to each
            PIL image before conversion.  If ``None``, a default
            :class:`~torchvision.transforms.ToTensor` is used.

    Example::

        dataset = CSVDataset(
            image_dir="data/images",
            csv_path="data/labels.csv",
            image_id_col="image_id",
            label_col="dx",
            file_extension=".jpg",
            transform=None,
        )
        img, label_idx = dataset[0]
        print(dataset.class_names)       # ['class_a', 'class_b', ...]
        print(dataset.class_to_idx)       # {'class_a': 0, 'class_b': 1, ...}
    """

    def __init__(
        self,
        image_dir: str | Path,
        csv_path: str | Path,
        image_id_col: str | None = None,
        label_col: str | None = None,
        file_extension: str = ".jpg",
        transform: transforms.Compose | None = None,
        dataframe: pd.DataFrame | None = None,
    ) -> None:
        self.image_dir = Path(image_dir)
        self.csv_path = Path(csv_path)
        self.file_extension = file_extension
        self.transform = transform

        loaded_df = dataframe.copy() if dataframe is not None else pd.read_csv(self.csv_path)
        self.image_id_col = _pick_existing_column(
            columns=loaded_df.columns.tolist(),
            preferred=image_id_col,
            candidates=IMAGE_ID_COLUMN_CANDIDATES,
        )
        self.dataframe, self.label_col = _maybe_create_label_column(loaded_df, label_col)

        self.dataframe = _sanitize_dataset_dataframe(
            df=self.dataframe,
            image_id_col=self.image_id_col,
            label_col=self.label_col,
            image_dir=self.image_dir,
            file_extension=self.file_extension,
        ).reset_index(drop=True)
        if self.dataframe.empty:
            raise ValueError("No valid rows left after sanitizing CSV dataset.")

        # Build sorted class list and class-to-index mapping
        unique_labels = sorted(self.dataframe[self.label_col].astype(str).unique().tolist())
        self._class_names: list[str] = unique_labels
        self._class_to_idx: dict[str, int] = {label: idx for idx, label in enumerate(unique_labels)}

        logger.info(
            "CSVDataset initialised — %d samples, %d classes from '%s'.",
            len(self.dataframe),
            len(self._class_names),
            self.csv_path,
        )
        logger.info(
            "Using CSV columns image_id_col='%s', label_col='%s'.",
            self.image_id_col,
            self.label_col,
        )

    @property
    def class_names(self) -> list[str]:
        """Return the sorted list of class label values."""
        return self._class_names

    @property
    def class_to_idx(self) -> dict[str, int]:
        """Return the mapping from label value to integer index."""
        return self._class_to_idx

    def __len__(self) -> int:
        """Return the number of samples in the dataset."""
        return len(self.dataframe)

    def __getitem__(self, index: int) -> tuple:
        """Return the transformed image and label index for *index*.

        Args:
            index: Sample position within the dataset.

        Returns:
            A tuple ``(image, label_index)`` where *image* is a transformed
            image tensor and *label_index* is the integer class index.
        """
        max_attempts = len(self.dataframe)
        for attempt in range(max_attempts):
            row = self.dataframe.iloc[(index + attempt) % max_attempts]
            label_value = str(row[self.label_col])
            image_filename = _to_image_filename(row[self.image_id_col], self.file_extension)
            image_path = self.image_dir / image_filename

            if not image_path.is_file():
                logger.warning("Missing image at load time, skipping row: %s", image_path)
                continue

            image = Image.open(image_path).convert("RGB")

            if self.transform is not None:
                image = self.transform(image)
            else:
                from torchvision.transforms import ToTensor

                image = ToTensor()(image)

            label_index = self._class_to_idx[label_value]
            return image, label_index

        raise FileNotFoundError("Could not load any image from dataset rows. Verify image directory and CSV paths.")


def create_csv_dataloader(
    image_dir: str | Path,
    csv_path: str | Path,
    image_id_col: str | None = None,
    label_col: str | None = None,
    file_extension: str = ".jpg",
    transform: transforms.Compose | None = None,
    batch_size: int = 32,
    shuffle: bool = False,
    num_workers: int | None = os.cpu_count(),
    dataframe: pd.DataFrame | None = None,
) -> DataLoaderResult:
    """Factory that creates a DataLoader from a CSV-described flat image directory.

    Combines :class:`CSVDataset` and :class:`~torch.utils.data.DataLoader`
    into a single call, returning the loader together with the discovered
    class names.

    Args:
        image_dir: Directory containing the image files.
        csv_path: Path to the CSV file with at least an image-ID column and a
            label column.
        image_id_col: Optional CSV image-ID column name.
        label_col: Optional CSV label column name.
        file_extension: File extension to append when resolving filenames.
            Defaults to ``".jpg"``.
        transform: Optional torchvision transform pipeline to apply to each
            PIL image.  If ``None``, a default :class:`~torchvision.transforms.ToTensor`
            is used.
        batch_size: Number of samples per batch.  Defaults to ``32``.
        shuffle: Whether to shuffle the data each epoch.
            Use ``True`` for training, ``False`` for validation/testing.
            Defaults to ``False``.
        num_workers: Subprocess count for data loading.  Defaults to
            ``os.cpu_count()`` or ``1`` if that returns ``None``.

    Returns:
        A :class:`DataLoaderResult` dict with keys
        ``"dataloader"`` and ``"class_names"``.

    Example::

        result = create_csv_dataloader(
            image_dir="data/images",
            csv_path="data/labels.csv",
            transform=None,
            batch_size=64,
            shuffle=True,
        )
        dataloader = result["dataloader"]
        class_names = result["class_names"]

        for batch_images, batch_labels in dataloader:
            ...
    """

    dataset = CSVDataset(
        image_dir=image_dir,
        csv_path=csv_path,
        image_id_col=image_id_col,
        label_col=label_col,
        file_extension=file_extension,
        transform=transform,
        dataframe=dataframe,
    )

    from torch.utils.data import DataLoader

    dataloader = DataLoader(
        dataset,
        batch_size=batch_size,
        shuffle=shuffle,
        num_workers=num_workers,
        pin_memory=True,
    )

    return DataLoaderResult(
        dataloader=dataloader,
        class_names=dataset.class_names,
    )
