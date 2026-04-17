"""Evaluation helpers for image classification models."""

from __future__ import annotations

from collections.abc import Sequence
from contextlib import nullcontext
from typing import Any, TypedDict

import numpy as np
import torch
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
)
from torch.utils.data import DataLoader

from pytorch_engine.utils import resolve_device


class ClassificationMetrics(TypedDict):
    """Aggregate classification metrics and per-class breakdown."""

    accuracy: float
    balanced_accuracy: float
    macro_f1: float
    macro_precision: float
    macro_recall: float
    weighted_f1: float
    auroc: float | None
    average_precision: float | None
    class_names: list[str]
    per_class_precision: dict[str, float]
    per_class_recall: dict[str, float]
    per_class_f1: dict[str, float]
    per_class_support: dict[str, int]
    confusion_matrix: list[list[int]]
    normalized_confusion_matrix: list[list[float]]
    positive_class_index: int | None
    y_prob: list[float] | None
    y_true: list[int]
    y_pred: list[int]


def _resolve_positive_class_index(class_names: list[str]) -> int | None:
    """Return positive-class index for binary classification metrics."""
    if len(class_names) != 2:
        return None
    if "PNEUMONIA" in class_names:
        return class_names.index("PNEUMONIA")
    return 1


def _autocast_context(
    device: torch.device,
    use_amp: bool,
    amp_dtype: torch.dtype,
) -> Any:
    """Return an autocast context when CUDA AMP is enabled."""
    if not use_amp or device.type != "cuda":
        return nullcontext()
    return torch.autocast(device_type=device.type, dtype=amp_dtype)


def _apply_tta_transform(X: torch.Tensor, transform_name: str) -> torch.Tensor:
    """Apply a named deterministic test-time augmentation."""
    if transform_name == "identity":
        return X
    if transform_name == "hflip":
        return torch.flip(X, dims=(-1,))
    if transform_name == "vflip":
        return torch.flip(X, dims=(-2,))
    if transform_name == "rot90":
        return torch.rot90(X, k=1, dims=(-2, -1))
    if transform_name == "rot180":
        return torch.rot90(X, k=2, dims=(-2, -1))
    if transform_name == "rot270":
        return torch.rot90(X, k=3, dims=(-2, -1))
    raise ValueError(f"Unsupported TTA transform: {transform_name}")


def _predict_logits_with_tta(
    model: torch.nn.Module,
    X: torch.Tensor,
    *,
    tta_transforms: Sequence[str],
    use_amp: bool,
    amp_dtype: torch.dtype,
    device: torch.device,
    use_channels_last: bool,
) -> torch.Tensor:
    """Average logits across deterministic TTA variants."""
    logits_sum: torch.Tensor | None = None
    for transform_name in tta_transforms:
        transformed_batch = _apply_tta_transform(X, transform_name)
        if use_channels_last and transformed_batch.ndim == 4:
            transformed_batch = transformed_batch.contiguous(memory_format=torch.channels_last)
        with _autocast_context(
            device=device,
            use_amp=use_amp,
            amp_dtype=amp_dtype,
        ):
            logits = model(transformed_batch)
        logits_sum = logits if logits_sum is None else logits_sum + logits
    assert logits_sum is not None
    return logits_sum / len(tta_transforms)


def evaluate_classification_model(
    model: torch.nn.Module,
    dataloader: DataLoader[Any],
    class_names: list[str],
    device: str | torch.device = "auto",
    use_amp: bool = False,
    amp_dtype: torch.dtype = torch.float16,
    use_channels_last: bool = False,
    tta_transforms: Sequence[str] | None = None,
) -> ClassificationMetrics:
    """Evaluate a classifier on a dataloader with balanced metrics.

    Args:
        model: Classification model returning class logits.
        dataloader: Dataloader yielding ``(inputs, labels)`` batches.
        class_names: Class names in model output order.
        device: Target device. ``"auto"`` prefers CUDA.
        use_amp: Enable autocast during forward pass on CUDA.
        amp_dtype: AMP dtype when autocast is enabled.
        use_channels_last: Use channels-last memory format for image batches.
        tta_transforms: Optional deterministic test-time augmentations whose
            logits will be averaged per batch. Use names such as
            ``("identity", "hflip", "vflip", "rot90")``.

    Returns:
        Aggregate and per-class metrics, confusion matrices, and raw labels.
    """
    computed_device = resolve_device(device)
    use_non_blocking = computed_device.type == "cuda"

    model = model.to(computed_device)
    if use_channels_last:
        model = model.to(memory_format=torch.channels_last)  # type: ignore[call-overload]
    model.eval()
    if tta_transforms is None:
        resolved_tta_transforms: tuple[str, ...] = ("identity",)
    else:
        if isinstance(tta_transforms, str):
            raise ValueError("tta_transforms must be a sequence of transform names, not a single string")
        resolved_tta_transforms = tuple(tta_transforms)
        if len(resolved_tta_transforms) == 0:
            raise ValueError("tta_transforms must not be empty")

    true_batches: list[torch.Tensor] = []
    pred_batches: list[torch.Tensor] = []
    prob_batches: list[torch.Tensor] = []
    positive_class_index = _resolve_positive_class_index(class_names)

    with torch.inference_mode():
        for X, y in dataloader:
            X = X.to(computed_device, non_blocking=use_non_blocking)
            y = y.to(computed_device, non_blocking=use_non_blocking)
            if use_channels_last and X.ndim == 4:
                X = X.contiguous(memory_format=torch.channels_last)
            logits = _predict_logits_with_tta(
                model=model,
                X=X,
                tta_transforms=resolved_tta_transforms,
                use_amp=use_amp,
                amp_dtype=amp_dtype,
                device=computed_device,
                use_channels_last=use_channels_last,
            )

            if positive_class_index is not None:
                probabilities = torch.softmax(logits, dim=1)[:, positive_class_index].cpu()
                prob_batches.append(probabilities)
            pred_batches.append(logits.argmax(dim=1).cpu())
            true_batches.append(y.cpu())

    y_true = torch.cat(true_batches).numpy()
    y_pred = torch.cat(pred_batches).numpy()
    y_prob = torch.cat(prob_batches).numpy() if prob_batches else None

    labels = list(range(len(class_names)))
    per_class_precision, per_class_recall, per_class_f1, per_class_support = precision_recall_fscore_support(
        y_true,
        y_pred,
        labels=labels,
        zero_division=0,
    )
    macro_precision, macro_recall, macro_f1, _ = precision_recall_fscore_support(
        y_true,
        y_pred,
        labels=labels,
        average="macro",
        zero_division=0,
    )
    _, _, weighted_f1, _ = precision_recall_fscore_support(
        y_true,
        y_pred,
        labels=labels,
        average="weighted",
        zero_division=0,
    )

    raw_confusion = confusion_matrix(y_true, y_pred, labels=labels)
    row_sums = raw_confusion.sum(axis=1, keepdims=True)
    normalized_confusion = np.divide(
        raw_confusion,
        row_sums,
        out=np.zeros_like(raw_confusion, dtype=np.float64),
        where=row_sums != 0,
    )
    auroc: float | None = None
    average_precision: float | None = None
    if y_prob is not None:
        try:
            auroc = float(roc_auc_score(y_true, y_prob))
            average_precision = float(average_precision_score(y_true, y_prob))
        except ValueError:
            # Small or pathological validation folds can contain one class only.
            auroc = None
            average_precision = None

    return ClassificationMetrics(
        accuracy=float(accuracy_score(y_true, y_pred)),
        balanced_accuracy=float(balanced_accuracy_score(y_true, y_pred)),
        macro_f1=float(macro_f1),
        macro_precision=float(macro_precision),
        macro_recall=float(macro_recall),
        weighted_f1=float(weighted_f1),
        auroc=auroc,
        average_precision=average_precision,
        class_names=class_names,
        per_class_precision={
            class_name: float(value) for class_name, value in zip(class_names, per_class_precision, strict=True)
        },
        per_class_recall={
            class_name: float(value) for class_name, value in zip(class_names, per_class_recall, strict=True)
        },
        per_class_f1={class_name: float(value) for class_name, value in zip(class_names, per_class_f1, strict=True)},
        per_class_support={
            class_name: int(value) for class_name, value in zip(class_names, per_class_support, strict=True)
        },
        confusion_matrix=raw_confusion.astype(int).tolist(),
        normalized_confusion_matrix=normalized_confusion.tolist(),
        positive_class_index=positive_class_index,
        y_prob=y_prob.astype(float).tolist() if y_prob is not None else None,
        y_true=y_true.astype(int).tolist(),
        y_pred=y_pred.astype(int).tolist(),
    )
