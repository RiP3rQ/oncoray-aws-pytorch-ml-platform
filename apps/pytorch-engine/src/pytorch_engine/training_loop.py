"""Training loop utilities for PyTorch image classification models.

Provides epoch-level :func:`train_step` and :func:`test_step` helpers, plus
a :func:`train_model` orchestrator that runs a full training run and returns
per-epoch metrics.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping
from contextlib import nullcontext
from typing import Any, NotRequired, TypedDict, cast

import torch
from torch.utils.data import DataLoader
from tqdm.auto import tqdm

from pytorch_engine.utils import clone_state_dict_to_cpu, resolve_device

logger = logging.getLogger(__name__)
MAX_AUTOTUNE_MIN_TRAIN_STEPS = 1024
TrainBatchTransform = Callable[
    [torch.Tensor, torch.Tensor],
    tuple[torch.Tensor, torch.Tensor, Callable[[torch.Tensor], float] | None],
]
ValidationMetricsCallback = Callable[[int, torch.nn.Module], Mapping[str, float | None]]


def _describe_train_batch_transform(train_batch_transform: TrainBatchTransform | None) -> str | None:
    """Return a human-readable name for an optional train batch transform."""
    if train_batch_transform is None:
        return None
    transform_name = getattr(train_batch_transform, "__name__", None)
    if isinstance(transform_name, str) and transform_name:
        return transform_name
    class_name = train_batch_transform.__class__.__name__
    return class_name if class_name else "custom_train_batch_transform"


def _unwrap_model(model: torch.nn.Module) -> torch.nn.Module:
    """Return original module when *model* comes from ``torch.compile``."""
    # ``torch.compile`` wraps the original nn.Module. Unwrapping keeps
    # checkpointing and callback code working with a normal module instance.
    original_model = getattr(model, "_orig_mod", None)
    if isinstance(original_model, torch.nn.Module):
        return original_model
    return model


def _set_frozen_batchnorm_eval(model: torch.nn.Module) -> None:
    """Keep frozen BatchNorm layers in eval mode during transfer learning.

    Frozen BatchNorm affine params are not enough: calling ``model.train()``
    would still update running mean/variance on tiny datasets, which often
    hurts validation performance for pretrained backbones.
    """
    for module in model.modules():
        if not isinstance(module, torch.nn.modules.batchnorm._BatchNorm):
            continue
        if all(not param.requires_grad for param in module.parameters(recurse=False)):
            module.eval()


def _step_lr_scheduler(
    lr_scheduler: torch.optim.lr_scheduler.LRScheduler | torch.optim.lr_scheduler.ReduceLROnPlateau,
    validation_loss: float,
) -> None:
    """Advance the LR scheduler using validation loss when required."""
    if isinstance(lr_scheduler, torch.optim.lr_scheduler.ReduceLROnPlateau):
        lr_scheduler.step(validation_loss)
        return
    lr_scheduler.step()


def _resolve_compile_mode(
    device: torch.device,
    compile_mode: str,
    train_dataloader: DataLoader[Any],
    epochs: int,
) -> str:
    """Downgrade expensive compile modes when startup cost dominates runtime."""
    if device.type != "cuda" or compile_mode != "max-autotune":
        return compile_mode

    train_batches = len(train_dataloader)
    total_train_steps = train_batches * epochs
    if total_train_steps < MAX_AUTOTUNE_MIN_TRAIN_STEPS:
        logger.info(
            "Downgrading torch.compile mode from max-autotune to reduce-overhead "
            "for short CUDA run (%d train steps across %d epochs, %d batches/epoch).",
            total_train_steps,
            epochs,
            train_batches,
        )
        return "reduce-overhead"
    return compile_mode


def _autocast_context(
    device: torch.device,
    use_amp: bool,
    amp_dtype: torch.dtype,
) -> Any:
    """Return an autocast context when AMP is enabled for supported devices."""
    # AMP helps on CUDA by running selected ops in lower precision.
    # On CPU we fall back to a no-op context to keep one code path.
    if not use_amp or device.type != "cuda":
        return nullcontext()
    return torch.autocast(device_type=device.type, dtype=amp_dtype)


def _prepare_inputs(
    X: torch.Tensor,
    y: torch.Tensor,
    device: torch.device,
    use_non_blocking: bool,
    use_channels_last: bool,
) -> tuple[torch.Tensor, torch.Tensor]:
    """Move a batch to the target device and memory format."""
    X = X.to(device, non_blocking=use_non_blocking)
    y = y.to(device, non_blocking=use_non_blocking)
    if use_channels_last and X.ndim == 4:
        X = X.contiguous(memory_format=torch.channels_last)
    return X, y


def _resolve_selection_metric_value(
    *,
    selection_metric: str,
    test_result: StepResult,
    validation_metrics: Mapping[str, float | None] | None,
) -> float:
    """Return numeric metric value used for best-model selection."""
    if selection_metric == "loss":
        return float(test_result["loss"])
    if selection_metric == "accuracy":
        return float(test_result["accuracy"])
    if validation_metrics is None or selection_metric not in validation_metrics:
        raise ValueError(
            f"selection_metric '{selection_metric}' requires validation_metrics_callback, "
            "validation_step_metrics_callback, or a metric available in test_result."
        )

    metric_value = validation_metrics[selection_metric]
    if metric_value is None:
        raise ValueError(f"selection_metric '{selection_metric}' resolved to None for current epoch.")
    return float(metric_value)


def _is_metric_improvement(
    *,
    current_value: float,
    best_value: float | None,
    selection_mode: str,
    min_delta: float,
) -> bool:
    """Return True when *current_value* beats *best_value* by configured margin."""
    if best_value is None:
        return True
    if selection_mode == "min":
        return current_value < (best_value - min_delta)
    if selection_mode == "max":
        return current_value > (best_value + min_delta)
    raise ValueError("selection_mode must be either 'min' or 'max'")


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


class StepResult(TypedDict):
    """Return type for :func:`train_step` and :func:`test_step`.

    Attributes:
        loss: Average loss over all samples in the epoch.
        accuracy: Average accuracy (0-1) over all samples in the epoch.
        y_true: Optional cached labels from the evaluation pass.
        y_pred: Optional cached predictions from the evaluation pass.
        y_prob: Optional cached positive-class probabilities.
    """

    loss: float
    accuracy: float
    y_true: NotRequired[list[int]]
    y_pred: NotRequired[list[int]]
    y_prob: NotRequired[list[float] | None]


ValidationStepMetricsCallback = Callable[[int, StepResult], Mapping[str, float | None]]


class TrainResult(TypedDict):
    """Return type for :func:`train_model`.

    Each value is a list of per-epoch measurements whose length equals
    the number of executed epochs.

    Attributes:
        train_loss: Training loss per epoch.
        train_acc: Training accuracy per epoch.
        test_loss: Test loss per epoch.
        test_acc: Test accuracy per epoch.
    """

    train_loss: list[float]
    train_acc: list[float]
    test_loss: list[float]
    test_acc: list[float]


# ---------------------------------------------------------------------------
# Single-epoch steps
# ---------------------------------------------------------------------------


def train_step(
    epoch: int,
    model: torch.nn.Module,
    dataloader: DataLoader[Any],
    loss_fn: torch.nn.Module,
    optimizer: torch.optim.Optimizer,
    device: str | torch.device = "auto",
    scaler: Any | None = None,
    use_amp: bool = False,
    amp_dtype: torch.dtype = torch.float16,
    grad_clip_max_norm: float | None = None,
    use_channels_last: bool = False,
    train_batch_transform: TrainBatchTransform | None = None,
) -> StepResult:
    """Run a single training epoch.

    Sets *model* to training mode, iterates every batch in *dataloader*
    (forward -> loss -> backward -> optimizer step), and returns the average
    loss and accuracy across all samples.

    Args:
        epoch: One-based epoch number for progress display.
        model: Model to train.
        dataloader: Training data loader.
        loss_fn: Loss function to minimise.
        optimizer: Optimizer for parameter updates.
        device: ``"auto"`` resolves to CUDA when available.
        scaler: Optional gradient scaler used for AMP training.
        use_amp: Whether to enable AMP autocast during forward/loss.
        amp_dtype: AMP dtype to use when autocast is enabled.
        grad_clip_max_norm: Optional gradient clipping threshold.
        use_channels_last: Whether to convert image batches to channels-last.
        train_batch_transform: Optional training-only batch transform such as
            MixUp. Must return ``(X, y, accuracy_fn)`` after device transfer.

    Returns:
        A :class:`StepResult` with average ``loss`` and ``accuracy``.
    """
    computed_device = resolve_device(device)
    use_non_blocking = computed_device.type == "cuda"

    model = cast(torch.nn.Module, model.to(computed_device))
    if use_channels_last:
        model = cast(torch.nn.Module, model.to(memory_format=torch.channels_last))  # type: ignore[call-overload]
    model.train()
    _set_frozen_batchnorm_eval(model)

    # Track sample-weighted metrics so the final partial batch does not distort
    # epoch averages.
    running_loss: float = 0.0
    running_correct: float = 0.0
    running_examples: int = 0
    num_batches = len(dataloader)

    logger.info("Train step started on %s (%d batches)", computed_device, num_batches)

    # Wrap the dataloader directly so progress and iteration stay in sync.
    progress_bar = tqdm(
        dataloader,
        desc=f"Train {epoch}",
        total=num_batches,
        leave=False,
    )

    for X, y in progress_bar:
        X, y = _prepare_inputs(
            X=X,
            y=y,
            device=computed_device,
            use_non_blocking=use_non_blocking,
            use_channels_last=use_channels_last,
        )
        batch_accuracy_fn: Callable[[torch.Tensor], float] | None = None
        if train_batch_transform is not None:
            X, y, batch_accuracy_fn = train_batch_transform(X, y)
        batch_size = y.size(0)

        # ``set_to_none=True`` avoids writing zeroes into every gradient tensor
        # and is the recommended modern PyTorch reset pattern.
        optimizer.zero_grad(set_to_none=True)

        with _autocast_context(
            device=computed_device,
            use_amp=use_amp,
            amp_dtype=amp_dtype,
        ):
            # Forward pass + loss calculation happen inside autocast when AMP
            # is enabled so supported ops can use faster lower precision math.
            y_pred = model(X)
            loss = loss_fn(y_pred, y)

        running_loss += loss.item() * batch_size

        if scaler is not None and scaler.is_enabled():
            # Gradient scaling prevents small float16 gradients from underflowing.
            scaler.scale(loss).backward()
            if grad_clip_max_norm is not None:
                scaler.unscale_(optimizer)
                torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip_max_norm)
            scaler.step(optimizer)
            scaler.update()
        else:
            loss.backward()
            if grad_clip_max_norm is not None:
                torch.nn.utils.clip_grad_norm_(model.parameters(), grad_clip_max_norm)
            optimizer.step()

        # ``argmax`` on raw logits is enough for top-1 classification.
        if batch_accuracy_fn is not None:
            running_correct += batch_accuracy_fn(y_pred)
        else:
            y_pred_class = y_pred.argmax(dim=1)
            y_metric = y.argmax(dim=1) if y.ndim > 1 else y
            running_correct += float(torch.eq(y_metric, y_pred_class).sum().item())
        running_examples += batch_size

        progress_bar.set_postfix(
            {
                "loss": running_loss / running_examples,
                "acc": running_correct / running_examples,
            }
        )

    avg_loss = running_loss / running_examples
    avg_acc = running_correct / running_examples

    logger.info("Train step complete - loss=%.4f accuracy=%.4f", avg_loss, avg_acc)
    return StepResult(loss=avg_loss, accuracy=avg_acc)


def test_step(
    epoch: int,
    model: torch.nn.Module,
    dataloader: DataLoader[Any],
    loss_fn: torch.nn.Module,
    device: str | torch.device = "auto",
    use_amp: bool = False,
    amp_dtype: torch.dtype = torch.float16,
    use_channels_last: bool = False,
    collect_predictions: bool = False,
    positive_class_index: int | None = None,
) -> StepResult:
    """Run a single evaluation epoch.

    Sets *model* to eval mode with :func:`torch.inference_mode` and
    computes average loss and accuracy over *dataloader*.

    Args:
        epoch: One-based epoch number for progress display.
        model: Model to evaluate.
        dataloader: Test/validation data loader.
        loss_fn: Loss function used for evaluation.
        device: ``"auto"`` resolves to CUDA when available.
        use_amp: Whether to enable AMP autocast during evaluation.
        amp_dtype: AMP dtype to use when autocast is enabled.
        use_channels_last: Whether to convert image batches to channels-last.
        collect_predictions: Whether to cache labels/predictions/probabilities
            from this validation pass for downstream metrics.
        positive_class_index: Optional class index used for cached
            positive-class probabilities when ``collect_predictions`` is True.

    Returns:
        A :class:`StepResult` with average ``loss`` and ``accuracy``.
    """
    return _evaluate_step(
        epoch=epoch,
        phase_name="Eval",
        model=model,
        dataloader=dataloader,
        loss_fn=loss_fn,
        device=device,
        use_amp=use_amp,
        amp_dtype=amp_dtype,
        use_channels_last=use_channels_last,
        collect_predictions=collect_predictions,
        positive_class_index=positive_class_index,
    )


def _evaluate_step(
    epoch: int,
    phase_name: str,
    model: torch.nn.Module,
    dataloader: DataLoader[Any],
    loss_fn: torch.nn.Module,
    device: str | torch.device = "auto",
    use_amp: bool = False,
    amp_dtype: torch.dtype = torch.float16,
    use_channels_last: bool = False,
    collect_predictions: bool = False,
    positive_class_index: int | None = None,
) -> StepResult:
    """Run a single eval-mode pass over *dataloader*.

    Used for validation/test metrics with gradients disabled.
    """
    computed_device = resolve_device(device)
    use_non_blocking = computed_device.type == "cuda"

    model = cast(torch.nn.Module, model.to(computed_device))
    if use_channels_last:
        model = cast(torch.nn.Module, model.to(memory_format=torch.channels_last))  # type: ignore[call-overload]
    model.eval()

    running_loss: float = 0.0
    running_correct: int = 0
    running_examples: int = 0
    num_batches = len(dataloader)
    true_batches: list[torch.Tensor] = []
    pred_batches: list[torch.Tensor] = []
    prob_batches: list[torch.Tensor] = []

    logger.info("%s step started on %s (%d batches)", phase_name, computed_device, num_batches)

    progress_bar = tqdm(
        dataloader,
        desc=f"{phase_name} {epoch}",
        total=num_batches,
        leave=False,
    )

    with torch.inference_mode():
        for X, y in progress_bar:
            X, y = _prepare_inputs(
                X=X,
                y=y,
                device=computed_device,
                use_non_blocking=use_non_blocking,
                use_channels_last=use_channels_last,
            )
            batch_size = y.size(0)

            with _autocast_context(
                device=computed_device,
                use_amp=use_amp,
                amp_dtype=amp_dtype,
            ):
                # Evaluation uses same forward path, but gradients stay disabled.
                test_pred_logits = model(X)
                loss = loss_fn(test_pred_logits, y)

            running_loss += loss.item() * batch_size
            test_pred_labels = test_pred_logits.argmax(dim=1)
            running_correct += int(torch.eq(y, test_pred_labels).sum().item())
            running_examples += batch_size
            if collect_predictions:
                true_batches.append(y.detach().cpu())
                pred_batches.append(test_pred_labels.detach().cpu())
                if positive_class_index is not None:
                    positive_probs = torch.softmax(test_pred_logits, dim=1)[:, positive_class_index]
                    prob_batches.append(positive_probs.detach().cpu())

            progress_bar.set_postfix(
                {
                    "loss": running_loss / running_examples,
                    "acc": running_correct / running_examples,
                }
            )

    avg_loss = running_loss / running_examples
    avg_acc = running_correct / running_examples

    logger.info("%s step complete - loss=%.4f accuracy=%.4f", phase_name, avg_loss, avg_acc)
    result = StepResult(loss=avg_loss, accuracy=avg_acc)
    if collect_predictions:
        result["y_true"] = torch.cat(true_batches).to(dtype=torch.int64).tolist()
        result["y_pred"] = torch.cat(pred_batches).to(dtype=torch.int64).tolist()
        result["y_prob"] = torch.cat(prob_batches).to(dtype=torch.float32).tolist() if prob_batches else None
    return result


# ---------------------------------------------------------------------------
# Full training run
# ---------------------------------------------------------------------------


def train_model(
    model: torch.nn.Module,
    train_dataloader: DataLoader[Any],
    test_dataloader: DataLoader[Any],
    optimizer: torch.optim.Optimizer,
    loss_fn: torch.nn.Module,
    epochs: int,
    device: str | torch.device = "auto",
    epoch_end_callback: Callable[[int, torch.nn.Module, StepResult, StepResult], None] | None = None,
    compile_model: bool = False,
    compile_mode: str = "default",
    compile_options: dict[str, Any] | None = None,
    use_amp: bool | None = None,
    amp_dtype: torch.dtype = torch.float16,
    lr_scheduler: (torch.optim.lr_scheduler.LRScheduler | torch.optim.lr_scheduler.ReduceLROnPlateau | None) = None,
    grad_clip_max_norm: float | None = None,
    use_channels_last: bool | None = None,
    early_stopping_patience: int | None = 5,
    early_stopping_min_delta: float = 0.0,
    train_batch_transform: TrainBatchTransform | None = None,
    validation_metrics_callback: ValidationMetricsCallback | None = None,
    validation_step_metrics_callback: ValidationStepMetricsCallback | None = None,
    eval_positive_class_index: int | None = None,
    selection_metric: str = "loss",
    selection_mode: str = "min",
) -> TrainResult:
    """Train and evaluate a model for multiple epochs.

    Runs :func:`train_step` followed by :func:`test_step` for each epoch.
    Reported training metrics come from the online optimization pass, while
    test metrics come from a separate eval-mode pass. When early stopping is
    enabled, training stops once test loss stops improving and the best model
    weights are restored before returning.

    Args:
        model: Model to train and evaluate.
        train_dataloader: DataLoader for training data.
        test_dataloader: DataLoader for test/validation data.
        optimizer: Optimizer for parameter updates.
        loss_fn: Loss function to minimise.
        epochs: Number of training epochs.
        device: ``"auto"`` resolves to CUDA when available.
        epoch_end_callback: Optional callback called after each epoch with
            ``(epoch_number_1_based, model, train_result, test_result)``.
            Callback failures are logged and training continues.
        compile_model: Compile model inside training loop when CUDA available.
        compile_mode: ``torch.compile`` mode.
        compile_options: Optional ``torch.compile`` backend options.
        use_amp: Enable automatic mixed precision. Defaults to CUDA-only.
        amp_dtype: AMP dtype to use when autocast is enabled.
        lr_scheduler: Optional epoch-level learning-rate scheduler. Metric-based
            schedulers such as ``ReduceLROnPlateau`` receive validation loss.
        grad_clip_max_norm: Optional gradient clipping threshold.
        use_channels_last: Enable channels-last memory format for CUDA conv nets.
        early_stopping_patience: Number of consecutive non-improving epochs to
            tolerate before stopping. Set to ``None`` to disable early stopping.
        early_stopping_min_delta: Minimum improvement required for the selected
            validation metric before it resets early stopping.
        train_batch_transform: Optional training-only batch transform such as
            MixUp. Validation/test data stays unchanged.
        validation_metrics_callback: Optional callback that computes extra
            validation metrics from the current model after each epoch.
        validation_step_metrics_callback: Optional callback that computes
            extra validation metrics directly from cached outputs produced by
            ``test_step`` during the current epoch. Prefer this over
            ``validation_metrics_callback`` when the metric can be derived
            from ``y_true``/``y_pred``/``y_prob`` because it avoids a second
            full validation pass.
        eval_positive_class_index: Optional class index whose probabilities
            should be cached during validation when
            ``validation_step_metrics_callback`` is used.
        selection_metric: Metric name used for best-model restore and early
            stopping. Defaults to ``"loss"`` for backward compatibility.
        selection_mode: Whether lower (``"min"``) or higher (``"max"``)
            values indicate improvement for ``selection_metric``.

    Returns:
        A :class:`TrainResult` dict with per-epoch metric lists.
    """
    computed_device = resolve_device(device)
    resolved_use_channels_last = computed_device.type == "cuda" if use_channels_last is None else use_channels_last
    model = cast(torch.nn.Module, model.to(computed_device))
    if resolved_use_channels_last:
        model = cast(torch.nn.Module, model.to(memory_format=torch.channels_last))  # type: ignore[call-overload]

    # Keep a handle to the real nn.Module so checkpoint callbacks do not need
    # to understand compile wrappers.
    base_model = _unwrap_model(model)
    resolved_compile_mode = _resolve_compile_mode(
        device=computed_device,
        compile_mode=compile_mode,
        train_dataloader=train_dataloader,
        epochs=epochs,
    )

    if compile_model:
        if not hasattr(torch, "compile"):
            logger.warning("torch.compile requested but unavailable in this PyTorch build.")
        elif computed_device.type != "cuda":
            # In this project we only opt into compile for CUDA because compile
            # startup overhead on CPU is usually not worth it for notebook runs.
            logger.info("Skipping torch.compile on %s; project only enables it for CUDA training.", computed_device)
        elif model is not base_model:
            logger.info("Model already compiled; reusing optimized module.")
        else:
            # Compile after model construction but before the first epoch so the
            # training loop uses the optimized graph from the start.
            model = cast(torch.nn.Module, torch.compile(model, mode=resolved_compile_mode, options=compile_options))
            base_model = _unwrap_model(model)
            logger.info("Compiled model with torch.compile(mode=%s).", resolved_compile_mode)

    # Default AMP behavior tracks CUDA availability, so callers do not need to
    # remember separate notebook flags for CPU vs GPU execution.
    resolved_use_amp = computed_device.type == "cuda" if use_amp is None else use_amp
    scaler = torch.amp.GradScaler(device="cuda", enabled=resolved_use_amp and computed_device.type == "cuda")

    logger.info(
        "Training started - model=%s epochs=%d device=%s compile=%s compile_mode=%s amp=%s channels_last=%s",
        model.__class__.__name__,
        epochs,
        computed_device,
        model is not base_model,
        resolved_compile_mode if model is not base_model else "n/a",
        resolved_use_amp and computed_device.type == "cuda",
        resolved_use_channels_last,
    )
    train_batch_transform_name = _describe_train_batch_transform(train_batch_transform)
    if train_batch_transform_name is not None:
        logger.warning(
            "Training batch transform '%s' active. Train loss/accuracy are not directly "
            "comparable to plain-label runs; use validation metrics such as macro_f1, "
            "balanced_accuracy, and per-class recall for model selection.",
            train_batch_transform_name,
        )

    results: TrainResult = {
        "train_loss": [],
        "train_acc": [],
        "test_loss": [],
        "test_acc": [],
    }
    early_stopping_enabled = early_stopping_patience is not None
    best_test_loss: float | None = None
    best_epoch: int | None = None
    best_model_state: dict[str, Any] | None = None
    best_selection_value: float | None = None
    epochs_without_improvement = 0
    resolved_early_stopping_patience = early_stopping_patience
    collect_validation_predictions = validation_step_metrics_callback is not None

    if early_stopping_enabled and resolved_early_stopping_patience is not None and resolved_early_stopping_patience < 1:
        raise ValueError("early_stopping_patience must be >= 1 or None")
    if early_stopping_min_delta < 0:
        raise ValueError("early_stopping_min_delta must be >= 0")
    if selection_mode not in {"min", "max"}:
        raise ValueError("selection_mode must be either 'min' or 'max'")

    for epoch_idx in tqdm(range(epochs), desc="Epochs"):
        epoch = epoch_idx + 1

        # One full epoch = one optimization pass + one eval-mode test pass.
        train_result = train_step(
            epoch=epoch,
            model=model,
            dataloader=train_dataloader,
            loss_fn=loss_fn,
            optimizer=optimizer,
            device=computed_device,
            scaler=scaler,
            use_amp=resolved_use_amp,
            amp_dtype=amp_dtype,
            grad_clip_max_norm=grad_clip_max_norm,
            use_channels_last=resolved_use_channels_last,
            train_batch_transform=train_batch_transform,
        )
        test_result = test_step(
            epoch=epoch,
            model=model,
            dataloader=test_dataloader,
            loss_fn=loss_fn,
            device=computed_device,
            use_amp=resolved_use_amp,
            amp_dtype=amp_dtype,
            use_channels_last=resolved_use_channels_last,
            collect_predictions=collect_validation_predictions,
            positive_class_index=eval_positive_class_index,
        )
        validation_metrics: Mapping[str, float | None] | None = None
        if validation_step_metrics_callback is not None:
            validation_metrics = validation_step_metrics_callback(epoch, test_result)
        elif validation_metrics_callback is not None:
            validation_metrics = validation_metrics_callback(epoch, base_model)
        current_selection_value = _resolve_selection_metric_value(
            selection_metric=selection_metric,
            test_result=test_result,
            validation_metrics=validation_metrics,
        )

        if lr_scheduler is not None:
            _step_lr_scheduler(
                lr_scheduler=lr_scheduler,
                validation_loss=test_result["loss"],
            )
        current_lr = optimizer.param_groups[0]["lr"]
        loss_gap = test_result["loss"] - train_result["loss"]
        acc_gap = train_result["accuracy"] - test_result["accuracy"]

        logger.info(
            "Epoch %d/%d - train_loss=%.4f train_acc=%.4f test_loss=%.4f "
            "test_acc=%.4f loss_gap=%.4f acc_gap=%.4f lr=%.6g",
            epoch,
            epochs,
            train_result["loss"],
            train_result["accuracy"],
            test_result["loss"],
            test_result["accuracy"],
            loss_gap,
            acc_gap,
            current_lr,
        )
        if validation_metrics is not None:
            logger.info(
                "Epoch %d validation metrics - %s",
                epoch,
                {name: value for name, value in validation_metrics.items() if value is not None},
            )
        logger.debug(
            "Epoch %d train metrics - loss=%.4f accuracy=%.4f",
            epoch,
            train_result["loss"],
            train_result["accuracy"],
        )

        results["train_loss"].append(train_result["loss"])
        results["train_acc"].append(train_result["accuracy"])
        results["test_loss"].append(test_result["loss"])
        results["test_acc"].append(test_result["accuracy"])

        if early_stopping_enabled:
            if _is_metric_improvement(
                current_value=current_selection_value,
                best_value=best_selection_value,
                selection_mode=selection_mode,
                min_delta=early_stopping_min_delta,
            ):
                best_test_loss = test_result["loss"]
                best_selection_value = current_selection_value
                best_epoch = epoch
                best_model_state = clone_state_dict_to_cpu(base_model.state_dict())
                epochs_without_improvement = 0
            else:
                epochs_without_improvement += 1

        if epoch_end_callback is not None:
            try:
                epoch_end_callback(epoch, base_model, train_result, test_result)
            except Exception as error:  # pragma: no cover - callback runtime dependent
                logger.warning("Epoch-end callback failed at epoch %d: %s", epoch, error)

        if (
            early_stopping_enabled
            and resolved_early_stopping_patience is not None
            and epochs_without_improvement >= resolved_early_stopping_patience
        ):
            logger.info(
                "Early stopping at epoch %d/%d - best %s=%.4f at epoch %d",
                epoch,
                epochs,
                selection_metric,
                best_selection_value if best_selection_value is not None else float("nan"),
                best_epoch,
            )
            break

    if early_stopping_enabled and best_model_state is not None and best_epoch is not None:
        base_model.load_state_dict(best_model_state)
        logger.info(
            "Restored best model weights from epoch %d (%s=%.4f, test_loss=%.4f).",
            best_epoch,
            selection_metric,
            best_selection_value if best_selection_value is not None else float("nan"),
            best_test_loss if best_test_loss is not None else float("nan"),
        )

    logger.info("Training complete - %d epochs finished", len(results["train_loss"]))
    return results
