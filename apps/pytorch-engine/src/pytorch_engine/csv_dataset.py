"""Generic CSV-backed image dataset for flat-directory image classification."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
from PIL import Image
from torch.utils.data import Dataset

if TYPE_CHECKING:
    from torchvision import transforms

from pytorch_engine.data_setup import DataLoaderResult

logger = logging.getLogger(__name__)


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
        image_id_col: Name of the CSV column containing the image identifier
            (filename without extension).  Defaults to ``"image_id"``.
        label_col: Name of the CSV column containing the class label.
            Defaults to ``"dx"``.
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
        image_id_col: str = "image_id",
        label_col: str = "dx",
        file_extension: str = ".jpg",
        transform: transforms.Compose | None = None,
    ) -> None:
        self.image_dir = Path(image_dir)
        self.csv_path = Path(csv_path)
        self.image_id_col = image_id_col
        self.label_col = label_col
        self.file_extension = file_extension
        self.transform = transform

        self.dataframe = pd.read_csv(self.csv_path)

        # Build sorted class list and class-to-index mapping
        unique_labels = sorted(self.dataframe[label_col].unique().tolist())
        self._class_names: list[str] = unique_labels
        self._class_to_idx: dict[str, int] = {
            label: idx for idx, label in enumerate(unique_labels)
        }

        logger.info(
            "CSVDataset initialised — %d samples, %d classes from '%s'.",
            len(self.dataframe),
            len(self._class_names),
            self.csv_path,
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
        row = self.dataframe.iloc[index]
        image_id = str(row[self.image_id_col])
        label_value = row[self.label_col]

        image_path = self.image_dir / f"{image_id}{self.file_extension}"
        image = Image.open(image_path).convert("RGB")

        if self.transform is not None:
            image = self.transform(image)
        else:
            from torchvision.transforms import ToTensor

            image = ToTensor()(image)

        label_index = self._class_to_idx[label_value]
        return image, label_index


def create_csv_dataloader(
    image_dir: str | Path,
    csv_path: str | Path,
    image_id_col: str = "image_id",
    label_col: str = "dx",
    file_extension: str = ".jpg",
    transform: transforms.Compose | None = None,
    batch_size: int = 32,
    shuffle: bool = False,
    num_workers: int | None = os.cpu_count(),
) -> DataLoaderResult:
    """Factory that creates a DataLoader from a CSV-described flat image directory.

    Combines :class:`CSVDataset` and :class:`~torch.utils.data.DataLoader`
    into a single call, returning the loader together with the discovered
    class names.

    Args:
        image_dir: Directory containing the image files.
        csv_path: Path to the CSV file with at least an image-ID column and a
            label column.
        image_id_col: Name of the CSV column containing the image identifier
            (filename without extension).  Defaults to ``"image_id"``.
        label_col: Name of the CSV column containing the class label.
            Defaults to ``"dx"``.
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
