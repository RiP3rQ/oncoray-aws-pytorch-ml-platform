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
    download_and_prepare_kaggle_chest_xray_pneumonia_dataset,
    find_cross_split_duplicate_files,
    find_cross_split_group_leaks,
    infer_chest_xray_patient_group_id,
    prepare_grouped_chest_xray_pneumonia_dataset,
    summarize_chest_xray_group_splits,
    summarize_imagefolder_splits,
)
from torchvision import transforms

TEST_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _write_image(path: Path, color: tuple[int, int, int] = (255, 255, 255)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (4, 4), color=color).save(path)


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


class DownloadAndPrepareChestXrayDatasetTests(unittest.TestCase):
    def test_skips_download_when_dataset_already_prepared(self) -> None:
        with _workspace_tmp_dir() as root:
            for split_name in ("train", "val", "test"):
                for class_name in ("NORMAL", "PNEUMONIA"):
                    _write_image(root / split_name / class_name / f"{split_name.lower()}_{class_name.lower()}.png")

            with patch("pytorch_engine.data_setup.download_with_curl") as mocked_download:
                dataset_root = download_and_prepare_kaggle_chest_xray_pneumonia_dataset(destination=root)

        self.assertEqual(dataset_root, root)
        mocked_download.assert_not_called()


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


class InferChestXrayPatientGroupIdTests(unittest.TestCase):
    def test_handles_augmented_and_multi_view_filename_patterns(self) -> None:
        self.assertEqual(infer_chest_xray_patient_group_id("person1003_bacteria_2934.jpeg"), "person1003")
        self.assertEqual(infer_chest_xray_patient_group_id("IM-0678-0001.jpeg"), "IM-0678")
        self.assertEqual(
            infer_chest_xray_patient_group_id("NORMAL2-IM-0173-0001-0002.jpeg"),
            "NORMAL2-IM-0173",
        )
        self.assertEqual(
            infer_chest_xray_patient_group_id("NORMAL2-IM-0530-0001_aug_411.jpg"),
            "NORMAL2-IM-0530",
        )


class PrepareGroupedChestXrayPneumoniaDatasetTests(unittest.TestCase):
    def test_rebuilds_patient_group_safe_split_dataset(self) -> None:
        with _workspace_tmp_dir() as root:
            source_root = root / "source"
            destination_root = root / "grouped"

            normal_groups = [
                ("train", "IM-0001-0001.jpeg", (255, 0, 0)),
                ("test", "IM-0001-0002.jpeg", (254, 0, 0)),
                ("train", "IM-0002-0001.jpeg", (0, 255, 0)),
                ("val", "IM-0003-0001.jpeg", (0, 0, 255)),
                ("train", "NORMAL2-IM-0004-0001-0001.jpeg", (255, 255, 0)),
                ("val", "NORMAL2-IM-0004-0001_aug_1.jpg", (255, 254, 0)),
                ("train", "NORMAL2-IM-0005-0001.jpeg", (255, 0, 255)),
            ]
            pneumonia_groups = [
                ("train", "person1_bacteria_1.jpeg", (10, 10, 10)),
                ("test", "person1_virus_2.jpeg", (11, 10, 10)),
                ("train", "person2_bacteria_3.jpeg", (20, 20, 20)),
                ("val", "person3_virus_4.jpeg", (30, 30, 30)),
                ("train", "person4_bacteria_5.jpeg", (40, 40, 40)),
                ("test", "person5_virus_6.jpeg", (50, 50, 50)),
            ]

            for split, filename, color in normal_groups:
                _write_image(source_root / split / "NORMAL" / filename, color=color)
            for split, filename, color in pneumonia_groups:
                _write_image(source_root / split / "PNEUMONIA" / filename, color=color)

            prepared_root = prepare_grouped_chest_xray_pneumonia_dataset(
                source_root=source_root,
                destination=destination_root,
                val_size=0.25,
                test_size=0.25,
                random_state=42,
            )

            self.assertEqual(prepared_root, destination_root)
            self.assertTrue((destination_root / "grouped_split_manifest.json").is_file())
            self.assertEqual(find_cross_split_group_leaks(destination_root), [])
            self.assertEqual(find_cross_split_duplicate_files(destination_root), [])

            image_summary = summarize_imagefolder_splits(destination_root)
            group_summary = summarize_chest_xray_group_splits(destination_root)
            self.assertEqual(sum(row["total"] for row in image_summary), len(normal_groups) + len(pneumonia_groups))
            self.assertEqual(
                sum(row["total_images"] for row in group_summary), len(normal_groups) + len(pneumonia_groups)
            )
            self.assertEqual(sum(row["total_groups"] for row in group_summary), 10)


if __name__ == "__main__":
    unittest.main()
