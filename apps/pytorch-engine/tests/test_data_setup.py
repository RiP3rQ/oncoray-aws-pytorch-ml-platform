from __future__ import annotations

import shutil
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from PIL import Image
from pytorch_engine.data_setup import (
    create_dataloader,
    find_cross_split_duplicate_files,
    summarize_imagefolder_splits,
)
from torchvision import transforms

TEST_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _write_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (4, 4), color=(255, 255, 255)).save(path)


@contextmanager
def _workspace_tmp_dir() -> Path:
    root = TEST_FIXTURES_DIR / f"tmp_{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=False)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


class SummarizeImagefolderSplitsTests(unittest.TestCase):
    def test_returns_expected_counts_for_each_split(self) -> None:
        with _workspace_tmp_dir() as root:
            _write_image(root / "train" / "NORMAL" / "normal_1.png")
            _write_image(root / "train" / "NORMAL" / "normal_2.png")
            _write_image(root / "train" / "PNEUMONIA" / "pneumonia_1.png")
            _write_image(root / "val" / "NORMAL" / "normal_1.png")
            _write_image(root / "test" / "PNEUMONIA" / "pneumonia_1.png")
            _write_image(root / "test" / "PNEUMONIA" / "pneumonia_2.png")

            summary = summarize_imagefolder_splits(root)

        self.assertEqual(
            summary,
            [
                {"split": "train", "NORMAL": 2, "PNEUMONIA": 1, "total": 3},
                {"split": "val", "NORMAL": 1, "PNEUMONIA": 0, "total": 1},
                {"split": "test", "NORMAL": 0, "PNEUMONIA": 2, "total": 2},
            ],
        )


class CreateDataloaderTests(unittest.TestCase):
    def test_disables_pin_memory_when_cuda_unavailable(self) -> None:
        with _workspace_tmp_dir() as root:
            _write_image(root / "NORMAL" / "sample.png")

            with patch("pytorch_engine.data_setup.torch.cuda.is_available", return_value=False):
                result = create_dataloader(
                    data_dir=str(root),
                    transform=transforms.ToTensor(),
                    batch_size=1,
                    num_workers=0,
                )

        self.assertEqual(result["class_names"], ["NORMAL"])
        self.assertFalse(result["dataloader"].pin_memory)


class FindCrossSplitDuplicateFilesTests(unittest.TestCase):
    def test_returns_exact_duplicates_that_span_multiple_splits(self) -> None:
        with _workspace_tmp_dir() as root:
            source_file = root / "source.png"
            _write_image(source_file)
            train_file = root / "train" / "NORMAL" / "same.png"
            test_file = root / "test" / "NORMAL" / "same_copy.png"
            train_file.parent.mkdir(parents=True, exist_ok=True)
            test_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_file, train_file)
            shutil.copyfile(source_file, test_file)

            duplicate_groups = find_cross_split_duplicate_files(root, split_names=("train", "test"))

        self.assertEqual(len(duplicate_groups), 1)
        duplicate_group = duplicate_groups[0]
        self.assertEqual(
            duplicate_group["files"],
            [
                {"split": "test", "path": str(test_file)},
                {"split": "train", "path": str(train_file)},
            ],
        )

    def test_ignores_duplicates_within_same_split_only(self) -> None:
        with _workspace_tmp_dir() as root:
            source_file = root / "source.png"
            _write_image(source_file)
            train_file_a = root / "train" / "NORMAL" / "same_a.png"
            train_file_b = root / "train" / "NORMAL" / "same_b.png"
            train_file_a.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_file, train_file_a)
            shutil.copyfile(source_file, train_file_b)

            duplicate_groups = find_cross_split_duplicate_files(root, split_names=("train",))

        self.assertEqual(duplicate_groups, [])


if __name__ == "__main__":
    unittest.main()
