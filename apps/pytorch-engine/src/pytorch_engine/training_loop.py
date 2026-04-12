"""Training loop utilities for PyTorch image classification models.

Provides epoch-level :func:`train_step` and :func:`test_step` helpers, plus
a :func:`train_model` orchestrator that runs a full training run and returns
per-epoch metrics.
"""

import logging
from collections.abc import Callable
from contextlib import nullcontext
from typing import Any, TypedDict, cast

import torch
from torch.utils.data import DataLoader
from tqdm.auto import tqdm

from pytorch_engine.utils import resolve_device

logger = logging.getLogger(__name__)


def _unwrap_model(model: torch.nn.Module) -> torch.nn.Module:
    """Return original module when *model* comes from ``torch.compile``."""
    # ``torch.compile`` wraps the original nn.Module. Unwrapping keeps
    # checkpointing and callback code working with a normal module instance.
    original_model = getattr(model, "_orig_mod", None)
    if isinstance(original_model, torch.nn.Module):
        return original_model
    return model


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


# ---------------------------------------------------------------------------
# Result types
# ---------------------------------------------------------------------------


class StepResult(TypedDict):
    """Return type for :func:`train_step` and :func:`test_step`.

    Attributes:
        loss: Average loss over all samples in the epoch.
        accuracy: Average accuracy (0-1) over all samples in the epoch.
    """

    loss: float
    accuracy: float


class TrainResult(TypedDict):
    """Return type for :func:`train_model`.

    Each value is a list of per-epoch measurements whose length equals
    the number of training epochs.

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

    Returns:
        A :class:`StepResult` with average ``loss`` and ``accuracy``.
    """
    computed_device = resolve_device(device)
    use_non_blocking = computed_device.type == "cuda"

    model = cast(torch.nn.Module, model.to(computed_device))
    if use_channels_last:
        model = cast(torch.nn.Module, model.to(memory_format=torch.channels_last))  # type: ignore[call-overload]
    model.train()

    # Track sample-weighted metrics so the final partial batch does not distort
    # epoch averages.
    running_loss: float = 0.0
    running_correct: int = 0
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
        y_pred_class = y_pred.argmax(dim=1)
        running_correct += int(torch.eq(y, y_pred_class).sum().item())
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

            progress_bar.set_postfix(
                {
                    "loss": running_loss / running_examples,
                    "acc": running_correct / running_examples,
                }
            )

    avg_loss = running_loss / running_examples
    avg_acc = running_correct / running_examples

    logger.info("%s step complete - loss=%.4f accuracy=%.4f", phase_name, avg_loss, avg_acc)
    return StepResult(loss=avg_loss, accuracy=avg_acc)


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
    lr_scheduler: torch.optim.lr_scheduler.LRScheduler | None = None,
    grad_clip_max_norm: float | None = None,
    use_channels_last: bool | None = None,
) -> TrainResult:
    """Train and evaluate a model for multiple epochs.

    Runs :func:`train_step` followed by :func:`test_step` for each epoch.
    Reported training metrics come from the online optimization pass, while
    test metrics come from a separate eval-mode pass.

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
        lr_scheduler: Optional epoch-level learning-rate scheduler.
        grad_clip_max_norm: Optional gradient clipping threshold.
        use_channels_last: Enable channels-last memory format for CUDA conv nets.

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
            model = cast(torch.nn.Module, torch.compile(model, mode=compile_mode, options=compile_options))
            base_model = _unwrap_model(model)
            logger.info("Compiled model with torch.compile(mode=%s).", compile_mode)

    # Default AMP behavior tracks CUDA availability, so callers do not need to
    # remember separate notebook flags for CPU vs GPU execution.
    resolved_use_amp = computed_device.type == "cuda" if use_amp is None else use_amp
    scaler = torch.amp.GradScaler(device="cuda", enabled=resolved_use_amp and computed_device.type == "cuda")

    logger.info(
        "Training started - model=%s epochs=%d device=%s compile=%s amp=%s channels_last=%s",
        model.__class__.__name__,
        epochs,
        computed_device,
        model is not base_model,
        resolved_use_amp and computed_device.type == "cuda",
        resolved_use_channels_last,
    )

    results: TrainResult = {
        "train_loss": [],
        "train_acc": [],
        "test_loss": [],
        "test_acc": [],
    }

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
        )

        if lr_scheduler is not None:
            lr_scheduler.step()
        current_lr = optimizer.param_groups[0]["lr"]

        logger.info(
            "Epoch %d/%d - train_loss=%.4f train_acc=%.4f test_loss=%.4f test_acc=%.4f lr=%.6g",
            epoch,
            epochs,
            train_result["loss"],
            train_result["accuracy"],
            test_result["loss"],
            test_result["accuracy"],
            current_lr,
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

        if epoch_end_callback is not None:
            try:
                epoch_end_callback(epoch, base_model, train_result, test_result)
            except Exception as error:  # pragma: no cover - callback runtime dependent
                logger.warning("Epoch-end callback failed at epoch %d: %s", epoch, error)

    logger.info("Training complete - %d epochs finished", epochs)
    return results
