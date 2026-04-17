"""Thin entrypoint for chest X-ray EfficientNet-B0 training."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from pytorch_engine import ChestXrayTrainingConfig, run_chest_xray_effnet_training


def _default_dataset_root() -> Path:
    project_root = Path(__file__).resolve().parent.parent
    return project_root / "data" / "chest-xray-pneumonia-balanced-dataset"


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    dataset_root = Path(os.getenv("CHEST_XRAY_DATASET_ROOT", str(_default_dataset_root())))
    output_dir = Path(
        os.getenv(
            "CHEST_XRAY_OUTPUT_DIR",
            str(Path(__file__).resolve().parent / "pytorch-saved-models" / "effnetb0_chest_xray"),
        )
    )
    config = ChestXrayTrainingConfig(
        dataset_root=dataset_root,
        output_dir=output_dir,
    )
    run = run_chest_xray_effnet_training(config)
    logging.info("Selected phase: %s", run.selected_phase)
    logging.info("Validation AUROC: %s", run.val_metrics["auroc"])
    logging.info("Validation AP: %s", run.val_metrics["average_precision"])
    logging.info("Test AUROC: %s", run.test_metrics["auroc"])
    logging.info("Test AP: %s", run.test_metrics["average_precision"])
    logging.info("Best checkpoint: %s", run.best_checkpoint_path)
    logging.info("Last checkpoint: %s", run.last_checkpoint_path)


if __name__ == "__main__":
    main()
