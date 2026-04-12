"""CSV-based train/test splitting utilities for metadata files."""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from sklearn.model_selection import train_test_split

from pytorch_engine.csv_dataset import (
    IMAGE_ID_COLUMN_CANDIDATES,
    _maybe_create_label_column,
    _pick_existing_column,
    _to_image_filename,
)

logger = logging.getLogger(__name__)


def split_csv_metadata(
    csv_path: str | Path,
    test_size: float = 0.2,
    random_state: int = 42,
    image_dir: str | Path | None = None,
    image_dirs: list[str | Path] | None = None,
    image_id_col: str | None = None,
    label_col: str | None = None,
    file_extension: str = ".jpg",
    stratify: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split a CSV metadata file into train and test DataFrames.

    Reads a CSV containing image identifiers and optional labels, optionally
    filters rows whose corresponding image files do not exist on disk, and
    then performs a random train/test split.

    Args:
        csv_path: Path to the CSV file containing metadata.
        test_size: Fraction of the dataset to hold out for testing.
            Defaults to 0.2 (20%).
        random_state: Random seed for reproducibility.
            Defaults to 42.
        image_dir: Root directory containing images. If provided, rows whose
            image files are missing from this directory are filtered out before
            splitting. The image path is constructed as
            ``image_dir / {image_id}{file_extension}``.
            Defaults to ``None`` (no filtering).
        image_dirs: Optional list of root directories containing images. When
            provided, a row is kept if the image exists in any directory from
            this list. If both ``image_dir`` and ``image_dirs`` are provided,
            ``image_dirs`` takes precedence.
        image_id_col: Optional image-ID column name. If ``None`` or not found,
            the function auto-detects common names (e.g. ``image_id``,
            ``image``, ``filename``).
        label_col: Optional class-label column name. If ``None``, function
            auto-detects common names or derives ``label`` from HAM10000
            one-hot columns.
        file_extension: File extension appended to each image ID to locate
            the image file on disk. Must include the leading dot.
            Defaults to ``".jpg"``.
        stratify: Whether to stratify the train/test split by labels when
            label distribution allows it. Defaults to ``True``.

    Returns:
        A two-element tuple containing ``(train_df, test_df)``, each a
        :class:`pandas.DataFrame` with all original CSV columns preserved.

    Raises:
        FileNotFoundError: If *csv_path* does not exist.
        ValueError: If *test_size* is not in (0, 1), or if both *train_df*
            and *test_df* would be empty after filtering.

    Example::

        # Simple split without file existence checks
        train_df, test_df = split_csv_metadata("metadata.csv", test_size=0.2)

        # Split with image existence filtering
        train_df, test_df = split_csv_metadata(
            csv_path="metadata.csv",
            image_dir="data/images",
            image_id_col="image_id",
            file_extension=".jpg",
            test_size=0.25,
            random_state=123,
        )
    """
    csv_path = Path(csv_path)

    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    if not (0.0 < test_size < 1.0):
        raise ValueError(f"test_size must be in (0, 1), got {test_size}")

    df = pd.read_csv(csv_path)
    resolved_image_id_col = _pick_existing_column(
        columns=df.columns.tolist(),
        preferred=image_id_col,
        candidates=IMAGE_ID_COLUMN_CANDIDATES,
    )
    df, resolved_label_col = _maybe_create_label_column(df, label_col)
    df[resolved_image_id_col] = df[resolved_image_id_col].astype(str).str.strip()
    df = df[df[resolved_image_id_col] != ""].copy()

    conflicting_ids = (
        df.groupby(resolved_image_id_col)[resolved_label_col]
        .nunique(dropna=True)
        .loc[lambda unique_counts: unique_counts > 1]
        .index
    )
    conflicting_count = len(conflicting_ids)
    if conflicting_count:
        logger.warning(
            "Dropping %d image ids with conflicting duplicate labels before split.",
            conflicting_count,
        )
        df = df.loc[~df[resolved_image_id_col].isin(conflicting_ids)].copy()

    duplicate_mask = df.duplicated(subset=[resolved_image_id_col], keep="first")
    duplicate_count = int(duplicate_mask.sum())
    if duplicate_count:
        logger.warning(
            "Dropping %d duplicate rows before split using image id column '%s'.",
            duplicate_count,
            resolved_image_id_col,
        )
        df = df.loc[~duplicate_mask].copy()

    original_len = len(df)
    logger.info("Loaded CSV with %d rows from '%s'", original_len, csv_path)

    resolved_image_dirs: list[Path] = []
    if image_dirs:
        resolved_image_dirs = [Path(directory) for directory in image_dirs]
    elif image_dir is not None:
        resolved_image_dirs = [Path(image_dir)]

    if resolved_image_dirs:
        mask = df[resolved_image_id_col].map(
            lambda image_id: any(
                (directory / _to_image_filename(image_id, file_extension)).is_file()
                for directory in resolved_image_dirs
            )
        )
        df = df[mask].reset_index(drop=True)
        filtered_len = len(df)
        dropped = original_len - filtered_len
        logger.info(
            "Filtered out %d rows with missing images (kept %d rows) using %d image directories",
            dropped,
            filtered_len,
            len(resolved_image_dirs),
        )

    if df.empty:
        raise ValueError("No rows remaining after filtering; cannot split.")

    stratify_col = None
    if stratify and resolved_label_col in df.columns:
        label_counts = df[resolved_label_col].astype(str).value_counts()
        if not label_counts.empty and label_counts.min() >= 2:
            stratify_col = df[resolved_label_col].astype(str)

    train_df, test_df = train_test_split(
        df,
        test_size=test_size,
        random_state=random_state,
        stratify=stratify_col,
    )

    logger.info(
        "Split complete: train=%d rows, test=%d rows",
        len(train_df),
        len(test_df),
    )

    return train_df, test_df
