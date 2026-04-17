"""Thin entrypoint for chest X-ray EfficientNet-B0 training."""

from __future__ import annotations

import logging
import os
from pathlib import Path

import torch
from pytorch_engine import ChestXrayTrainingConfig, run_chest_xray_effnet_training
from pytorch_engine.data_setup import summarize_imagefolder_splits
from pytorch_engine.utils import configure_torch_runtime, resolve_device


def _default_dataset_root() -> Path:
    project_root = Path(__file__).resolve().parent.parent
    return project_root / "data" / "chest-xray-pneumonia-balanced-dataset"


def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean string, got {raw_value!r}")


def _env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    return default if raw_value is None else int(raw_value)


def _env_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    return default if raw_value is None else float(raw_value)


def _env_optional_int(name: str) -> int | None:
    raw_value = os.getenv(name)
    if raw_value is None or raw_value.strip() == "":
        return None
    return int(raw_value)


def _build_training_config(dataset_root: Path, output_dir: Path) -> ChestXrayTrainingConfig:
    requested_device = os.getenv("CHEST_XRAY_DEVICE", "auto")
    resolved_device = resolve_device(requested_device)
    cuda_defaults = resolved_device.type == "cuda"
    return ChestXrayTrainingConfig(
        dataset_root=dataset_root,
        output_dir=output_dir,
        device=resolved_device,
        batch_size=_env_int("CHEST_XRAY_BATCH_SIZE", 32 if cuda_defaults else 16),
        num_workers=_env_optional_int("CHEST_XRAY_NUM_WORKERS"),
        head_warmup_epochs=_env_int("CHEST_XRAY_HEAD_WARMUP_EPOCHS", 1),
        fine_tune_epochs=_env_int("CHEST_XRAY_FINE_TUNE_EPOCHS", 8),
        trainable_feature_blocks=_env_int("CHEST_XRAY_TRAINABLE_FEATURE_BLOCKS", 2),
        head_learning_rate=_env_float("CHEST_XRAY_HEAD_LR", 3e-4),
        fine_tune_head_learning_rate=_env_float("CHEST_XRAY_FINE_TUNE_HEAD_LR", 1e-4),
        backbone_learning_rate=_env_float("CHEST_XRAY_BACKBONE_LR", 3e-5),
        weight_decay=_env_float("CHEST_XRAY_WEIGHT_DECAY", 1e-4),
        label_smoothing=_env_float("CHEST_XRAY_LABEL_SMOOTHING", 0.05),
        compile_model=_env_bool("CHEST_XRAY_COMPILE_MODEL", cuda_defaults),
        use_amp=_env_bool("CHEST_XRAY_USE_AMP", cuda_defaults),
        use_channels_last=_env_bool("CHEST_XRAY_USE_CHANNELS_LAST", cuda_defaults),
        pin_memory=_env_bool("CHEST_XRAY_PIN_MEMORY", cuda_defaults),
        early_stopping_patience=_env_int("CHEST_XRAY_EARLY_STOPPING_PATIENCE", 3),
    )


def _log_split_summary(dataset_root: Path) -> None:
    for row in summarize_imagefolder_splits(dataset_root):
        logging.info(
            "Dataset split %s | total=%s normal=%s pneumonia=%s",
            row["split"],
            row["total"],
            row.get("NORMAL", 0),
            row.get("PNEUMONIA", 0),
        )


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
    config = _build_training_config(dataset_root=dataset_root, output_dir=output_dir)
    resolved_device = resolve_device(config.device)
    configure_torch_runtime(resolved_device)
    logging.info("Training device: %s", resolved_device)
    if resolved_device.type == "cuda":
        logging.info("CUDA device: %s", torch.cuda.get_device_name(resolved_device))
    logging.info(
        "Config | batch_size=%d warmup=%d fine_tune=%d trainable_blocks=%d "
        "head_lr=%.2e fine_tune_head_lr=%.2e backbone_lr=%.2e amp=%s compile=%s channels_last=%s",
        config.batch_size,
        config.head_warmup_epochs,
        config.fine_tune_epochs,
        config.trainable_feature_blocks,
        config.head_learning_rate,
        config.fine_tune_head_learning_rate,
        config.backbone_learning_rate,
        config.use_amp,
        config.compile_model,
        config.use_channels_last,
    )
    _log_split_summary(dataset_root)
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
