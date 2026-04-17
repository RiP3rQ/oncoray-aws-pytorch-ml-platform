"""Chest X-ray EfficientNet-B0 training pipeline."""

from __future__ import annotations

import os
from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader

from pytorch_engine.data_setup import create_dataloader
from pytorch_engine.evaluation import ClassificationMetrics, evaluate_classification_model
from pytorch_engine.models import create_effnetb0_model
from pytorch_engine.training_loop import StepResult, TrainResult, train_model
from pytorch_engine.transforms import get_chest_xray_eval_transform, get_chest_xray_train_transform
from pytorch_engine.utils import resolve_device, set_seeds

EpochEndCallback = Callable[[int, torch.nn.Module, StepResult, StepResult], None]


@dataclass
class ChestXrayImageFolderLoaders:
    """ImageFolder-backed train/val/test dataloaders plus class names."""

    train_dataloader: DataLoader[Any]
    val_dataloader: DataLoader[Any]
    test_dataloader: DataLoader[Any]
    class_names: list[str]


@dataclass
class ChestXrayTrainingConfig:
    """Configuration for EfficientNet-B0 chest X-ray fine-tuning."""

    dataset_root: str | Path
    output_dir: str | Path = field(default_factory=lambda: Path("src") / "pytorch-saved-models" / "effnetb0_chest_xray")
    best_checkpoint_name: str = "best.pth"
    last_checkpoint_name: str = "last.pth"
    batch_size: int = 32
    image_size: tuple[int, int] = (224, 224)
    resize_size: tuple[int, int] = (256, 256)
    num_workers: int | None = None
    prefetch_factor: int = 2
    pin_memory: bool | None = None
    seed: int = 42
    device: str | torch.device = "auto"
    dropout_p: float = 0.2
    head_warmup_epochs: int = 2
    fine_tune_epochs: int = 10
    trainable_feature_blocks: int = 2
    head_learning_rate: float = 3e-4
    fine_tune_head_learning_rate: float = 1e-4
    backbone_learning_rate: float = 3e-5
    weight_decay: float = 1e-4
    scheduler_eta_min: float = 1e-6
    grad_clip_max_norm: float = 1.0
    use_amp: bool | None = None
    amp_dtype: torch.dtype = torch.float16
    use_channels_last: bool | None = None
    compile_model: bool = True
    compile_mode: str = "max-autotune"
    early_stopping_patience: int = 3
    early_stopping_min_delta: float = 0.0
    positive_class_name: str = "PNEUMONIA"
    selection_metric: str = "auroc"
    selection_mode: str = "max"
    fine_tune_epoch_end_callback: EpochEndCallback | None = None

    def __post_init__(self) -> None:
        if self.batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if self.head_warmup_epochs < 0:
            raise ValueError("head_warmup_epochs must be >= 0")
        if self.fine_tune_epochs < 0:
            raise ValueError("fine_tune_epochs must be >= 0")
        if self.head_warmup_epochs + self.fine_tune_epochs < 1:
            raise ValueError("At least one training epoch is required.")
        if self.trainable_feature_blocks < 0:
            raise ValueError("trainable_feature_blocks must be >= 0")
        if self.num_workers is not None and self.num_workers < 0:
            raise ValueError("num_workers must be >= 0 or None")
        if self.prefetch_factor < 1:
            raise ValueError("prefetch_factor must be >= 1")
        if self.early_stopping_patience < 1:
            raise ValueError("early_stopping_patience must be >= 1")
        if self.early_stopping_min_delta < 0:
            raise ValueError("early_stopping_min_delta must be >= 0")
        if self.selection_mode not in {"min", "max"}:
            raise ValueError("selection_mode must be either 'min' or 'max'")


@dataclass
class ChestXrayTrainingRun:
    """Artifacts and metrics produced by chest X-ray EfficientNet training."""

    config: ChestXrayTrainingConfig
    class_names: list[str]
    model: torch.nn.Module
    warmup_results: TrainResult | None
    fine_tune_results: TrainResult | None
    warmup_val_metrics: ClassificationMetrics | None
    val_metrics: ClassificationMetrics
    test_metrics: ClassificationMetrics
    best_checkpoint_path: Path
    last_checkpoint_path: Path
    selected_phase: str


def _resolve_loader_workers(config: ChestXrayTrainingConfig) -> int:
    if config.num_workers is not None:
        return config.num_workers
    return min(8, os.cpu_count() or 4)


def _save_checkpoint(model: torch.nn.Module, checkpoint_path: Path) -> None:
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    model_to_save = getattr(model, "_orig_mod", model)
    if isinstance(model_to_save, torch.nn.Module):
        torch.save(model_to_save.state_dict(), checkpoint_path)
        return
    raise TypeError("Expected torch.nn.Module when saving checkpoint.")


def _unfreeze_last_feature_blocks(model: torch.nn.Module, blocks_to_unfreeze: int) -> int:
    if blocks_to_unfreeze <= 0:
        return 0
    feature_blocks = getattr(model, "features", None)
    if not isinstance(feature_blocks, torch.nn.Sequential):
        raise TypeError("EfficientNet model must expose `features` as nn.Sequential.")

    resolved_blocks = min(blocks_to_unfreeze, len(feature_blocks))
    for feature_block in feature_blocks[-resolved_blocks:]:
        for parameter in feature_block.parameters():
            parameter.requires_grad = True
    return resolved_blocks


def _build_validation_metrics(
    model: torch.nn.Module,
    dataloader: DataLoader[Any],
    class_names: list[str],
    config: ChestXrayTrainingConfig,
) -> ClassificationMetrics:
    resolved_device = resolve_device(config.device)
    use_channels_last = (
        config.use_channels_last if config.use_channels_last is not None else resolved_device.type == "cuda"
    )
    return evaluate_classification_model(
        model=model,
        dataloader=dataloader,
        class_names=class_names,
        device=resolved_device,
        use_amp=config.use_amp if config.use_amp is not None else resolved_device.type == "cuda",
        amp_dtype=config.amp_dtype,
        use_channels_last=use_channels_last,
    )


def _selection_value(
    metrics: ClassificationMetrics,
    metric_name: str,
) -> float | None:
    if metric_name == "accuracy":
        return float(metrics["accuracy"])
    if metric_name == "balanced_accuracy":
        return float(metrics["balanced_accuracy"])
    if metric_name == "macro_f1":
        return float(metrics["macro_f1"])
    if metric_name == "macro_precision":
        return float(metrics["macro_precision"])
    if metric_name == "macro_recall":
        return float(metrics["macro_recall"])
    if metric_name == "weighted_f1":
        return float(metrics["weighted_f1"])
    if metric_name == "auroc":
        return metrics["auroc"]
    if metric_name == "average_precision":
        return metrics["average_precision"]
    raise ValueError(f"Unsupported selection metric: {metric_name}")


def _candidate_improves(
    *,
    candidate_value: float | None,
    current_best: float | None,
    mode: str,
    min_delta: float,
) -> bool:
    if candidate_value is None:
        return False
    if current_best is None:
        return True
    if mode == "min":
        return candidate_value < (current_best - min_delta)
    return candidate_value > (current_best + min_delta)


def build_chest_xray_imagefolder_loaders(
    config: ChestXrayTrainingConfig,
) -> ChestXrayImageFolderLoaders:
    """Build train/val/test ImageFolder dataloaders for chest X-rays."""
    dataset_root = Path(config.dataset_root)
    resolved_device = resolve_device(config.device)
    resolved_num_workers = _resolve_loader_workers(config)
    resolved_pin_memory = resolved_device.type == "cuda" if config.pin_memory is None else config.pin_memory

    train_transform = get_chest_xray_train_transform(
        image_size=config.image_size,
        resize_size=config.resize_size,
    )
    eval_transform = get_chest_xray_eval_transform(
        image_size=config.image_size,
        resize_size=config.resize_size,
    )
    train_result = create_dataloader(
        data_dir=str(dataset_root / "train"),
        transform=train_transform,
        batch_size=config.batch_size,
        shuffle=True,
        num_workers=resolved_num_workers,
        drop_last=resolved_device.type == "cuda",
        prefetch_factor=config.prefetch_factor if resolved_num_workers > 0 else None,
        pin_memory=resolved_pin_memory,
    )
    val_result = create_dataloader(
        data_dir=str(dataset_root / "val"),
        transform=eval_transform,
        batch_size=config.batch_size,
        shuffle=False,
        num_workers=resolved_num_workers,
        drop_last=False,
        prefetch_factor=config.prefetch_factor if resolved_num_workers > 0 else None,
        pin_memory=resolved_pin_memory,
    )
    test_result = create_dataloader(
        data_dir=str(dataset_root / "test"),
        transform=eval_transform,
        batch_size=config.batch_size,
        shuffle=False,
        num_workers=resolved_num_workers,
        drop_last=False,
        prefetch_factor=config.prefetch_factor if resolved_num_workers > 0 else None,
        pin_memory=resolved_pin_memory,
    )
    class_names = train_result["class_names"]
    if val_result["class_names"] != class_names or test_result["class_names"] != class_names:
        raise ValueError("train/val/test class names must match for chest X-ray training.")
    if len(class_names) != 2:
        raise ValueError(f"Expected binary classification with 2 classes, got {class_names}.")
    if config.positive_class_name not in class_names:
        raise ValueError(f"positive_class_name '{config.positive_class_name}' not found in class names {class_names}.")

    return ChestXrayImageFolderLoaders(
        train_dataloader=train_result["dataloader"],
        val_dataloader=val_result["dataloader"],
        test_dataloader=test_result["dataloader"],
        class_names=class_names,
    )


def run_chest_xray_effnet_training(
    config: ChestXrayTrainingConfig,
) -> ChestXrayTrainingRun:
    """Train EfficientNet-B0 for binary chest X-ray classification."""
    set_seeds(config.seed)
    dataloaders = build_chest_xray_imagefolder_loaders(config)
    model_bundle = create_effnetb0_model(
        num_classes=len(dataloaders.class_names),
        seed=config.seed,
        dropout_p=config.dropout_p,
        trainable_feature_blocks=0,
    )
    model = model_bundle.model
    classifier = getattr(model, "classifier", None)
    if not isinstance(classifier, torch.nn.Module):
        raise TypeError("EfficientNet model must expose classifier as nn.Module.")
    feature_extractor = getattr(model, "features", None)
    if not isinstance(feature_extractor, torch.nn.Module):
        raise TypeError("EfficientNet model must expose features as nn.Module.")
    loss_fn = torch.nn.CrossEntropyLoss()
    output_dir = Path(config.output_dir)
    best_checkpoint_path = output_dir / config.best_checkpoint_name
    last_checkpoint_path = output_dir / config.last_checkpoint_name
    warmup_results: TrainResult | None = None
    fine_tune_results: TrainResult | None = None
    warmup_val_metrics: ClassificationMetrics | None = None
    selected_phase = "warmup"

    if config.head_warmup_epochs > 0:
        warmup_optimizer = torch.optim.AdamW(
            classifier.parameters(),
            lr=config.head_learning_rate,
            weight_decay=config.weight_decay,
        )
        warmup_results = train_model(
            model=model,
            train_dataloader=dataloaders.train_dataloader,
            test_dataloader=dataloaders.val_dataloader,
            optimizer=warmup_optimizer,
            loss_fn=loss_fn,
            epochs=config.head_warmup_epochs,
            device=config.device,
            compile_model=False,
            use_amp=config.use_amp,
            amp_dtype=config.amp_dtype,
            grad_clip_max_norm=config.grad_clip_max_norm,
            use_channels_last=config.use_channels_last,
            early_stopping_patience=None,
        )
        warmup_val_metrics = _build_validation_metrics(
            model=model,
            dataloader=dataloaders.val_dataloader,
            class_names=dataloaders.class_names,
            config=config,
        )

    selected_model_state = deepcopy(model.state_dict())
    selected_val_metrics = warmup_val_metrics
    selected_metric_value = (
        _selection_value(warmup_val_metrics, config.selection_metric) if warmup_val_metrics is not None else None
    )

    if config.fine_tune_epochs > 0:
        _unfreeze_last_feature_blocks(model, config.trainable_feature_blocks)
        backbone_parameters = [parameter for parameter in feature_extractor.parameters() if parameter.requires_grad]
        classifier_parameters = [parameter for parameter in classifier.parameters() if parameter.requires_grad]
        fine_tune_parameter_groups: list[dict[str, Any]] = []
        if backbone_parameters:
            fine_tune_parameter_groups.append({"params": backbone_parameters, "lr": config.backbone_learning_rate})
        if classifier_parameters:
            fine_tune_parameter_groups.append(
                {"params": classifier_parameters, "lr": config.fine_tune_head_learning_rate}
            )
        fine_tune_optimizer = torch.optim.AdamW(
            fine_tune_parameter_groups,
            weight_decay=config.weight_decay,
        )
        fine_tune_scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            fine_tune_optimizer,
            T_max=max(config.fine_tune_epochs, 1),
            eta_min=config.scheduler_eta_min,
        )

        def save_last_checkpoint_callback(
            _epoch: int,
            callback_model: torch.nn.Module,
            _train_result: StepResult,
            _test_result: StepResult,
        ) -> None:
            _save_checkpoint(callback_model, last_checkpoint_path)

        def combined_epoch_end_callback(
            epoch: int,
            callback_model: torch.nn.Module,
            train_result: StepResult,
            test_result: StepResult,
        ) -> None:
            save_last_checkpoint_callback(
                epoch,
                callback_model,
                train_result,
                test_result,
            )
            if config.fine_tune_epoch_end_callback is not None:
                config.fine_tune_epoch_end_callback(
                    epoch,
                    callback_model,
                    train_result,
                    test_result,
                )

        fine_tune_results = train_model(
            model=model,
            train_dataloader=dataloaders.train_dataloader,
            test_dataloader=dataloaders.val_dataloader,
            optimizer=fine_tune_optimizer,
            loss_fn=loss_fn,
            epochs=config.fine_tune_epochs,
            device=config.device,
            epoch_end_callback=combined_epoch_end_callback,
            compile_model=config.compile_model,
            compile_mode=config.compile_mode,
            use_amp=config.use_amp,
            amp_dtype=config.amp_dtype,
            lr_scheduler=fine_tune_scheduler,
            grad_clip_max_norm=config.grad_clip_max_norm,
            use_channels_last=config.use_channels_last,
            early_stopping_patience=config.early_stopping_patience,
            early_stopping_min_delta=config.early_stopping_min_delta,
            validation_metrics_callback=lambda _epoch, validation_model: {
                config.selection_metric: _selection_value(
                    _build_validation_metrics(
                        model=validation_model,
                        dataloader=dataloaders.val_dataloader,
                        class_names=dataloaders.class_names,
                        config=config,
                    ),
                    config.selection_metric,
                )
            },
            selection_metric=config.selection_metric,
            selection_mode=config.selection_mode,
        )
        fine_tune_val_metrics = _build_validation_metrics(
            model=model,
            dataloader=dataloaders.val_dataloader,
            class_names=dataloaders.class_names,
            config=config,
        )
        fine_tune_metric_value = _selection_value(fine_tune_val_metrics, config.selection_metric)
        if _candidate_improves(
            candidate_value=fine_tune_metric_value,
            current_best=selected_metric_value,
            mode=config.selection_mode,
            min_delta=config.early_stopping_min_delta,
        ):
            selected_model_state = deepcopy(model.state_dict())
            selected_val_metrics = fine_tune_val_metrics
            selected_metric_value = fine_tune_metric_value
            selected_phase = "fine_tune"

    if selected_val_metrics is None:
        selected_val_metrics = _build_validation_metrics(
            model=model,
            dataloader=dataloaders.val_dataloader,
            class_names=dataloaders.class_names,
            config=config,
        )
        selected_metric_value = _selection_value(selected_val_metrics, config.selection_metric)
        selected_model_state = deepcopy(model.state_dict())

    model.load_state_dict(selected_model_state)
    _save_checkpoint(model, best_checkpoint_path)
    if not last_checkpoint_path.is_file():
        _save_checkpoint(model, last_checkpoint_path)

    test_metrics = _build_validation_metrics(
        model=model,
        dataloader=dataloaders.test_dataloader,
        class_names=dataloaders.class_names,
        config=config,
    )

    return ChestXrayTrainingRun(
        config=config,
        class_names=dataloaders.class_names,
        model=model,
        warmup_results=warmup_results,
        fine_tune_results=fine_tune_results,
        warmup_val_metrics=warmup_val_metrics,
        val_metrics=selected_val_metrics,
        test_metrics=test_metrics,
        best_checkpoint_path=best_checkpoint_path,
        last_checkpoint_path=last_checkpoint_path,
        selected_phase=selected_phase,
    )
