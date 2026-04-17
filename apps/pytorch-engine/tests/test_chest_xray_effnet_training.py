from __future__ import annotations

import shutil
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import torch
from PIL import Image
from pytorch_engine.chest_xray_effnet_training import (
    ChestXrayTrainingConfig,
    build_chest_xray_imagefolder_loaders,
    run_chest_xray_effnet_training,
)

TEST_FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"


def _write_image(path: Path, color: tuple[int, int, int] = (255, 255, 255)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (8, 8), color=color).save(path)


@contextmanager
def _workspace_tmp_dir() -> Path:
    root = TEST_FIXTURES_DIR / f"tmp_{uuid4().hex}"
    root.mkdir(parents=True, exist_ok=False)
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _populate_imagefolder_dataset(root: Path) -> None:
    for split_name in ("train", "val", "test"):
        _write_image(root / split_name / "NORMAL" / f"{split_name}_normal.png", color=(255, 255, 255))
        _write_image(root / split_name / "PNEUMONIA" / f"{split_name}_pneumonia.png", color=(32, 32, 32))


class BuildChestXrayImagefolderLoadersTests(unittest.TestCase):
    def test_builds_expected_binary_dataloaders(self) -> None:
        with _workspace_tmp_dir() as root:
            _populate_imagefolder_dataset(root)
            config = ChestXrayTrainingConfig(
                dataset_root=root,
                device="cuda",
                batch_size=4,
                num_workers=0,
                head_warmup_epochs=1,
                fine_tune_epochs=0,
            )

            loaders = build_chest_xray_imagefolder_loaders(config)

        self.assertEqual(loaders.class_names, ["NORMAL", "PNEUMONIA"])
        self.assertEqual(loaders.train_dataloader.batch_size, 4)
        self.assertTrue(loaders.train_dataloader.drop_last)
        self.assertFalse(loaders.val_dataloader.drop_last)
        self.assertTrue(loaders.train_dataloader.pin_memory)


class RunChestXrayEffnetTrainingTests(unittest.TestCase):
    def test_selects_best_phase_and_writes_local_checkpoints(self) -> None:
        with _workspace_tmp_dir() as root:
            _populate_imagefolder_dataset(root)
            output_dir = root / "checkpoints"
            config = ChestXrayTrainingConfig(
                dataset_root=root,
                output_dir=output_dir,
                num_workers=0,
                device="cpu",
                head_warmup_epochs=1,
                fine_tune_epochs=2,
            )

            class TinyEffNet(torch.nn.Module):
                def __init__(self) -> None:
                    super().__init__()
                    self.features = torch.nn.Sequential(
                        torch.nn.Linear(4, 4, bias=False),
                        torch.nn.Linear(4, 4, bias=False),
                        torch.nn.Linear(4, 4, bias=False),
                    )
                    self.classifier = torch.nn.Sequential(
                        torch.nn.Dropout(p=0.0),
                        torch.nn.Linear(4, 2),
                    )

                def forward(self, X: torch.Tensor) -> torch.Tensor:
                    flattened = X.view(X.size(0), -1)
                    return self.classifier(flattened[:, :4])

            fake_model_bundle = SimpleNamespace(model=TinyEffNet(), transforms=None)

            def fake_train_model(*args: object, **kwargs: object) -> dict[str, list[float]]:
                callback = kwargs.get("epoch_end_callback")
                model = kwargs["model"]
                if callable(callback):
                    callback(
                        1,
                        model,
                        {"loss": 0.2, "accuracy": 1.0},
                        {"loss": 0.3, "accuracy": 1.0},
                    )
                return {
                    "train_loss": [0.2],
                    "train_acc": [1.0],
                    "test_loss": [0.3],
                    "test_acc": [1.0],
                }

            validation_metrics = [
                {
                    "accuracy": 1.0,
                    "balanced_accuracy": 1.0,
                    "macro_f1": 1.0,
                    "macro_precision": 1.0,
                    "macro_recall": 1.0,
                    "weighted_f1": 1.0,
                    "auroc": 0.65,
                    "average_precision": 0.7,
                    "class_names": ["NORMAL", "PNEUMONIA"],
                    "per_class_precision": {"NORMAL": 1.0, "PNEUMONIA": 1.0},
                    "per_class_recall": {"NORMAL": 1.0, "PNEUMONIA": 1.0},
                    "per_class_f1": {"NORMAL": 1.0, "PNEUMONIA": 1.0},
                    "per_class_support": {"NORMAL": 1, "PNEUMONIA": 1},
                    "confusion_matrix": [[1, 0], [0, 1]],
                    "normalized_confusion_matrix": [[1.0, 0.0], [0.0, 1.0]],
                    "positive_class_index": 1,
                    "y_prob": [0.1, 0.9],
                    "y_true": [0, 1],
                    "y_pred": [0, 1],
                },
                {
                    "accuracy": 1.0,
                    "balanced_accuracy": 1.0,
                    "macro_f1": 1.0,
                    "macro_precision": 1.0,
                    "macro_recall": 1.0,
                    "weighted_f1": 1.0,
                    "auroc": 0.82,
                    "average_precision": 0.85,
                    "class_names": ["NORMAL", "PNEUMONIA"],
                    "per_class_precision": {"NORMAL": 1.0, "PNEUMONIA": 1.0},
                    "per_class_recall": {"NORMAL": 1.0, "PNEUMONIA": 1.0},
                    "per_class_f1": {"NORMAL": 1.0, "PNEUMONIA": 1.0},
                    "per_class_support": {"NORMAL": 1, "PNEUMONIA": 1},
                    "confusion_matrix": [[1, 0], [0, 1]],
                    "normalized_confusion_matrix": [[1.0, 0.0], [0.0, 1.0]],
                    "positive_class_index": 1,
                    "y_prob": [0.1, 0.9],
                    "y_true": [0, 1],
                    "y_pred": [0, 1],
                },
                {
                    "accuracy": 1.0,
                    "balanced_accuracy": 1.0,
                    "macro_f1": 1.0,
                    "macro_precision": 1.0,
                    "macro_recall": 1.0,
                    "weighted_f1": 1.0,
                    "auroc": 0.81,
                    "average_precision": 0.84,
                    "class_names": ["NORMAL", "PNEUMONIA"],
                    "per_class_precision": {"NORMAL": 1.0, "PNEUMONIA": 1.0},
                    "per_class_recall": {"NORMAL": 1.0, "PNEUMONIA": 1.0},
                    "per_class_f1": {"NORMAL": 1.0, "PNEUMONIA": 1.0},
                    "per_class_support": {"NORMAL": 1, "PNEUMONIA": 1},
                    "confusion_matrix": [[1, 0], [0, 1]],
                    "normalized_confusion_matrix": [[1.0, 0.0], [0.0, 1.0]],
                    "positive_class_index": 1,
                    "y_prob": [0.1, 0.9],
                    "y_true": [0, 1],
                    "y_pred": [0, 1],
                },
            ]

            with (
                patch(
                    "pytorch_engine.chest_xray_effnet_training.create_effnetb0_model",
                    return_value=fake_model_bundle,
                ),
                patch("pytorch_engine.chest_xray_effnet_training.train_model", side_effect=fake_train_model),
                patch(
                    "pytorch_engine.chest_xray_effnet_training._build_validation_metrics",
                    side_effect=validation_metrics,
                ),
            ):
                run = run_chest_xray_effnet_training(config)

            self.assertEqual(run.selected_phase, "fine_tune")
            self.assertTrue(run.best_checkpoint_path.is_file())
            self.assertTrue(run.last_checkpoint_path.is_file())
            self.assertAlmostEqual(run.val_metrics["auroc"] or 0.0, 0.82, places=6)
            self.assertAlmostEqual(run.test_metrics["auroc"] or 0.0, 0.81, places=6)


if __name__ == "__main__":
    unittest.main()
