"""Chest X-ray ViT-B/16 training pipeline."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import torch
import torchvision
from torch.utils.data import DataLoader

from pytorch_engine.data_setup import create_dataloader
from pytorch_engine.evaluation import (
    ClassificationMetrics,
    build_classification_metrics,
    evaluate_classification_model,
)
from pytorch_engine.models import create_vit_model
from pytorch_engine.regularization import MixUpBatchTransform, SoftTargetCrossEntropyLoss
from pytorch_engine.training_loop import StepResult, TrainResult, train_model
from pytorch_engine.transforms import get_chest_xray_eval_transform, get_chest_xray_train_transform
from pytorch_engine.utils import clone_state_dict_to_cpu, resolve_device, set_seeds

EpochEndCallback = Callable[[int, torch.nn.Module, StepResult, StepResult], None]


@dataclass(frozen=True)
class OptimizerGroupSummary:
    """Human-readable summary for one optimizer parameter group.

    Attributes:
        group_name: Descriptive group identifier used in notebook tables.
        learning_rate: Learning rate assigned to the parameter group.
        weight_decay: Weight decay assigned to the parameter group.
        parameter_count: Number of trainable parameters inside the group.
    """

    group_name: str
    learning_rate: float
    weight_decay: float
    parameter_count: int


@dataclass
class ChestXrayVitImageFolderLoaders:
    """ImageFolder-backed chest X-ray dataloaders for ViT training.

    Attributes:
        train_dataloader: Augmented training dataloader.
        val_dataloader: Deterministic validation dataloader.
        test_dataloader: Deterministic held-out test dataloader.
        class_names: Ordered class labels inferred from directory names.
    """

    train_dataloader: DataLoader[Any]
    val_dataloader: DataLoader[Any]
    test_dataloader: DataLoader[Any]
    class_names: list[str]


@dataclass
class ChestXrayVitTrainingConfig:
    """Configuration for chest X-ray ViT-B/16 transfer learning.

    Attributes:
        dataset_root: Dataset directory containing ``train/``, ``val/``, and
            ``test/`` ImageFolder splits.
        output_dir: Directory that receives stable ``best.pth`` and
            ``last.pth`` checkpoints.
        best_checkpoint_name: Filename for best-validation checkpoint.
        last_checkpoint_name: Filename for last-epoch checkpoint.
        batch_size: Samples per minibatch.
        image_size: Final image size after cropping. Keep this at ``(224, 224)``
            for the torchvision ViT-B/16 weights used here.
        resize_size: Size used before crop to preserve a little framing jitter.
        num_workers: DataLoader worker count. ``None`` auto-selects a sensible
            value from available CPU cores.
        prefetch_factor: Number of prefetched batches per worker.
        pin_memory: Whether to pin host memory before device transfer.
        seed: Global random seed.
        device: Training device or ``"auto"``.
        label_smoothing: Label smoothing used during head warmup.
        head_warmup_epochs: Epochs to train only the fresh classifier head.
        fine_tune_epochs: Epochs to run selective backbone fine-tuning.
        fine_tune_lr_warmup_epochs: Linear warmup epochs before cosine decay
            inside the fine-tuning stage.
        trainable_encoder_blocks: Number of final transformer blocks to unfreeze.
        head_warmup_lr: Learning rate for the head-only warmup phase.
        fine_tune_head_lr: Head learning rate during selective fine-tuning.
        backbone_lr: Backbone learning rate during selective fine-tuning.
        min_learning_rate: Minimum cosine scheduler learning rate.
        weight_decay: AdamW weight decay for decayed parameter groups.
        mixup_alpha: Beta distribution concentration for MixUp sampling.
        mixup_probability: Probability of applying MixUp to a training batch.
        grad_clip_max_norm: Gradient clipping threshold.
        use_amp: Whether to enable automatic mixed precision.
        amp_dtype: AMP dtype to use when autocast is enabled.
        use_channels_last: Whether to move image batches to channels-last memory
            format. ViT defaults to ``False`` because gains are modest compared
            with convolutional backbones.
        compile_model: Whether to enable ``torch.compile`` during fine-tuning.
        compile_mode: Requested ``torch.compile`` mode.
        early_stopping_patience: Number of non-improving epochs to tolerate.
        early_stopping_min_delta: Minimum selection-metric improvement required
            to reset early stopping.
        positive_class_name: Positive class label used for AUROC/AP metrics.
        selection_metric: Validation metric used for model selection.
        selection_mode: ``"max"`` when larger metric values are better,
            ``"min"`` when smaller values are better.
        fine_tune_epoch_end_callback: Optional callback invoked after each
            fine-tuning epoch. Useful for milestone checkpointing in long runs.
    """

    dataset_root: str | Path
    output_dir: str | Path = field(default_factory=lambda: Path("src") / "pytorch-saved-models" / "vitb16_chest_xray")
    best_checkpoint_name: str = "best.pth"
    last_checkpoint_name: str = "last.pth"
    batch_size: int = 16
    image_size: tuple[int, int] = (224, 224)
    resize_size: tuple[int, int] = (256, 256)
    num_workers: int | None = None
    prefetch_factor: int = 2
    pin_memory: bool | None = None
    seed: int = 42
    device: str | torch.device = "auto"
    label_smoothing: float = 0.05
    head_warmup_epochs: int = 2
    fine_tune_epochs: int = 18
    fine_tune_lr_warmup_epochs: int = 3
    trainable_encoder_blocks: int = 2
    head_warmup_lr: float = 5e-4
    fine_tune_head_lr: float = 1e-4
    backbone_lr: float = 2e-5
    min_learning_rate: float = 1e-6
    weight_decay: float = 5e-2
    mixup_alpha: float = 0.2
    mixup_probability: float = 0.5
    grad_clip_max_norm: float = 1.0
    use_amp: bool | None = None
    amp_dtype: torch.dtype = torch.float16
    use_channels_last: bool | None = False
    compile_model: bool = True
    compile_mode: str = "max-autotune"
    early_stopping_patience: int = 6
    early_stopping_min_delta: float = 1e-4
    positive_class_name: str = "PNEUMONIA"
    selection_metric: str = "auroc"
    selection_mode: str = "max"
    fine_tune_epoch_end_callback: EpochEndCallback | None = None

    def __post_init__(self) -> None:
        """Validate hyperparameters after dataclass initialisation."""
        if self.batch_size < 1:
            raise ValueError("batch_size must be >= 1")
        if self.image_size[0] != self.image_size[1]:
            raise ValueError("image_size must be square for torchvision ViT-B/16.")
        if self.head_warmup_epochs < 0:
            raise ValueError("head_warmup_epochs must be >= 0")
        if self.fine_tune_epochs < 0:
            raise ValueError("fine_tune_epochs must be >= 0")
        if self.head_warmup_epochs + self.fine_tune_epochs < 1:
            raise ValueError("At least one training epoch is required.")
        if self.fine_tune_lr_warmup_epochs < 0:
            raise ValueError("fine_tune_lr_warmup_epochs must be >= 0")
        if self.trainable_encoder_blocks < 0:
            raise ValueError("trainable_encoder_blocks must be >= 0")
        if self.num_workers is not None and self.num_workers < 0:
            raise ValueError("num_workers must be >= 0 or None")
        if self.prefetch_factor < 1:
            raise ValueError("prefetch_factor must be >= 1")
        if not (0.0 <= self.label_smoothing < 1.0):
            raise ValueError("label_smoothing must be in [0, 1)")
        if self.mixup_alpha <= 0:
            raise ValueError("mixup_alpha must be > 0")
        if not (0.0 <= self.mixup_probability <= 1.0):
            raise ValueError("mixup_probability must be in [0, 1]")
        if self.weight_decay < 0:
            raise ValueError("weight_decay must be >= 0")
        if self.min_learning_rate < 0:
            raise ValueError("min_learning_rate must be >= 0")
        if self.early_stopping_patience < 1:
            raise ValueError("early_stopping_patience must be >= 1")
        if self.early_stopping_min_delta < 0:
            raise ValueError("early_stopping_min_delta must be >= 0")
        if self.selection_mode not in {"min", "max"}:
            raise ValueError("selection_mode must be either 'min' or 'max'")


@dataclass
class ChestXrayVitTrainingRun:
    """Artifacts and metrics produced by chest X-ray ViT training.

    Attributes:
        config: Training configuration used for the run.
        class_names: Ordered class labels used by the model head.
        model: Best-selected model restored to its chosen checkpoint weights.
        warmup_results: Training curves from the head-warmup phase.
        fine_tune_results: Training curves from the selective fine-tuning phase.
        warmup_val_metrics: Validation metrics measured after warmup.
        val_metrics: Validation metrics for the selected final model.
        test_metrics: Test metrics for the selected final model.
        optimizer_group_summaries: Summary of parameter groups used by AdamW
            during fine-tuning.
        unfrozen_encoder_blocks: Number of transformer blocks unfrozen during
            fine-tuning.
        best_checkpoint_path: Path to the best-validation checkpoint.
        last_checkpoint_path: Path to the last-epoch checkpoint.
        selected_phase: Training phase that produced the kept model weights.
    """

    config: ChestXrayVitTrainingConfig
    class_names: list[str]
    model: torch.nn.Module
    warmup_results: TrainResult | None
    fine_tune_results: TrainResult | None
    warmup_val_metrics: ClassificationMetrics | None
    val_metrics: ClassificationMetrics
    test_metrics: ClassificationMetrics
    optimizer_group_summaries: list[OptimizerGroupSummary]
    unfrozen_encoder_blocks: int
    best_checkpoint_path: Path
    last_checkpoint_path: Path
    selected_phase: str


def _resolve_loader_workers(config: ChestXrayVitTrainingConfig) -> int:
    """Resolve the number of DataLoader workers for the current run.

    Args:
        config: ViT training configuration.

    Returns:
        Explicitly configured worker count, or ``min(8, cpu_count)`` when the
        caller leaves worker selection to the pipeline.
    """
    if config.num_workers is not None:
        return config.num_workers
    return min(8, os.cpu_count() or 4)


def _get_reference_vit_eval_transform() -> torchvision.transforms.Compose:
    """Return torchvision's canonical ViT-B/16 preprocessing transform.

    Returns:
        The preprocessing transform bundled with the ImageNet SWAG Linear
        ViT-B/16 weights used throughout this training pipeline.
    """
    weights = torchvision.models.ViT_B_16_Weights.IMAGENET1K_SWAG_LINEAR_V1
    return weights.transforms()


def _build_vit_transforms(
    config: ChestXrayVitTrainingConfig,
) -> tuple[torchvision.transforms.Compose, torchvision.transforms.Compose]:
    """Build chest-X-ray-safe train and evaluation transforms for ViT.

    Args:
        config: ViT training configuration.

    Returns:
        A ``(train_transform, eval_transform)`` tuple aligned with the
        pretrained ViT normalization statistics and interpolation settings.
    """
    reference_transform = _get_reference_vit_eval_transform()
    reference_crop_size = (
        reference_transform.crop_size[0]
        if isinstance(reference_transform.crop_size, (tuple, list))
        else reference_transform.crop_size
    )
    if config.image_size != (reference_crop_size, reference_crop_size):
        raise ValueError(
            "image_size must match torchvision ViT-B/16 pretrained crop size "
            f"{(reference_crop_size, reference_crop_size)}, got {config.image_size}."
        )

    train_transform = get_chest_xray_train_transform(
        image_size=config.image_size,
        resize_size=config.resize_size,
        normalize_mean=list(reference_transform.mean),
        normalize_std=list(reference_transform.std),
        interpolation=reference_transform.interpolation,
    )
    eval_transform = get_chest_xray_eval_transform(
        image_size=config.image_size,
        resize_size=config.resize_size,
        normalize_mean=list(reference_transform.mean),
        normalize_std=list(reference_transform.std),
        interpolation=reference_transform.interpolation,
    )
    return train_transform, eval_transform


def _save_checkpoint(model: torch.nn.Module, checkpoint_path: Path) -> None:
    """Save a stable checkpoint path for local notebook workflows.

    Args:
        model: Model whose ``state_dict`` should be written.
        checkpoint_path: Exact destination path, including filename.
    """
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    model_to_save = getattr(model, "_orig_mod", model)
    if not isinstance(model_to_save, torch.nn.Module):
        raise TypeError("Expected torch.nn.Module when saving checkpoint.")
    torch.save(model_to_save.state_dict(), checkpoint_path)


def _unfreeze_last_vit_encoder_blocks(module: torch.nn.Module, blocks_to_unfreeze: int) -> int:
    """Unfreeze final ViT encoder blocks plus companion trainable parameters.

    Args:
        module: ViT model created by :func:`create_vit_model`.
        blocks_to_unfreeze: Number of trailing encoder blocks to unfreeze.

    Returns:
        Number of encoder blocks actually unfrozen after clamping to the model
        depth.
    """
    if blocks_to_unfreeze <= 0:
        return 0

    encoder = getattr(module, "encoder", None)
    if not isinstance(encoder, torch.nn.Module):
        raise TypeError("ViT model must expose encoder as nn.Module.")
    encoder_layers = getattr(encoder, "layers", None)
    if encoder_layers is None:
        raise AttributeError("ViT encoder does not expose encoder layers for partial fine-tuning.")

    encoder_blocks = list(encoder_layers.children())
    resolved_blocks = min(blocks_to_unfreeze, len(encoder_blocks))
    for encoder_block in encoder_blocks[-resolved_blocks:]:
        for parameter in encoder_block.parameters():
            parameter.requires_grad = True

    encoder_ln = getattr(encoder, "ln", None)
    if isinstance(encoder_ln, torch.nn.Module):
        for parameter in encoder_ln.parameters():
            parameter.requires_grad = True

    class_token = getattr(module, "class_token", None)
    if isinstance(class_token, torch.nn.Parameter):
        class_token.requires_grad = True

    pos_embedding = getattr(encoder, "pos_embedding", None)
    if isinstance(pos_embedding, torch.nn.Parameter):
        pos_embedding.requires_grad = True

    return resolved_blocks


def _build_adamw_parameter_groups(
    module: torch.nn.Module,
    *,
    head_lr: float,
    weight_decay: float,
    backbone_lr: float | None = None,
) -> tuple[list[dict[str, Any]], list[OptimizerGroupSummary]]:
    """Create AdamW parameter groups with no-decay handling for norms/tokens.

    Args:
        module: Model whose trainable parameters should be grouped.
        head_lr: Learning rate for classifier-head parameters.
        weight_decay: Weight decay for parameters that should be decayed.
        backbone_lr: Optional learning rate for backbone parameters. When
            ``None``, only head parameter groups are returned.

    Returns:
        A tuple containing:

        - parameter groups ready for :class:`torch.optim.AdamW`
        - notebook-friendly summaries of those parameter groups
    """
    grouped_parameters: dict[str, list[torch.nn.Parameter]] = {
        "backbone_decay": [],
        "backbone_no_decay": [],
        "head_decay": [],
        "head_no_decay": [],
    }

    for name, parameter in module.named_parameters():
        if not parameter.requires_grad:
            continue

        is_head = name.startswith("heads.")
        apply_no_decay = (
            parameter.ndim <= 1 or name.endswith(".bias") or "class_token" in name or "pos_embedding" in name
        )

        if is_head and apply_no_decay:
            grouped_parameters["head_no_decay"].append(parameter)
        elif is_head:
            grouped_parameters["head_decay"].append(parameter)
        elif apply_no_decay:
            grouped_parameters["backbone_no_decay"].append(parameter)
        else:
            grouped_parameters["backbone_decay"].append(parameter)

    parameter_groups: list[dict[str, Any]] = []
    group_summaries: list[OptimizerGroupSummary] = []
    group_specs = [
        ("backbone_decay", backbone_lr, weight_decay),
        ("backbone_no_decay", backbone_lr, 0.0),
        ("head_decay", head_lr, weight_decay),
        ("head_no_decay", head_lr, 0.0),
    ]
    for group_name, group_lr, group_weight_decay in group_specs:
        parameters = grouped_parameters[group_name]
        if not parameters or group_lr is None:
            continue
        parameter_groups.append(
            {
                "group_name": group_name,
                "params": parameters,
                "lr": group_lr,
                "weight_decay": group_weight_decay,
            }
        )
        group_summaries.append(
            OptimizerGroupSummary(
                group_name=group_name,
                learning_rate=group_lr,
                weight_decay=group_weight_decay,
                parameter_count=sum(parameter.numel() for parameter in parameters),
            )
        )
    return parameter_groups, group_summaries


def _build_validation_metrics(
    model: torch.nn.Module,
    dataloader: DataLoader[Any],
    class_names: list[str],
    config: ChestXrayVitTrainingConfig,
) -> ClassificationMetrics:
    """Evaluate the current model using deterministic validation preprocessing.

    Args:
        model: Model to evaluate.
        dataloader: Validation or test dataloader.
        class_names: Ordered class labels.
        config: ViT training configuration.

    Returns:
        Aggregate and per-class classification metrics.
    """
    resolved_device = resolve_device(config.device)
    resolved_use_amp = config.use_amp if config.use_amp is not None else resolved_device.type == "cuda"
    resolved_use_channels_last = (
        resolved_device.type == "cuda" if config.use_channels_last is None else config.use_channels_last
    )
    return evaluate_classification_model(
        model=model,
        dataloader=dataloader,
        class_names=class_names,
        device=resolved_device,
        use_amp=resolved_use_amp,
        amp_dtype=config.amp_dtype,
        use_channels_last=resolved_use_channels_last,
    )


def _selection_value(
    metrics: ClassificationMetrics,
    metric_name: str,
) -> float | None:
    """Extract the scalar validation metric used for phase selection.

    Args:
        metrics: Computed classification metrics.
        metric_name: Metric key to extract.

    Returns:
        Scalar metric value, or ``None`` when the requested metric can be
        legitimately unavailable (for example AUROC on a one-class fold).
    """
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
    """Return whether a candidate metric beats the current best value.

    Args:
        candidate_value: Candidate metric from the latest phase.
        current_best: Best metric value seen so far.
        mode: ``"max"`` for larger-is-better metrics, ``"min"`` otherwise.
        min_delta: Minimum required margin for a new candidate to count as an
            improvement.

    Returns:
        ``True`` when the candidate improves on the current best value.
    """
    if candidate_value is None:
        return False
    if current_best is None:
        return True
    if mode == "min":
        return candidate_value < (current_best - min_delta)
    return candidate_value > (current_best + min_delta)


def _validation_metrics_from_step_result(
    step_result: StepResult,
    class_names: list[str],
    positive_class_index: int,
) -> dict[str, float | None]:
    """Build scalar validation metrics from cached epoch predictions.

    Args:
        step_result: Validation result returned by :func:`train_model`.
        class_names: Ordered class labels.
        positive_class_index: Positive class index used for AUROC/AP metrics.

    Returns:
        Scalar validation metrics suitable for early stopping and notebook
        tables.
    """
    if "y_true" not in step_result or "y_pred" not in step_result:
        raise ValueError("StepResult must include cached predictions to build classification metrics.")

    metrics = build_classification_metrics(
        class_names=class_names,
        y_true=step_result["y_true"],
        y_pred=step_result["y_pred"],
        y_prob=step_result.get("y_prob"),
        positive_class_index=positive_class_index,
    )
    return {
        "accuracy": metrics["accuracy"],
        "balanced_accuracy": metrics["balanced_accuracy"],
        "macro_f1": metrics["macro_f1"],
        "macro_precision": metrics["macro_precision"],
        "macro_recall": metrics["macro_recall"],
        "weighted_f1": metrics["weighted_f1"],
        "auroc": metrics["auroc"],
        "average_precision": metrics["average_precision"],
    }


def _build_fine_tune_scheduler(
    optimizer: torch.optim.Optimizer,
    config: ChestXrayVitTrainingConfig,
) -> torch.optim.lr_scheduler.LRScheduler:
    """Build the learning-rate scheduler used during ViT fine-tuning.

    Args:
        optimizer: Fine-tuning optimizer.
        config: ViT training configuration.

    Returns:
        Linear warmup followed by cosine decay when warmup epochs are
        configured, otherwise a plain cosine decay scheduler.
    """
    if 0 < config.fine_tune_lr_warmup_epochs < config.fine_tune_epochs:
        warmup_scheduler = torch.optim.lr_scheduler.LinearLR(
            optimizer,
            start_factor=0.1,
            total_iters=config.fine_tune_lr_warmup_epochs,
        )
        cosine_scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            optimizer,
            T_max=config.fine_tune_epochs - config.fine_tune_lr_warmup_epochs,
            eta_min=config.min_learning_rate,
        )
        return torch.optim.lr_scheduler.SequentialLR(
            optimizer,
            schedulers=[warmup_scheduler, cosine_scheduler],
            milestones=[config.fine_tune_lr_warmup_epochs],
        )
    return torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer,
        T_max=max(config.fine_tune_epochs, 1),
        eta_min=config.min_learning_rate,
    )


def build_chest_xray_vit_imagefolder_loaders(
    config: ChestXrayVitTrainingConfig,
) -> ChestXrayVitImageFolderLoaders:
    """Build train, validation, and test dataloaders for ViT fine-tuning.

    Args:
        config: ViT training configuration.

    Returns:
        ImageFolder-backed dataloaders with chest-X-ray-safe preprocessing and
        consistent class-name ordering across all splits.
    """
    dataset_root = Path(config.dataset_root)
    resolved_device = resolve_device(config.device)
    resolved_num_workers = _resolve_loader_workers(config)
    resolved_pin_memory = resolved_device.type == "cuda" if config.pin_memory is None else config.pin_memory
    train_transform, eval_transform = _build_vit_transforms(config)

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
        raise ValueError("train/val/test class names must match for chest X-ray ViT training.")
    if len(class_names) != 2:
        raise ValueError(f"Expected binary classification with 2 classes, got {class_names}.")
    if config.positive_class_name not in class_names:
        raise ValueError(f"positive_class_name '{config.positive_class_name}' not found in class names {class_names}.")

    return ChestXrayVitImageFolderLoaders(
        train_dataloader=train_result["dataloader"],
        val_dataloader=val_result["dataloader"],
        test_dataloader=test_result["dataloader"],
        class_names=class_names,
    )


def run_chest_xray_vit_training(
    config: ChestXrayVitTrainingConfig,
) -> ChestXrayVitTrainingRun:
    """Train ViT-B/16 for binary chest X-ray classification.

    Args:
        config: ViT training configuration.

    Returns:
        Restored best-selected model plus per-phase curves, evaluation metrics,
        optimizer-group summaries, and stable checkpoint paths.
    """
    set_seeds(config.seed)
    dataloaders = build_chest_xray_vit_imagefolder_loaders(config)
    positive_class_index = dataloaders.class_names.index(config.positive_class_name)

    model_bundle = create_vit_model(
        num_classes=len(dataloaders.class_names),
        seed=config.seed,
        trainable_encoder_blocks=0,
    )
    model = model_bundle.model
    heads = getattr(model, "heads", None)
    if not isinstance(heads, torch.nn.Module):
        raise TypeError("ViT model must expose heads as nn.Module.")

    output_dir = Path(config.output_dir)
    best_checkpoint_path = output_dir / config.best_checkpoint_name
    last_checkpoint_path = output_dir / config.last_checkpoint_name
    warmup_results: TrainResult | None = None
    fine_tune_results: TrainResult | None = None
    warmup_val_metrics: ClassificationMetrics | None = None
    fine_tune_optimizer_group_summaries: list[OptimizerGroupSummary] = []
    selected_phase = "head_warmup"
    unfrozen_encoder_blocks = 0

    if config.head_warmup_epochs > 0:
        warmup_parameter_groups, _ = _build_adamw_parameter_groups(
            model,
            head_lr=config.head_warmup_lr,
            backbone_lr=None,
            weight_decay=config.weight_decay,
        )
        warmup_optimizer = torch.optim.AdamW(
            warmup_parameter_groups,
            betas=(0.9, 0.999),
            eps=1e-8,
        )
        warmup_results = train_model(
            model=model,
            train_dataloader=dataloaders.train_dataloader,
            test_dataloader=dataloaders.val_dataloader,
            optimizer=warmup_optimizer,
            loss_fn=torch.nn.CrossEntropyLoss(label_smoothing=config.label_smoothing),
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

    selected_model_state = clone_state_dict_to_cpu(model.state_dict())
    selected_val_metrics = warmup_val_metrics
    selected_metric_value = (
        _selection_value(warmup_val_metrics, config.selection_metric) if warmup_val_metrics is not None else None
    )

    if config.fine_tune_epochs > 0:
        unfrozen_encoder_blocks = _unfreeze_last_vit_encoder_blocks(model, config.trainable_encoder_blocks)
        mixup_transform = MixUpBatchTransform(
            num_classes=len(dataloaders.class_names),
            alpha=config.mixup_alpha,
            p=config.mixup_probability,
        )
        fine_tune_parameter_groups, fine_tune_optimizer_group_summaries = _build_adamw_parameter_groups(
            model,
            head_lr=config.fine_tune_head_lr,
            backbone_lr=config.backbone_lr,
            weight_decay=config.weight_decay,
        )
        fine_tune_optimizer = torch.optim.AdamW(
            fine_tune_parameter_groups,
            betas=(0.9, 0.999),
            eps=1e-8,
        )
        fine_tune_scheduler = _build_fine_tune_scheduler(fine_tune_optimizer, config)

        def save_last_checkpoint_callback(
            _epoch: int,
            callback_model: torch.nn.Module,
            _train_result: StepResult,
            _test_result: StepResult,
        ) -> None:
            """Persist the latest fine-tuning checkpoint after each epoch."""
            _save_checkpoint(callback_model, last_checkpoint_path)

        def combined_epoch_end_callback(
            epoch: int,
            callback_model: torch.nn.Module,
            train_result: StepResult,
            test_result: StepResult,
        ) -> None:
            """Save the latest checkpoint and run any optional external callback."""
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
            loss_fn=SoftTargetCrossEntropyLoss(),
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
            train_batch_transform=mixup_transform,
            validation_step_metrics_callback=lambda _epoch, step_result: _validation_metrics_from_step_result(
                step_result,
                dataloaders.class_names,
                positive_class_index,
            ),
            eval_positive_class_index=positive_class_index,
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
            selected_model_state = clone_state_dict_to_cpu(model.state_dict())
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
        selected_model_state = clone_state_dict_to_cpu(model.state_dict())

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

    return ChestXrayVitTrainingRun(
        config=config,
        class_names=dataloaders.class_names,
        model=model,
        warmup_results=warmup_results,
        fine_tune_results=fine_tune_results,
        warmup_val_metrics=warmup_val_metrics,
        val_metrics=selected_val_metrics,
        test_metrics=test_metrics,
        optimizer_group_summaries=fine_tune_optimizer_group_summaries,
        unfrozen_encoder_blocks=unfrozen_encoder_blocks,
        best_checkpoint_path=best_checkpoint_path,
        last_checkpoint_path=last_checkpoint_path,
        selected_phase=selected_phase,
    )
