"""CSV-based train/test splitting utilities for metadata files."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import cast

import pandas as pd
from sklearn.model_selection import train_test_split

logger = logging.getLogger(__name__)


def split_csv_metadata(
    csv_path: str | Path,
    test_size: float = 0.2,
    random_state: int = 42,
    image_dir: str | Path | None = None,
    image_id_col: str = "image_id",
    label_col: str = "dx",
    file_extension: str = ".jpg",
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
        image_id_col: Name of the column in *csv_path* that contains the image
            base name (without extension). Defaults to ``"image_id"``.
        label_col: Name of the column containing the label. This parameter
            is accepted for API consistency but is not used for stratification.
            Defaults to ``"dx"``.
        file_extension: File extension appended to each image ID to locate
            the image file on disk. Must include the leading dot.
            Defaults to ``".jpg"``.

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
    original_len = len(df)
    logger.info("Loaded CSV with %d rows from '%s'", original_len, csv_path)

    if image_dir is not None:
        image_dir = Path(image_dir)
        image_paths = {
            row[image_id_col]: image_dir / f"{row[image_id_col]}{file_extension}"
            for _, row in df.iterrows()
        }
        mask = pd.Series([p.is_file() for p in image_paths.values()], index=df.index)
        df = df[mask].reset_index(drop=True)
        filtered_len = len(df)
        dropped = original_len - filtered_len
        logger.info(
            "Filtered out %d rows with missing images (kept %d rows)",
            dropped,
            filtered_len,
        )

    if df.empty:
        raise ValueError("No rows remaining after filtering; cannot split.")

    train_df, test_df = train_test_split(
        df,
        test_size=test_size,
        random_state=random_state,
    )

    logger.info(
        "Split complete: train=%d rows, test=%d rows",
        len(train_df),
        len(test_df),
    )

    return cast(tuple[pd.DataFrame, pd.DataFrame], (train_df, test_df))
