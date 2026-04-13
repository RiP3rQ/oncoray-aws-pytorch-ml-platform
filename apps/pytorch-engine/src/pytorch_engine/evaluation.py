"""Evaluation helpers for image classification models."""

from __future__ import annotations

from contextlib import nullcontext
from typing import Any, TypedDict

import numpy as np
import torch
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
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
    class_names: list[str]
    per_class_precision: dict[str, float]
    per_class_recall: dict[str, float]
    per_class_f1: dict[str, float]
    per_class_support: dict[str, int]
    confusion_matrix: list[list[int]]
    normalized_confusion_matrix: list[list[float]]
    y_true: list[int]
    y_pred: list[int]


def _autocast_context(
    device: torch.device,
    use_amp: bool,
    amp_dtype: torch.dtype,
) -> Any:
    """Return an autocast context when CUDA AMP is enabled."""
    if not use_amp or device.type != "cuda":
        return nullcontext()
    return torch.autocast(device_type=device.type, dtype=amp_dtype)


def evaluate_classification_model(
    model: torch.nn.Module,
    dataloader: DataLoader[Any],
    class_names: list[str],
    device: str | torch.device = "auto",
    use_amp: bool = False,
    amp_dtype: torch.dtype = torch.float16,
    use_channels_last: bool = False,
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

    Returns:
        Aggregate and per-class metrics, confusion matrices, and raw labels.
    """
    computed_device = resolve_device(device)
    use_non_blocking = computed_device.type == "cuda"

    model = model.to(computed_device)
    if use_channels_last:
        model = model.to(memory_format=torch.channels_last)  # type: ignore[call-overload]
    model.eval()

    true_batches: list[torch.Tensor] = []
    pred_batches: list[torch.Tensor] = []

    with torch.inference_mode():
        for X, y in dataloader:
            X = X.to(computed_device, non_blocking=use_non_blocking)
            y = y.to(computed_device, non_blocking=use_non_blocking)
            if use_channels_last and X.ndim == 4:
                X = X.contiguous(memory_format=torch.channels_last)

            with _autocast_context(
                device=computed_device,
                use_amp=use_amp,
                amp_dtype=amp_dtype,
            ):
                logits = model(X)

            pred_batches.append(logits.argmax(dim=1).cpu())
            true_batches.append(y.cpu())

    y_true = torch.cat(true_batches).numpy()
    y_pred = torch.cat(pred_batches).numpy()

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

    return ClassificationMetrics(
        accuracy=float(accuracy_score(y_true, y_pred)),
        balanced_accuracy=float(balanced_accuracy_score(y_true, y_pred)),
        macro_f1=float(macro_f1),
        macro_precision=float(macro_precision),
        macro_recall=float(macro_recall),
        weighted_f1=float(weighted_f1),
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
        y_true=y_true.astype(int).tolist(),
        y_pred=y_pred.astype(int).tolist(),
    )
